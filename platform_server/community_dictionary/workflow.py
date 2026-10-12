"""Read-only next-step suggestions; paid work starts only through explicit POST."""
from decimal import Decimal
import hashlib
import json
import uuid

from django.core import signing
from django.db.models import Q
from django.http import Http404
from django.urls import reverse

from projects.billing import get_user_balance_usd
from . import batch_descriptions as batch, port_vocabulary as vocabulary, porting, photo_ai, tts, port_ai
from .models import LanguagePort, MembershipRequest
from .permissions import dictionaries_for
from .services import Conflict
from .voices import DEFAULT_VOICE

SALT = 'community-workflow-approval-v1'
MAX_AGE = 3600


def ports_for(user, dictionary):
    return LanguagePort.objects.filter(user=user).filter(
        Q(source=dictionary, is_description_batch=True) | Q(destination=dictionary)
    ).select_related('source', 'destination', 'user').order_by('-created_at')


def batch_port(user, dictionary):
    return LanguagePort.objects.filter(source=dictionary, user=user, is_description_batch=True).first() or LanguagePort(
        source=dictionary, user=user, is_description_batch=True, name=dictionary.name,
        language=dictionary.language, explanation_language=dictionary.explanation_language, voice=DEFAULT_VOICE)


def run_url(run):
    return reverse('community_dictionary:port-run', args=[run.port.source_id, run.pk])


def suggestion(user, dictionary, *, details=False):
    if (not user.is_authenticated or dictionary.owner_id != user.pk or dictionary.hidden or
            not dictionary.show_workflow_suggestions or
            not dictionaries_for(user).filter(pk=dictionary.pk).exists()):
        return None
    count = MembershipRequest.objects.filter(dictionary=dictionary, status='pending').count()
    if count:
        return {'kind': 'requests', 'label': f'{count} membership request' + ('s' if count != 1 else ''),
            'button': 'View requests', 'url': reverse('community_dictionary:membership-requests') + f'?dictionary={dictionary.pk}'}
    ports = []
    for port in ports_for(user, dictionary):
        try:
            porting.authority(port)
        except (Conflict, Http404):
            continue
        ports.append(port)
    # Ready previews can be reviewed while other items finish. A vocabulary run
    # remains 'running' while it waits for this human step; don't call that busy.
    for port in ports:
        for run in port.runs.exclude(status__in=['estimate', 'cancelled']):
            ready = sentence_count = 0
            for item in run.items.filter(status__in=['ready', 'unclear'], invalidated=False, needs_attention=False).select_related('source_entry'):
                item.run = run
                try:
                    porting.current_item(item)
                except (Conflict, Http404):
                    continue
                ready += 1
                sentence_count += run.stage == 'descriptions' or item.source_entry.entry_type == 'sentence'
            if ready:
                words = run.stage == 'vocabulary'
                noun = 'sentence' if sentence_count == ready else 'entry'
                plural = 'sentences' if noun == 'sentence' else 'entries'
                label = (f'Word suggestions for {ready} sentence' + ('s' if ready != 1 else '') + ' ready to review') if words else (
                    f'{ready} {noun if ready == 1 else plural} ready to review')
                button = 'Review word suggestions' if words else ('Review sentences' if noun == 'sentence' else 'Review language results')
                return {'kind': 'review', 'label': label, 'button': button, 'url': run_url(run)}
    for port in ports:
        run = port.runs.filter(status='running').first()
        if run:
            return {'kind': 'processing', 'label': 'Processing…', 'button': 'View progress', 'url': run_url(run)}
    # Finish vocabulary for accepted sentences before describing more pictures.
    for port in ports:
        try:
            vocabulary.authority(port)
        except (Conflict, Http404):
            continue
        entries, _ = vocabulary.candidates(port)
        if entries:
            count = len(entries)
            result = {'kind': 'vocabulary', 'port_id': port.pk,
                'label': 'Word pages ready to create',
                'scope': f'Words and expressions from {count} accepted sentence' + ('s' if count != 1 else ''),
                'button': 'Approve and create word suggestions', 'count': count}
            break
    else:
        port = batch_port(user, dictionary)
        try:
            porting.authority(port)
        except (Conflict, Http404):
            return None
        pictures = batch.candidates(dictionary, port)['pictures']
        if not pictures:
            return None
        count = len(pictures)
        result = {'kind': 'descriptions', 'port_id': port.pk,
            'label': f'{count} picture' + ('s' if count != 1 else '') + ' ready for sentences',
            'scope': 'Accepted pictures and pictures awaiting review, keeping existing words and translations as hints.',
            'button': 'Approve and create sentences', 'count': count}
    result['url'] = reverse('community_dictionary:dictionary', args=[dictionary.pk]) + '#next-step'
    if details:
        try:
            planned = prepare(user, dictionary, result['kind'], port)
            result.update({k: planned[k] for k in ['estimated', 'allowance', 'payer', 'model', 'voice']})
            result['balance'] = get_user_balance_usd(user) if planned['payer'] == 'credits' else None
            result['enough_funds'] = result['balance'] is None or result['balance'] >= planned['allowance']
            result['approval'] = signing.dumps({'user': user.pk, 'dictionary': dictionary.pk,
                'stage': result['kind'], 'port': port.pk, 'id': str(uuid.uuid4()),
                'fingerprint': planned['fingerprint']}, salt=SALT, compress=True)
        except (Conflict, Http404) as exc:
            result['unavailable'] = str(exc) or 'This operation is not currently available.'
    return result


def price_basis(stage, prices):
    result = {**{k: str(v) for k, v in prices.items()}, 'speech_recipe': tts.INSTRUCTIONS_VERSION}
    if stage == 'descriptions':
        result.update(description_recipe=batch.VERSION,
            sentence_speech_recipe=port_ai.speech_version({'entry_type': 'sentence'}))
    else:
        result['vocabulary_recipe'] = vocabulary.VERSION
    return result


def fingerprint(stage, port, model, prices, payer, items):
    rows = []
    for item in items:
        rows.append({'entry': item['source_entry'].pk, 'snapshot': item['snapshot'],
            'estimate': str(item['estimated_usd']), 'allowance': str(item['allowance_usd'])})
    data = [stage, port.source_id, port.target_id, port.language, port.explanation_language,
        port.voice, model, prices, payer, sorted(rows, key=lambda row: (row['entry'], json.dumps(row['snapshot'], sort_keys=True)))]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def prepare(user, dictionary, stage, port):
    model, _, _, prices = photo_ai.configuration(user)
    payer = porting.payer_now(user)
    if stage == 'descriptions':
        porting.authority(port)
        planned = batch.plan(dictionary, port, prices)
    else:
        vocabulary.authority(port)
        planned = vocabulary.plan(port, prices)
    items = planned['items']
    if not items:
        raise Conflict('No new work is ready. Reload the dictionary.')
    return {'estimated': sum((i['estimated_usd'] for i in items), Decimal('0')),
        'allowance': sum((i['allowance_usd'] for i in items), Decimal('0')),
        'model': model, 'voice': port.voice, 'payer': payer,
        'fingerprint': fingerprint(stage, port, model, price_basis(stage, prices), payer, items)}


def run_fingerprint(run):
    items = [{'source_entry': i.source_entry, 'snapshot': i.snapshot,
        'estimated_usd': i.estimated_usd, 'allowance_usd': i.allowance_usd} for i in run.items.select_related('source_entry')]
    return fingerprint(run.stage, run.port, run.model, run.prices, run.payer, items)
