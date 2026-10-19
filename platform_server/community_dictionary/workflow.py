"""Read-only next-step suggestions; paid work starts only through explicit POST."""
from decimal import Decimal
import hashlib
import json
import uuid

from django.core import signing
from django.db.models import Q
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext as _, ngettext

from projects.billing import get_user_balance_usd
from . import batch_descriptions as batch, port_vocabulary as vocabulary, porting, photo_ai, tts, port_ai
from .models import LanguagePort, MembershipRequest, PortItem
from .permissions import dictionaries_for
from .services import Conflict
from .voices import DEFAULT_VOICE
from .workflow_data import reading

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
    with reading():
        return _suggestion(user, dictionary, details=details)


def _suggestion(user, dictionary, *, details=False):
    if (not user.is_authenticated or dictionary.owner_id != user.pk or dictionary.hidden or
            not dictionary.show_workflow_suggestions or
            not dictionaries_for(user).filter(pk=dictionary.pk).exists()):
        return None
    count = MembershipRequest.objects.filter(dictionary=dictionary, status='pending').count()
    if count:
        return {'kind': 'requests', 'label': ngettext('%(count)s membership request', '%(count)s membership requests', count) % {'count': count},
            'button': _('View requests'), 'url': reverse('community_dictionary:membership-requests') + f'?dictionary={dictionary.pk}'}
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
        for run in port.runs.exclude(status__in=['estimate', 'cancelled']).filter(
                items__status__in=['ready','unclear'], items__invalidated=False,
                items__needs_attention=False).distinct():
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
                sentences = sentence_count == ready
                if words:
                    label = ngettext('Word suggestions for %(count)s sentence ready to review',
                        'Word suggestions for %(count)s sentences ready to review', ready) % {'count': ready}
                elif sentences:
                    label = ngettext('%(count)s sentence ready to review', '%(count)s sentences ready to review', ready) % {'count': ready}
                else:
                    label = ngettext('%(count)s entry ready to review', '%(count)s entries ready to review', ready) % {'count': ready}
                button = _('Review word suggestions') if words else (_('Review sentences') if sentences else _('Review language results'))
                return {'kind': 'review', 'label': label, 'button': button, 'url': run_url(run)}
    for port in ports:
        run = port.runs.filter(status='running').first()
        if run:
            if run.items.filter(status='budget').exists() or run.speech.filter(status='budget').exists():
                return {'kind':'processing','label':_('More allowance needs your approval'),
                    'button':_('Review allowance'),'url':run_url(run)}
            return {'kind': 'processing', 'label': _('Processing…'), 'button': _('View progress'), 'url': run_url(run)}
    # Finish vocabulary for accepted sentences before describing more pictures.
    for port in ports:
        try:
            vocabulary.authority(port)
        except (Conflict, Http404):
            continue
        entries, _skipped = vocabulary.candidates(port)
        if entries:
            count = len(entries)
            result = {'kind': 'vocabulary', 'port_id': port.pk,
                'label': _('Word pages ready to create'),
                'scope': ngettext('Words and expressions from %(count)s accepted sentence',
                    'Words and expressions from %(count)s accepted sentences', count) % {'count': count},
                'button': _('Approve and create word suggestions'), 'count': count}
            break
    else:
        port = batch_port(user, dictionary)
        try:
            porting.authority(port)
        except (Conflict, Http404):
            pictures = []
        else:
            pictures = batch.candidates(dictionary, port)['pictures']
        if not pictures:
            return related_suggestion(user, dictionary, details=details)
        count = len(pictures)
        result = {'kind': 'descriptions', 'port_id': port.pk,
            'label': ngettext('%(count)s picture ready for sentences', '%(count)s pictures ready for sentences', count) % {'count': count},
            'scope': _('Accepted pictures and pictures awaiting review, keeping existing words and translations as hints.'),
            'button': _('Approve and create sentences'), 'count': count}
    return complete_suggestion(user, dictionary, result, port, details=details)


def complete_suggestion(user, dictionary, result, port, *, details):
    result.setdefault('url', reverse('community_dictionary:dictionary', args=[dictionary.pk]) + '#next-step')
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
            result['unavailable'] = _(str(exc)) if str(exc) else _('This operation is not currently available.')
    return result


def price_basis(stage, prices):
    result = {**{k: str(v) for k, v in prices.items()}, 'speech_recipe': tts.INSTRUCTIONS_VERSION}
    if stage == 'descriptions':
        result.update(description_recipe=batch.VERSION,
            sentence_speech_recipe=port_ai.speech_version({'entry_type': 'sentence'}))
    elif stage == 'sentences':
        result['sentence_speech_recipe'] = port_ai.speech_version({'entry_type': 'sentence'})
    else:
        result['vocabulary_recipe'] = vocabulary.VERSION
    return result


