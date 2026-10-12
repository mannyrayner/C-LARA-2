"""One-click approval of the exact, previously displayed scope and cost."""
import hashlib
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import workflow, batch_descriptions, port_vocabulary, porting
from .discovery_views import DiscoveryForm
from .models import Dictionary, PortRun
from .permissions import get_dictionary, require_owner
from .services import Conflict, event
from .views import fail


@never_cache
@login_required
@require_POST
def start(request, pk):
    try:
        token = request.POST.get('approval', '')
        payload = signing.loads(token, salt=workflow.SALT, max_age=workflow.MAX_AGE)
        if payload['user'] != request.user.pk or payload['dictionary'] != pk or payload['stage'] not in {'descriptions', 'vocabulary', 'sentences'}:
            raise signing.BadSignature
        run_id = uuid.UUID(payload['id'])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return fail(request, 'This suggestion expired or changed. Reload the dictionary to see a fresh estimate.', 409)
    try:
        with transaction.atomic():
            porting.locks()
            dictionary = get_dictionary(request.user, pk)
            require_owner(request.user, dictionary)
            receipt = hashlib.sha256(token.encode()).hexdigest()
            previous = PortRun.objects.filter(pk=run_id, port__user=request.user).first()
            if previous:
                if previous.options.get('workflow_approval') != receipt:
                    raise Conflict('This approval belongs to another operation. Reload the dictionary.')
                return redirect(workflow.run_url(previous))
            current = workflow.suggestion(request.user, dictionary)
            if (not current or current['kind'] != payload['stage'] or
                    current.get('port_id') != payload['port']):
                raise Conflict('The next step changed. Reload the dictionary before starting.')
            port = workflow.batch_port(request.user, dictionary) if payload['stage'] == 'descriptions' else get_object_or_404(
                workflow.related_ports(request.user, dictionary) if payload['stage'] == 'sentences' else workflow.ports_for(request.user, dictionary), pk=payload['port'])
            if payload['stage'] == 'descriptions':
                run = batch_descriptions.quote(request.user, dictionary, run_id, voice=port.voice)
            elif payload['stage'] == 'sentences':
                run = porting.quote(request.user, port.source, {}, run_id, port=port, sentence_updates=True)
            else:
                run = port_vocabulary.quote(request.user, port, run_id)
            if workflow.run_fingerprint(run) != payload['fingerprint']:
                raise Conflict('The pictures, wording, voice, model, prices or payment account changed. Reload for a fresh estimate; nothing was started.')
            run.options['workflow_approval'] = receipt
            run.save(update_fields=['options'])
            porting.approve(request.user, run.pk)
            event(dictionary, request.user, 'workflow_approved', detail=f'{run.stage} {run.pk}; displayed scope, cost and provider permission confirmed')
    except Conflict as exc:
        return fail(request, exc, 409)
    return redirect(workflow.run_url(run))


@never_cache
@login_required
@require_POST
@transaction.atomic
def settings(request, pk):
    dictionary = get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    require_owner(request.user, dictionary)
    form = DiscoveryForm(request.POST)
    action = request.POST.get('action')
    if not form.is_valid() or action not in {'enable', 'disable'}:
        return fail(request, 'Reload Settings and choose whether to show workflow suggestions.')
    enabled = action == 'enable'
    revision = form.cleaned_data['revision']
    if dictionary.show_workflow_suggestions == enabled and revision == dictionary.workflow_suggestions_revision - 1:
        return redirect('community_dictionary:settings', pk=pk)
    if revision != dictionary.workflow_suggestions_revision:
        return fail(request, 'This preference changed. Reload Settings.', 409)
    if enabled != dictionary.show_workflow_suggestions:
        dictionary.show_workflow_suggestions = enabled
        dictionary.workflow_suggestions_revision += 1
        dictionary.save(update_fields=['show_workflow_suggestions', 'workflow_suggestions_revision'])
    messages.success(request, 'Workflow suggestions are on.' if enabled else 'Workflow suggestions are off. The existing controls remain available in Settings.')
    return redirect('community_dictionary:settings', pk=pk)
