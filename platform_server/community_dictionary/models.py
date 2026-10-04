"""Small dictionary records independent of the compilation pipeline."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .voices import DEFAULT_VOICE, VOICE_CHOICES


class Dictionary(models.Model):
    name = models.CharField(max_length=160)
    language = models.CharField(max_length=80)
    explanation_language = models.CharField(max_length=80, blank=True)
    photo_ai_enabled = models.BooleanField(default=True)
    tts_enabled = models.BooleanField(default=True)
    image_generation_enabled = models.BooleanField(default=False)
    image_generation_revision = models.PositiveIntegerField(default=0)
    image_style = models.ForeignKey('Contribution', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    text_direction = models.CharField(max_length=4, choices=[('auto', 'Automatic'), ('ltr', 'Left to right'), ('rtl', 'Right to left')], default='auto')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    personal = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    collection_source = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='personal_collections')
    membership_policy = models.CharField(max_length=16, default='owner', choices=[('owner', 'Owner manages membership'), ('coordinators', 'Two coordinators approve changes')])
    membership_revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [models.UniqueConstraint(fields=['owner', 'collection_source'], condition=models.Q(personal=True), name='cd_personal_collection')]

    def __str__(self):
        return self.name


class Membership(models.Model):
    ROLES = [('member', 'Member'), ('editor', 'Editor'), ('coordinator', 'Coordinator')]
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=ROLES, default='member')
    accepted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, default='invited', choices=[('invited', 'Invited'), ('active', 'Active'), ('inactive', 'Inactive')])

    def save(self, *args, **kwargs):
        # Keep old integrations that create accepted memberships compatible.
        if self._state.adding and self.accepted and self.status == 'invited':
            self.status = 'active'
        super().save(*args, **kwargs)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dictionary', 'user'], name='cd_unique_member')]


class Participation(models.Model):
    """Voluntary withdrawal is independent of membership and its moderation."""
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='participations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    withdrawn = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dictionary', 'user'], name='cd_unique_participation')]


class WithdrawalHold(models.Model):
    """A contribution stays private until every source withdrawal is restored."""
    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name='holds')
    contribution = models.ForeignKey('Contribution', on_delete=models.CASCADE, related_name='withdrawal_holds')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['participation', 'contribution'], name='cd_unique_withdrawal_hold')]


class Partnership(models.Model):
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='partnerships')
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name


class Partner(models.Model):
    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name='partners')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['partnership', 'user'], name='cd_unique_partner')]


class Entry(models.Model):
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='entries')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    # These fields are the accepted presentation. Proposed text lives in Contribution.
    word = models.CharField(max_length=255, blank=True)
    meaning = models.TextField(blank=True, max_length=3000)
    category = models.CharField(max_length=80, blank=True)
    text_version = models.PositiveIntegerField(default=0)
    current_text = models.ForeignKey('Contribution', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    selected_image = models.ForeignKey('Contribution', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    current_meaning = models.ForeignKey('Contribution', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    current_category = models.ForeignKey('Contribution', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    meaning_version = models.PositiveIntegerField(default=0)
    category_version = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)
    collection_source = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='collection_entries')

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['dictionary', 'collection_source'], condition=models.Q(collection_source__isnull=False), name='cd_collection_entry')]

    @property
    def title(self):
        if self.word:
            return self.word
        proposal = next((c for c in self.contributions.all() if c.kind == 'text' and c.status == 'pending' and c.word), None)
        return proposal.word if proposal else f'Entry {self.pk}'


class Request(models.Model):
    KINDS = [('image', 'Picture'), ('audio', 'Recording')]
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='requests')
    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name='requests')
    kind = models.CharField(max_length=8, choices=KINDS)
    note = models.TextField(blank=True, max_length=2000)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    withdrawn = models.BooleanField(default=False)
    completed_with = models.ForeignKey('Contribution', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-created_at', '-pk']

    @property
    def progress(self):
        if self.withdrawn:
            return 'withdrawn'
        if self.completed_with_id and self.completed_with.status == 'accepted':
            return 'complete'
        if any(c.status == 'pending' for c in self.responses.all() if c.kind == self.kind):
            return 'awaiting'
        return 'open'


class Contribution(models.Model):
    KINDS = [('text', 'Written information'), ('image', 'Picture'), ('audio', 'Recording'), ('note', 'Comment')]
    STATUSES = [('pending', 'Awaiting review'), ('accepted', 'Accepted'), ('rejected', 'Changes requested'), ('withdrawn', 'Withdrawn'), ('removed', 'Removed'), ('superseded', 'Earlier copy')]
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='contributions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=KINDS)
    status = models.CharField(max_length=12, choices=STATUSES, default='pending')
    word = models.CharField(max_length=255, blank=True)
    meaning = models.TextField(blank=True, max_length=3000)
    category = models.CharField(max_length=80, blank=True)
    label = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True, max_length=3000)
    base_version = models.PositiveIntegerField(default=0)
    provenance = models.JSONField(default=dict, blank=True)
    file_path = models.CharField(max_length=200, blank=True)
    mime_type = models.CharField(max_length=80, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    request = models.ForeignKey(Request, null=True, blank=True, on_delete=models.SET_NULL, related_name='responses')
    created_at = models.DateTimeField(default=timezone.now)
    text_field = models.CharField(max_length=10, blank=True, choices=[('word', 'Word or phrase'), ('meaning', 'Translation or explanation'), ('category', 'Category')])
    controlled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='controlled_dictionary_contributions')
    previous_revision = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='later_revisions')
    shared_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='shared_copies')
    withdrawn_from = models.ForeignKey(Entry, null=True, blank=True, on_delete=models.PROTECT, related_name='withdrawn_contributions')
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.controlled_by_id:
            self.controlled_by_id = self.author_id
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at', '-pk']

    @property
    def component_label(self):
        return self.get_text_field_display() if self.kind == 'text' and self.text_field else self.get_kind_display()

    @property
    def text_value(self):
        return getattr(self, self.text_field, '') if self.text_field else self.word


class MembershipDecision(models.Model):
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='membership_decisions')
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    action = models.CharField(max_length=16)
    member = models.ForeignKey(Membership, null=True, blank=True, on_delete=models.PROTECT)
    value = models.CharField(max_length=16, blank=True)
    base_revision = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class ImageWordLink(models.Model):
    """An additional word for one accepted picture; its original word is implicit."""
    image = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='word_links')
    word_entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='picture_links')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['image', 'word_entry'], name='cd_unique_image_word')]

    def clean(self):
        super().clean()
        if not self.image_id or not self.word_entry_id:
            return
        if self.image.kind != 'image' or self.image.status != 'accepted' or not self.image.file_path:
            raise ValidationError('Choose an accepted picture.')
        if self.image.entry.dictionary_id != self.word_entry.dictionary_id:
            raise ValidationError('The picture and word must belong to the same dictionary.')
        if not self.word_entry.word:
            raise ValidationError('Choose an entry with accepted wording.')
        if self.image.entry_id == self.word_entry_id:
            raise ValidationError('The original word is already associated with this picture.')


class Event(models.Model):
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='events')
    entry = models.ForeignKey(Entry, null=True, blank=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    detail = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-pk']


class Submission(models.Model):
    """A committed receipt makes retrying an interrupted POST safe."""
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE)
    scope = models.CharField(max_length=100)
    digest = models.CharField(max_length=64)
    result_url = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(default=timezone.now)


class PhotoStudy(models.Model):
    """Private, short-lived learning attempt; a saved entry has its own media copy."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, default='processing', choices=[
        (s, s) for s in ['processing', 'candidate', 'unclear', 'failed', 'confirmed', 'saved', 'discarded']])
    file_path = models.CharField(max_length=200, blank=True)
    mime_type = models.CharField(max_length=80, default='image/jpeg')
    file_size = models.PositiveIntegerField(default=0)
    language = models.CharField(max_length=80)
    explanation_language = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    result = models.JSONField(default=dict, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    personal_key = models.BooleanField(default=False)
    failure_code = models.CharField(max_length=40, blank=True)
    confirmed_at = models.DateTimeField(null=True)
    saved_entry = models.ForeignKey(Entry, on_delete=models.SET_NULL, null=True, blank=True)
    source_entry = models.ForeignKey(Entry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    source_image_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_text_version = models.PositiveIntegerField(default=0)


class VoicePreference(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE)
    voice = models.CharField(max_length=40, choices=VOICE_CHOICES, default=DEFAULT_VOICE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'dictionary'], name='cd_unique_voice_preference')]


