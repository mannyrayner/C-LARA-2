#!/usr/bin/env python3
"""Private, append-only development study journal. Standard library only.

No network, deployment, credential access or model calls. See the how-to for
measurement definitions. This records elapsed response intervals, not internal
reasoning-only time. UTC event time and journal receipt time remain distinct.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

SCHEMA = 1
PHASES = {'assistant_response', 'human_work', 'tool'}
TARGETS = {'development', 'tooling', 'laptop', 'aws', 'staging'}
MILESTONES = {'specification', 'implementation_ready', 'installation_finished',
              'acceptance', 'revision_requested', 'note', 'feature_closed'}
KINDS = MILESTONES | {'request', 'work_started', 'work_stopped', 'workflow_finished', 'void'}
TIMINGS = {'observed', 'reported_exact', 'approximate', 'unknown'}
SOURCES = {'assistant_note', 'human_report', 'local_clock', 'clock_checkpoint',
           'controller_receipt', 'github_workflow'}
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,79}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
EVENT_NAMESPACE = uuid.UUID('3b922457-7f06-4270-94b7-31e269158df5')
TIMING_NOTE = ('Assistant response elapsed time includes reasoning, composition, tools and waits '
    'within instrumented intervals. Internal reasoning-only time is not observable. '
    'Open or unknown-ended intervals are not counted. Partial intervals are identified. '
    'Tool intervals may overlap response intervals and must not be added to them.')


class Invalid(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    if not isinstance(value, str):
        raise Invalid('A timestamp must be a string with a timezone offset.')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise Invalid('Invalid ISO timestamp.') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise Invalid('Naive timestamps are not accepted; include the timezone offset.')
    return result.astimezone(timezone.utc)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def text(value, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Invalid(f'Expected nonempty text of at most {maximum} characters.')
    return value


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise Invalid('Invalid feature identifier.')
    return value


def validate(event):
    required = {'schema', 'event_id', 'feature_id', 'kind', 'recorded_at', 'occurred_at',
                'timing', 'actor', 'source', 'summary', 'evidence', 'data', 'retrospective'}
    if not isinstance(event, dict) or set(event) != required or event['schema'] != SCHEMA:
        raise Invalid('Unsupported event schema or fields.')
    try:
        if str(uuid.UUID(event['event_id'])) != event['event_id']:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise Invalid('Invalid event ID.') from None
    identifier(event['feature_id'])
    if event['kind'] not in KINDS or event['timing'] not in TIMINGS:
        raise Invalid('Unknown event kind or timing precision.')
    timestamp(event['recorded_at'])
    if event['occurred_at'] is not None:
        timestamp(event['occurred_at'])
    if (event['timing'] == 'unknown') != (event['occurred_at'] is None):
        raise Invalid('Unknown times must be null; all other precisions require a timestamp.')
    if event['actor'] not in {'assistant', 'human', 'automation'} or event['source'] not in SOURCES:
        raise Invalid('Unknown actor or evidence source.')
    if not isinstance(event['retrospective'], bool):
        raise Invalid('Retrospective must be a boolean.')
    text(event['summary'])
    if not isinstance(event['evidence'], list) or len(event['evidence']) > 20:
        raise Invalid('Evidence must be a list of at most 20 references.')
    for reference in event['evidence']:
        text(reference, 2048)
    data, kind = event['data'], event['kind']
    if not isinstance(data, dict):
        raise Invalid('Event data must be an object.')
    if 'commit' in data and data['commit'] is not None and not COMMIT.fullmatch(str(data['commit'])):
        raise Invalid('Use a full lowercase Git commit SHA.')
    if 'target' in data and data['target'] not in TARGETS:
        raise Invalid('Unknown target.')
    if kind == 'request':
        text(data.get('title'), 200)
        if data.get('category') not in {'feature', 'bugfix', 'research', 'tooling', 'documentation'}:
            raise Invalid('Unknown feature category.')
    if kind == 'specification' and data.get('status') not in {'proposed', 'agreed'}:
        raise Invalid('Specify whether the specification is proposed or agreed.')
    if kind == 'implementation_ready' and not data.get('commit'):
        raise Invalid('An installable implementation needs an exact commit.')
    if kind in {'installation_finished', 'acceptance', 'revision_requested'} and 'target' not in data:
        raise Invalid('This milestone requires a target.')
    if kind == 'installation_finished':
        if data.get('outcome') not in {'installed', 'prepared', 'refused', 'controller_refused',
                                     'recovered_previous_release', 'recovery_required'}:
            raise Invalid('Unsupported terminal controller outcome.')
        if data['outcome'] in {'installed', 'prepared'} and not data.get('commit'):
            raise Invalid('A successful installation needs an exact commit.')
    if kind == 'acceptance' and event['actor'] != 'human':
        raise Invalid('Functional acceptance must be attributed to an explicit human report.')
    if kind == 'specification' and data['status'] == 'agreed' and event['actor'] != 'human':
        raise Invalid('Human agreement cannot be inferred from an assistant specification.')
    if kind == 'feature_closed' and data.get('outcome') not in {'accepted', 'abandoned', 'superseded'}:
        raise Invalid('Unknown closure outcome.')
    if kind == 'work_started':
        if data.get('phase') not in PHASES or data.get('coverage') not in {'complete', 'partial'}:
            raise Invalid('Unknown work phase or coverage.')
        text(data.get('session_id'), 80)
        if event['timing'] not in {'observed', 'reported_exact'}:
            raise Invalid('A work interval needs an exact or explicitly reported start.')
    if kind == 'work_stopped':
        text(data.get('session_id'), 80)
        if event['timing'] == 'approximate':
            raise Invalid('Use unknown for an unmeasured work interval end.')
    if kind == 'void':
        text(data.get('event_id'), 80)
    return event


def active(events):
    voided = {e['data']['event_id'] for e in events if e['kind'] == 'void'}
    return [e for e in events if e['kind'] != 'void' and e['event_id'] not in voided]


def validate_sequence(events):
    ids = {e['event_id']:e for e in events}
    if len(ids) != len(events):
        raise Invalid('Duplicate event IDs.')
    requests = {}
    for event in events:
        if event['kind'] == 'request':
            if event['feature_id'] in requests:
                raise Invalid('A feature can have only one request record.')
            requests[event['feature_id']] = event
        if event['kind'] == 'void':
            other = ids.get(event['data']['event_id'])
            if not other or other['feature_id'] != event['feature_id'] or other['kind'] in {'request', 'void'}:
                raise Invalid('A correction must reference a non-request event in the same feature.')
    if any(e['feature_id'] not in requests for e in events):
        raise Invalid('Record the feature request before adding events.')
    current = active(events)
    for event in current:
        if event['kind'] == 'feature_closed' and event['data']['outcome'] == 'accepted':
            if event['actor'] != 'human' or not any(
                    e['feature_id'] == event['feature_id'] and e['kind'] == 'acceptance' for e in current):
                raise Invalid('Accepted closure needs a human report and a functional acceptance record.')
    starts, stops = {}, set()
    for event in active(events):
        if event['kind'] == 'work_started':
            key = (event['feature_id'], event['data']['session_id'])
            if key in starts:
                raise Invalid('Duplicate work session.')
            starts[key] = event
    for event in active(events):
        if event['kind'] == 'work_stopped':
            key = (event['feature_id'], event['data']['session_id'])
            if key not in starts or key in stops:
                raise Invalid('A stop needs exactly one start and no previous active stop.')
            stops.add(key)
            if event['occurred_at'] and timestamp(event['occurred_at']) < timestamp(starts[key]['occurred_at']):
                raise Invalid('Work ended before it started; check the clock and timezone.')


class Journal:
    def __init__(self, root, clock=now):
        self.root, self.clock = Path(root), clock

    def read(self):
        folder = self.root / 'events'
        if folder.is_symlink():
            raise Invalid('The events directory cannot be a symlink.')
        events = []
        for path in sorted(folder.glob('*.json')):
            if path.is_symlink():
                raise Invalid('Event files cannot be symlinks.')
            event = validate(json.loads(path.read_text(encoding='utf-8')))
            if path.stem != event['event_id']:
                raise Invalid('Filename and event ID differ.')
            events.append(event)
        validate_sequence(events)
        return sorted(events, key=lambda e:(e['recorded_at'], e['event_id']))

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = self.root / '.write-lock'
        try:
            lock.mkdir(mode=0o700)
        except FileExistsError:
            raise Invalid('Journal is locked. Check for an active writer before removing a stale .write-lock.') from None
        try:
            yield
        finally:
            lock.rmdir()

    def append(self, feature, kind, summary, *, data=None, occurred_at=None, timing='unknown',
               actor='assistant', source='assistant_note', evidence=(), retrospective=False, import_key=None):
        event_id = str(uuid.uuid5(EVENT_NAMESPACE, feature + ':' + import_key) if import_key else uuid.uuid4())
        event = validate(dict(schema=SCHEMA, event_id=event_id, feature_id=feature, kind=kind,
            recorded_at=timestamp(self.clock()).isoformat(),
            occurred_at=timestamp(occurred_at).isoformat() if occurred_at else None,
            timing=timing, actor=actor, source=source, summary=summary,
            evidence=list(evidence), data=data or {}, retrospective=retrospective))
        with self.locked():
            events = self.read()
            previous = next((e for e in events if e['event_id'] == event_id), None)
            if previous:
                # Reimported evidence has a new journal receipt time, not a new event.
                if {k:v for k,v in previous.items() if k != 'recorded_at'} != {k:v for k,v in event.items() if k != 'recorded_at'}:
                    raise Invalid('Import ID already exists with different content; add an explicit correction.')
                return previous
            if kind == 'work_started':
                current = active(events)
                ended = {e['data']['session_id'] for e in current if e['feature_id']==feature and e['kind']=='work_stopped'}
                if any(e['feature_id']==feature and e['kind']=='work_started' and
                       e['data']['phase']==event['data']['phase'] and e['data']['session_id'] not in ended for e in current):
                    raise Invalid('This phase already has an open session. Close it, with unknown end if necessary.')
            validate_sequence([*events, event])
            folder = self.root / 'events'
            folder.mkdir(exist_ok=True, mode=0o700)
            destination = folder / (event_id + '.json')
            if destination.exists() or destination.is_symlink():
                raise Invalid('Refusing to overwrite an event.')
            fd, temporary = tempfile.mkstemp(prefix='.event-', dir=folder)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(json.dumps(event, ensure_ascii=False, indent=2)+'\n')
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, destination)  # Exclusive journal lock; never an existing event.
            finally:
                Path(temporary).unlink(missing_ok=True)
        return event

    def start(self, feature, phase, summary, coverage='complete', capture=None, at=None, model=None):
        when = at or self.clock()
        source, timing, evidence = ('human_report', 'reported_exact', []) if at else ('local_clock', 'observed', [])
        if capture is not None:
            when = capture['recorded_at']
            source, timing, evidence = 'clock_checkpoint', 'observed', ['sha256:'+digest(capture)]
        return self.append(feature, 'work_started', summary, occurred_at=when, timing=timing,
            source=source, actor='human' if phase=='human_work' else 'assistant', evidence=evidence,
            data={'session_id':str(uuid.uuid4()), 'phase':phase, 'coverage':coverage, 'model_label':model})

    def stop(self, feature, session, summary, at=None, unknown=False):
        starts = [e for e in active(self.read()) if e['feature_id']==feature and e['kind']=='work_started'
                  and e['data']['session_id']==session]
        if len(starts) != 1:
            raise Invalid('Unknown work session.')
        human = starts[0]['data']['phase']=='human_work'
        return self.append(feature, 'work_stopped', summary, data={'session_id':session},
            occurred_at=None if unknown else at or self.clock(),
            timing='unknown' if unknown else 'reported_exact' if at else 'observed',
            source='human_report' if at or human or unknown else 'local_clock',
            actor='human' if human else 'assistant')

    def import_receipt(self, feature, receipt, retrospective=False):
        if not isinstance(receipt, dict) or receipt.get('schema') != 1 or receipt.get('target') not in {'laptop','aws','staging'}:
            raise Invalid('Unsupported controller receipt.')
        status, start, end = receipt.get('status'), receipt.get('started'), receipt.get('finished')
        if start: timestamp(start)
        if end: timestamp(end)
        if start and end and timestamp(end)<timestamp(start):
            raise Invalid('Receipt finish precedes start.')
        if receipt.get('previous') is not None and not COMMIT.fullmatch(str(receipt['previous'])):
            raise Invalid('Invalid previous commit in receipt.')
        # Whitelist metadata: never copy raw stdout, credentials, environment or log paths.
        data = {'target':receipt['target'], 'outcome':status, 'commit':receipt.get('commit'),
                'previous':receipt.get('previous'), 'started_at':start, 'source_sha256':digest(receipt),
                'duration_seconds':(timestamp(end)-timestamp(start)).total_seconds() if start and end else None}
        if receipt.get('operation'):
            data['operation'] = text(receipt['operation'], 100)
        return self.append(feature, 'installation_finished', 'Controller outcome: '+str(status),
            occurred_at=end, timing='observed' if end else 'unknown', actor='automation',
            source='controller_receipt', evidence=['sha256:'+digest(receipt)], data=data,
            retrospective=retrospective, import_key='receipt:'+digest(receipt))

    def import_workflow(self, feature, run, repository, jobs=None, retrospective=False):
        if not isinstance(run, dict) or not isinstance(run.get('repository'), dict) or \
                run['repository'].get('full_name') != repository or run.get('status')!='completed':
            raise Invalid('Workflow must be completed and belong to the expected repository.')
        paths = {'.github/workflows/laptop.yml':'laptop', '.github/workflows/aws.yml':'aws'}
        path = run.get('path', '').split('@')[0]
        if path not in paths or not isinstance(run.get('id'), int) or not isinstance(run.get('run_attempt'), int):
            raise Invalid('Unsupported deployment workflow metadata.')
        if run.get('conclusion') not in {'success','failure','neutral','cancelled','skipped','timed_out',
                                         'action_required','stale','startup_failure'}:
            raise Invalid('Unsupported terminal workflow conclusion.')
        if not COMMIT.fullmatch(str(run.get('head_sha'))):
            raise Invalid('Invalid workflow control commit.')
        if run.get('run_started_at'):
            timestamp(run['run_started_at'])
        end = None
        if jobs is not None:
            if not isinstance(jobs, dict):
                raise Invalid('Expected a jobs object.')
            rows = jobs.get('jobs', [])
            if not isinstance(rows, list) or not rows or jobs.get('total_count') != len(rows):
                raise Invalid('Provide all jobs for this workflow attempt.')
            if any(not isinstance(j, dict) or j.get('run_id') != run['id'] or j.get('run_attempt') != run['run_attempt'] or
                   j.get('status') != 'completed' or not j.get('completed_at') for j in rows):
                raise Invalid('Jobs do not match the completed workflow attempt.')
            end = max(timestamp(j['completed_at']) for j in rows).isoformat()
            if run.get('run_started_at') and timestamp(end) < timestamp(run['run_started_at']):
                raise Invalid('Workflow finish precedes start.')
        data = {'target':paths[path], 'repository':repository, 'run_id':run['id'],
            'attempt':run['run_attempt'], 'conclusion':run.get('conclusion'),
            'control_commit':run.get('head_sha'), 'workflow_started_at':run.get('run_started_at'),
            'source_sha256':digest({'run':run, 'jobs':jobs})}
        return self.append(feature, 'workflow_finished', 'Deployment workflow: '+str(run.get('conclusion')),
            occurred_at=end, timing='observed' if end else 'unknown', actor='automation',
            source='github_workflow', evidence=[f'https://github.com/{repository}/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}'],
            data=data, retrospective=retrospective,
            import_key=f'workflow:{repository}:{run["id"]}:{run["run_attempt"]}')


def union_seconds(intervals):
    end, total = None, 0.0
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += (stop-start).total_seconds()
        elif stop > end:
            total += (stop-end).total_seconds()
        end = stop if end is None else max(end, stop)
    return round(total, 6)


def exact_time(event):
    return timestamp(event['occurred_at']) if event['timing'] in {'observed','reported_exact'} else None


def describe(events):
    current = active(events)
    features, all_intervals = [], {p:[] for p in PHASES}
    for request in (e for e in current if e['kind']=='request'):
        feature = request['feature_id']
        rows = [e for e in current if e['feature_id']==feature]
        stops = {e['data']['session_id']:e for e in rows if e['kind']=='work_stopped'}
        sessions, intervals = [], {p:[] for p in PHASES}
        for start in (e for e in rows if e['kind']=='work_started'):
            stop = stops.get(start['data']['session_id'])
            begin, finish = exact_time(start), exact_time(stop) if stop else None
            seconds = (finish-begin).total_seconds() if begin and finish else None
            if seconds is not None:
                pair = (begin, finish)
                intervals[start['data']['phase']].append(pair)
                all_intervals[start['data']['phase']].append(pair)
            sessions.append({'session_id':start['data']['session_id'], 'phase':start['data']['phase'],
                'coverage':start['data']['coverage'], 'started_at':start['occurred_at'],
                'stopped_at':stop['occurred_at'] if stop else None, 'seconds':seconds,
                'status':'open' if stop is None else 'measured' if seconds is not None else 'unknown_end'})
        ready = [e for e in rows if e['kind']=='implementation_ready' and exact_time(e)]
        origin = exact_time(request)
        def turnaround(endpoints):
            end = min((exact_time(e) for e in endpoints), default=None)
            return (end-origin).total_seconds() if origin and end and end >= origin else None
        closed = [e for e in rows if e['kind']=='feature_closed']
        delivery = {}
        for target in ('laptop','aws','staging','tooling'):
            for milestone, kind in [('install','installation_finished'),('acceptance','acceptance')]:
                matching = [e for e in rows if e['kind']==kind and e['data']['target']==target and exact_time(e)
                            and (kind!='installation_finished' or e['data']['outcome']=='installed')]
                delivery[f'request_to_first_{target}_{milestone}_seconds'] = turnaround(matching)
        features.append({'feature_id':feature, 'title':request['data']['title'],
            'category':request['data']['category'], 'status':closed[-1]['data']['outcome'] if closed else 'open',
            'request_time_precision':request['timing'], 'request_recorded_at':request['recorded_at'],
            'retrospective_events':sum(e['retrospective'] for e in rows),
            'milestones':[e['event_id'] for e in rows if e['kind'] in MILESTONES],
            'metrics':{'request_to_first_ready_seconds':turnaround(ready),
                **delivery,
                'elapsed_seconds':{p:union_seconds(intervals[p]) for p in sorted(PHASES)},
                'open_sessions':sum(s['status']=='open' for s in sessions),
                'unknown_ended_sessions':sum(s['status']=='unknown_end' for s in sessions),
                'partial_sessions':sum(s['coverage']=='partial' for s in sessions),
                'revision_requests':sum(e['kind']=='revision_requested' for e in rows),
                'unsuccessful_installations':sum(e['kind']=='installation_finished' and
                    e['data']['outcome'] not in {'installed','prepared'} for e in rows),
                'unsuccessful_workflows':sum(e['kind']=='workflow_finished' and
                    e['data']['conclusion']!='success' for e in rows)}, 'sessions':sessions})
    return {'features':features, 'feature_count':len(features),
        'open_feature_count':sum(f['status']=='open' for f in features),
        'voided_event_count':len({e['data']['event_id'] for e in events if e['kind']=='void'}),
        'global_elapsed_seconds':{p:union_seconds(all_intervals[p]) for p in sorted(PHASES)},
        'timing_note':TIMING_NOTE,
        'interpretation':'Zero totals mean no measured closed intervals, not proof of zero effort. '
            'Feature totals can overlap each other; global totals union intervals across features. '
            'Timing precision and evidence source remain available in the original events. '
            'Turnaround needs exact endpoints; installation and functional acceptance are separate.'}


def csv_safe(value):
    value = str(value)
    return "'"+value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t','\r','\n')) else value


def md(value):
    return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','\\|').replace('\n',' ')


def export(journal, output):
    events = journal.read()
    report = describe(events)
    output = Path(output)
    if output.resolve() == (journal.root/'events').resolve():
        raise Invalid('Do not write derived exports into the canonical events directory.')
    output.mkdir(parents=True, exist_ok=True)
    dataset = {'schema':SCHEMA, 'exported_at':journal.clock(), 'summary':report, 'events':events}
    (output/'development-log.json').write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (output/'development-events.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer = csv.writer(stream)
        columns = ['event_id','feature_id','kind','recorded_at','occurred_at','timing','actor','source',
                   'retrospective','summary','evidence','data']
        writer.writerow(columns)
        for event in events:
            writer.writerow([csv_safe(canonical(event[k]) if k in {'evidence','data'} else
                '' if event[k] is None else event[k]) for k in columns])
    lines = ['# Development study journal', '', 'All timestamps are UTC. '+TIMING_NOTE, '', report['interpretation'], '',
             '| Feature | Status | Response minutes recorded | Coverage | Revisions |', '| --- | --- | ---: | --- | ---: |']
    for feature in report['features']:
        metrics=feature['metrics']
        coverage=f'{metrics["partial_sessions"]} partial; {metrics["open_sessions"]} open; {metrics["unknown_ended_sessions"]} unknown-ended sessions'
        lines.append(f'| {md(feature["feature_id"])} — {md(feature["title"])} | {feature["status"]} | '
            f'{metrics["elapsed_seconds"]["assistant_response"]/60:.2f} | {coverage} | {metrics["revision_requests"]} |')
    voided = {e['data']['event_id'] for e in events if e['kind']=='void'}
    for feature in report['features']:
        lines += ['', '## '+md(feature['feature_id'])+' — '+md(feature['title']), '',
                  '| Event | Occurred | Recorded | Source | Note |', '| --- | --- | --- | --- | --- |']
        for e in events:
            if e['feature_id']!=feature['feature_id']: continue
            kind=e['kind']+(' (voided)' if e['event_id'] in voided else '')
            occurred=(e['occurred_at'] or 'unknown')+' ('+e['timing']+')'
            details = e['summary'] + (' Evidence: '+', '.join(e['evidence']) if e['evidence'] else '')
            lines.append('| '+' | '.join(md(x) for x in [kind,occurred,e['recorded_at'],e['source'],details])+' |')
    (output/'development-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dataset


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True, help='Private journal directory')
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('new', help='Record a feature request; request time is unknown by default')
    new.add_argument('--feature', required=True); new.add_argument('--title', required=True)
    new.add_argument('--category', choices=['feature','bugfix','research','tooling','documentation'], required=True)
    event = sub.add_parser('event', help='Append an attributed milestone or note')
    event.add_argument('--feature', required=True); event.add_argument('--kind', choices=sorted(MILESTONES), required=True)
    event.add_argument('--data', default='{}', help='JSON object, e.g. target, commit or specification status')
    for command in [new,event]:
        command.add_argument('--summary', required=True); command.add_argument('--at')
        command.add_argument('--timing', choices=sorted(TIMINGS), default='unknown')
        command.add_argument('--actor', choices=['assistant','human','automation'], default='human' if command==new else 'assistant')
        command.add_argument('--evidence', action='append', default=[])
        command.add_argument('--retrospective', action='store_true')
    start = sub.add_parser('start', help='Start an instrumented response, human-work or tool interval')
    start.add_argument('--feature', required=True); start.add_argument('--phase', choices=sorted(PHASES), required=True)
    start.add_argument('--coverage', choices=['complete','partial'], default='complete')
    start.add_argument('--summary', required=True); start.add_argument('--model')
    when = start.add_mutually_exclusive_group(); when.add_argument('--at'); when.add_argument('--clock-file', type=Path)
    stop = sub.add_parser('stop', help='Close a work interval without counting interruptions as work')
    stop.add_argument('--feature', required=True); stop.add_argument('--session', required=True)
    stop.add_argument('--summary', required=True)
    when = stop.add_mutually_exclusive_group(); when.add_argument('--at'); when.add_argument('--unknown-end', action='store_true')
    void = sub.add_parser('void', help='Append an explained correction; original event remains')
    void.add_argument('--event', required=True); void.add_argument('--reason', required=True)
    receipt = sub.add_parser('import-receipt'); workflow = sub.add_parser('import-workflow')
    for command in [receipt,workflow]:
        command.add_argument('--feature', required=True); command.add_argument('--file', required=True, type=Path)
        command.add_argument('--retrospective', action='store_true')
    workflow.add_argument('--repository', required=True); workflow.add_argument('--jobs', type=Path)
    out = sub.add_parser('export'); out.add_argument('--output', required=True, type=Path)
    sub.add_parser('summary'); sub.add_parser('check')
    args=parser.parse_args(argv)
    journal=Journal(args.store)
    load=lambda path:json.loads(path.read_text(encoding='utf-8'))
    try:
        if args.command in {'new','event'}:
            kind='request' if args.command=='new' else args.kind
            data={'title':args.title,'category':args.category} if args.command=='new' else json.loads(args.data)
            result=journal.append(args.feature,kind,args.summary,data=data,occurred_at=args.at,timing=args.timing,
                actor=args.actor,source='human_report' if args.actor=='human' else 'assistant_note',
                evidence=args.evidence,retrospective=args.retrospective)
        elif args.command=='start':
            result=journal.start(args.feature,args.phase,args.summary,args.coverage,
                capture=load(args.clock_file) if args.clock_file else None,at=args.at,model=args.model)
        elif args.command=='stop':
            result=journal.stop(args.feature,args.session,args.summary,at=args.at,unknown=args.unknown_end)
        elif args.command=='void':
            old=next((e for e in journal.read() if e['event_id']==args.event),None)
            if old is None: raise Invalid('Unknown event ID.')
            result=journal.append(old['feature_id'],'void',args.reason,data={'event_id':args.event},
                                  occurred_at=journal.clock(),timing='observed')
        elif args.command=='import-receipt':
            result=journal.import_receipt(args.feature,load(args.file),args.retrospective)
        elif args.command=='import-workflow':
            result=journal.import_workflow(args.feature,load(args.file),args.repository,
                jobs=load(args.jobs) if args.jobs else None,retrospective=args.retrospective)
        elif args.command=='export':
            result=export(journal,args.output)['summary']
        elif args.command=='summary':
            result=describe(journal.read())
        else:
            result={'valid':True,'event_count':len(journal.read())}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (Invalid, OSError, json.JSONDecodeError, KeyError) as exc:
        parser.exit(1, f'Stopped: {exc}\n')


if __name__=='__main__':
    raise SystemExit(cli())
