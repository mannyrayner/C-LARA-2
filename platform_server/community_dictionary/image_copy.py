"""Owner-only image test copies. Source custody and withdrawal remain connected."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from .capture import locks
from .capture_forms import ImageCopyForm
from .models import Contribution, Dictionary, Entry
from .permissions import get_dictionary, require_owner
from .services import Conflict, event, submit_once
from .storage import path_for
from .views import context


def images(dictionary):
    """One copy per original picture, including captures with a new physical file."""
    seen = set()
    for image in Contribution.objects.filter(entry__dictionary=dictionary, entry__archived=False,
            kind='image', status='accepted').exclude(file_path='').select_related('author', 'controlled_by').order_by('pk'):
        root = image
        visited = set()
        while root.shared_from_id and root.pk not in visited:
            visited.add(root.pk)
            root = root.shared_from
        if root.pk not in seen:
            seen.add(root.pk)
            yield image


def create(source, user, name):
    # Caller holds dictionary locks, shared with withdrawal / publication.
    require_owner(user, source)
    originals = list(images(source))
    if not originals:
        raise Conflict('There are no shared images to copy.')
    target = Dictionary.objects.create(owner=user, name=name, language=source.language,
        explanation_language=source.explanation_language, text_direction=source.text_direction,
        photo_ai_enabled=source.photo_ai_enabled, tts_enabled=source.tts_enabled,
        sentence_capture_enabled=source.sentence_capture_enabled,
        image_generation_enabled=False)
    for original in originals:
        if not path_for(original.file_path).is_file():
            raise Conflict('An image file is missing. No copy was created; please check the source dictionary.')
        entry = Entry.objects.create(dictionary=target, created_by=user)
        picture = Contribution.objects.create(entry=entry, kind='image', status='accepted',
            author=original.author, controlled_by=original.controlled_by or original.author,
            shared_from=original, file_path=original.file_path, mime_type=original.mime_type,
            file_size=original.file_size, provenance=original.provenance)
        entry.selected_image = picture
        entry.save(update_fields=['selected_image'])
    event(source,user,'image_only_copy',detail=f'Image-only test dictionary {target.pk}; {len(originals)} images')
    return target


@login_required
def copy_view(request, pk):
    source = get_dictionary(request.user, pk)
    require_owner(request.user, source)
    form = ImageCopyForm(request.POST or None, initial={'name':source.name[:146]+' — images only'})
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                # Take these BEFORE submit_once's single-dictionary lock, so the
                # order remains consistent with withdrawal across dictionaries.
                locks()
                current = get_dictionary(request.user, pk)
                require_owner(request.user,current)
                def make(_paths):
                    target = create(current,request.user,form.cleaned_data['name'])
                    return reverse('community_dictionary:dictionary',args=[target.pk])
                result = submit_once(request,current,'image-only-copy',make)
            return redirect(result)
        except Conflict as exc:
            form.add_error(None,str(exc))
    return render(request,'community_dictionary/image_copy.html',context(request,source,form=form,
        image_count=sum(1 for _ in images(source)),
        submission_id=request.POST.get('submission_id') or context(request)['submission_id']))
