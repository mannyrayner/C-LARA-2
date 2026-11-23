"""Schedule only after publication commits; browsing never starts paid work."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Entry


@receiver(post_save, sender=Entry, dispatch_uid='community_lemma_image')
def accepted_word(sender, instance, raw=False, **kwargs):
    if raw or instance.entry_type != 'word' or instance.archived:
        return
    # The first save may still contain no accepted text. Read again after the
    # surrounding publication transaction commits, when media and senses exist.
    from .lemma_images import automatic
    transaction.on_commit(lambda pk=instance.pk: automatic(pk), robust=True)