class AudioStudy(models.Model):
    """A private TTS preview; saving copies it into a reviewed contribution."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE)
    entry = models.ForeignKey(Entry, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, default='processing', choices=[
        (s, s) for s in ['processing', 'ready', 'failed', 'saved', 'discarded']])
    source_text = models.CharField(max_length=255)
    source_text_version = models.PositiveIntegerField()
    source_text_id = models.PositiveBigIntegerField()
    source_meaning = models.TextField(blank=True)
    source_meaning_id = models.PositiveBigIntegerField(null=True, blank=True)
    synthesis = models.JSONField(default=dict, blank=True)
    language = models.CharField(max_length=80)
    language_code = models.CharField(max_length=16)
    model = models.CharField(max_length=80)
    voice = models.CharField(max_length=40)
    personal_key = models.BooleanField(default=False)
    file_path = models.CharField(max_length=200, blank=True)
    mime_type = models.CharField(max_length=80, default='audio/wav')
    file_size = models.PositiveIntegerField(default=0)
    duration_seconds = models.FloatField(null=True)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    saved_contribution = models.ForeignKey(Contribution, on_delete=models.SET_NULL, null=True, blank=True)


class ImageStudy(models.Model):
    """A private, single-call image preview; prompts never go in public logs."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE)
    entry = models.ForeignKey(Entry, null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=[('style', 'Style sample'), ('entry', 'Entry picture')])
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, default='processing', choices=[
        (s, s) for s in ['processing', 'ready', 'failed', 'saved', 'discarded']])
    subject = models.CharField(max_length=2000)
    style_description = models.CharField(max_length=2000)
    source_style = models.ForeignKey(Contribution, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    style_baseline_id = models.PositiveBigIntegerField(null=True, blank=True)
    participation_revision = models.PositiveIntegerField(default=0)
    membership_revision = models.PositiveIntegerField(default=0)
    prompt = models.TextField()
    policy_revision = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=80)
    quality = models.CharField(max_length=16, default='high')
    personal_key = models.BooleanField(default=False)
    usage = models.JSONField(default=dict)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    accounted = models.BooleanField(default=False)
    failure_code = models.CharField(max_length=40, blank=True)
    file_path = models.CharField(max_length=200, blank=True)
    mime_type = models.CharField(max_length=80, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    saved_contribution = models.ForeignKey(Contribution, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')


class ContributionDependency(models.Model):
    """Additional source components used by a derived contribution."""
    source = models.ForeignKey(Contribution, on_delete=models.PROTECT, related_name='derived_uses')
    derived = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='source_dependencies')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'derived'], name='cd_unique_dependency')]


