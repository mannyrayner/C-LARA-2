"""Small dictionary records independent of the compilation pipeline."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Dictionary(models.Model):
    name = models.CharField(max_length=160)
    language = models.CharField(max_length=80)
    explanation_language = models.CharField(max_length=80, blank=True)
    text_direction = models.CharField(max_length=4, choices=[('auto', 'Automatic'), ('ltr', 'Left to right'), ('rtl', 'Right to left')], default='auto')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name


class Membership(models.Model):
    ROLES = [('member', 'Member'), ('editor', 'Editor')]
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=ROLES, default='member')
    accepted = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dictionary', 'user'], name='cd_unique_member')]


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

    class Meta:
        ordering = ['-created_at', '-pk']

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
    STATUSES = [('pending', 'Awaiting review'), ('accepted', 'Accepted'), ('rejected', 'Changes requested'), ('withdrawn', 'Withdrawn'), ('removed', 'Removed')]
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
    file_path = models.CharField(max_length=200, blank=True)
    mime_type = models.CharField(max_length=80, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    request = models.ForeignKey(Request, null=True, blank=True, on_delete=models.SET_NULL, related_name='responses')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-pk']


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