def fingerprint(stage, port, model, prices, payer, items, *, category_plan=None):
    rows = []
    for item in items:
        rows.append({'entry': item['source_entry'].pk, 'snapshot': item['snapshot'],
            'estimate': str(item['estimated_usd']), 'allowance': str(item['allowance_usd'])})
        if stage == 'sentences':
            rows[-1]['destination_digest'] = item['destination_digest']
    data = [stage, port.source_id, port.target_id, port.language, port.explanation_language,
        port.voice, model, prices, payer, sorted(rows, key=lambda row: (row['entry'], json.dumps(row['snapshot'], sort_keys=True)))]
    if stage == 'sentences':
        data += [category_plan, port.source.language, port.source.explanation_language]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def prepare(user, dictionary, stage, port):
    model, _key, _personal, prices = photo_ai.configuration(user)
    payer = porting.payer_now(user)
    if stage == 'descriptions':
        porting.authority(port)
        planned = batch.plan(dictionary, port, prices)
    elif stage == 'sentences':
        porting.authority(port)
        planned = porting.plan(port, prices, sentence_updates=True)
    else:
        vocabulary.authority(port)
        planned = vocabulary.plan(port, prices)
    items = planned['items']
    if not items:
        raise Conflict(_('No new work is ready. Reload the dictionary.'))
    return {'estimated': sum((i['estimated_usd'] for i in items), Decimal('0')),
        'allowance': sum((i['allowance_usd'] for i in items), Decimal('0')),
        'model': model, 'voice': port.voice, 'payer': payer,
        'fingerprint': fingerprint(stage, port, model, price_basis(stage, prices), payer, items, category_plan=planned.get('category_plan'))}


def run_fingerprint(run):
    items = [{'source_entry': i.source_entry, 'snapshot': i.snapshot,
        'estimated_usd': i.estimated_usd, 'allowance_usd': i.allowance_usd,
        'destination_digest': i.destination_digest} for i in run.items.select_related('source_entry')]
    return fingerprint(run.stage, run.port, run.model, run.prices, run.payer, items, category_plan=run.category_plan)


def related_ports(user, dictionary):
    """Existing language relationships the current owner can operate at both ends."""
    return (LanguagePort.objects.filter(user=user, is_description_batch=False,is_audio_batch=False,
        source__hidden=False, destination__hidden=False, destination__show_workflow_suggestions=True,
        destination__photo_ai_enabled=True).filter(Q(source=dictionary) | Q(destination=dictionary))
        .select_related('source', 'destination', 'user').order_by('pk'))


def related_suggestion(user, dictionary, *, details=False):
    for port in related_ports(user, dictionary):
        try:
            porting.authority(port)
        except (Conflict, Http404):
            continue
        if not porting.same_language(port.source.language, port.language) and (
                not port.destination.tts_enabled or not tts.language_code(port.language)):
            continue
        destination = port.destination
        label = destination.name
        # Don't offer an update that the existing quote would refuse. The shared
        # progress/review screen also allows stale previews to be discarded.
        run = port.runs.filter(status='running').first()
        if run:
            return {'kind':'related-progress', 'label':_('%(dictionary)s: work in progress') % {'dictionary': label},
                'button':_('View progress'), 'url':run_url(run)}
        item = (PortItem.objects.filter(run__port=port, status__in=['ready','unclear'])
            .select_related('run__port').order_by('pk').first())
        if item:
            return {'kind':'related-review', 'label':_('%(dictionary)s: finish reviewing the previous results') % {'dictionary': label},
                'button':_('Review previous results'), 'url':run_url(item.run)}
        # On the source side, point at unfinished destination vocabulary before
        # offering a new update. Word work itself remains on the destination.
        if dictionary.pk == port.source_id:
            try:
                vocabulary.authority(port)
                pending_words, _skipped = vocabulary.candidates(port)
            except (Conflict, Http404):
                pending_words = []
            if pending_words:
                return {'kind':'related-vocabulary', 'label':_('%(dictionary)s: word pages ready to create') % {'dictionary': label},
                    'button':_('Open language version'),
                    'url':reverse('community_dictionary:dictionary',args=[destination.pk])+'#next-step'}
        planned = porting.plan(port, sentence_updates=True)
        count = len(planned['items'])
        if not count:
            continue
        new, changed = planned['new'], planned['changed']
        new_summary = ngettext('%(count)s new sentence', '%(count)s new sentences', new) % {'count': new} if new else ''
        changed_summary = ngettext('%(count)s changed sentence', '%(count)s changed sentences', changed) % {'count': changed} if changed else ''
        summary = _('%(new)s and %(changed)s') % {'new': new_summary, 'changed': changed_summary} if new and changed else new_summary or changed_summary
        result = {'kind':'sentences', 'port_id':port.pk, 'count':count,
            'label':_('%(dictionary)s: %(summary)s to translate') % {'dictionary': label, 'summary': summary} if dictionary.pk == port.source_id else _('%(summary)s available from %(source)s') % {'summary': summary.capitalize(), 'source': port.source.name},
            'scope':_('Update %(destination)s (%(language)s / %(explanation_language)s) from %(source)s.') % {
                'destination': destination.name, 'language': destination.language,
                'explanation_language': destination.explanation_language, 'source': port.source.name},
            'button':_('Approve and update %(dictionary)s') % {'dictionary': destination.name}, 'destination_name':destination.name,
            'new_count':new, 'changed_count':changed, 'protected_count':planned['protected'],
            'url':reverse('community_dictionary:dictionary',args=[destination.pk])+'#next-step'}
        return complete_suggestion(user, dictionary, result, port, details=details)
    return None