class LanguagePort(models.Model):
    source = models.ForeignKey(Dictionary, on_delete=models.PROTECT, related_name='language_ports')
    destination = models.OneToOneField(Dictionary, null=True, blank=True, on_delete=models.PROTECT, related_name='language_port')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    language = models.CharField(max_length=80)
    explanation_language = models.CharField(max_length=80)
    voice = models.CharField(max_length=40, choices=VOICE_CHOICES, default=DEFAULT_VOICE)
    created_at = models.DateTimeField(default=timezone.now)


class PortRun(models.Model):
    """An immutable quote, approved once, with a refundable credit reservation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    port = models.ForeignKey(LanguagePort, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=16, default='estimate')
    source_language = models.CharField(max_length=80)
    source_explanation_language = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    prices = models.JSONField(default=dict)
    category_plan = models.JSONField(default=dict, blank=True)
    payer = models.CharField(max_length=8)
    estimated_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    allowance_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    reserved_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    charged_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    settled = models.BooleanField(default=False)
    skipped = models.PositiveIntegerField(default=0)
    protected = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    queue_error = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


class PortEntryLink(models.Model):
    port = models.ForeignKey(LanguagePort, on_delete=models.CASCADE, related_name='entry_links')
    source = models.ForeignKey(Entry, on_delete=models.PROTECT, related_name='+')
    destination = models.ForeignKey(Entry, on_delete=models.PROTECT, related_name='+')
    source_digest = models.CharField(max_length=64)
    manually_edited = models.BooleanField(default=False)
    destination_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['port', 'source'], name='cd_unique_port_entry')]


class PortItem(models.Model):
    run = models.ForeignKey(PortRun, on_delete=models.CASCADE, related_name='items')
    source_entry = models.ForeignKey(Entry, on_delete=models.PROTECT, related_name='+')
    sources = models.ManyToManyField(Contribution, related_name='port_previews')
    snapshot = models.JSONField(default=dict)
    destination_digest = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, default='waiting', db_index=True)
    phase = models.CharField(max_length=16, blank=True)
    result = models.JSONField(default=dict)
    file_path = models.CharField(max_length=200, blank=True)
    usage = models.JSONField(default=dict)
    translation_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    audio_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    estimated_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    allowance_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    uncertain_cost = models.BooleanField(default=False)
    invalidated = models.BooleanField(default=False)
    message = models.CharField(max_length=300, blank=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['run', 'source_entry'], name='cd_unique_port_item')]
