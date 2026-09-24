"""Private, validated media. Paths never contain user-supplied filenames."""

import io
import uuid
import warnings
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError


def root():
    return Path(settings.COMMUNITY_DICTIONARY_MEDIA_ROOT).resolve()


def path_for(relative):
    result = (root() / relative).resolve()
    if not relative or not result.is_relative_to(root()):
        raise ValidationError('Invalid media path.')
    return result


def delete_file(relative):
    if relative:
        path_for(relative).unlink(missing_ok=True)


def prepare_upload(upload, kind):
    if upload.size > 15 * 1024 * 1024 or upload.size == 0:
        raise ValidationError('Choose a non-empty file smaller than 15 MB.')
    data = upload.read()
    upload.seek(0)
    if kind == 'image':
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as source:
                    if source.format not in {'JPEG', 'PNG', 'WEBP', 'GIF'}:
                        raise ValidationError('Use a JPEG, PNG, WebP or GIF picture.')
                    source.load()
                    picture = ImageOps.exif_transpose(source).convert('RGBA')
                    picture.thumbnail((1600, 1600))
                    background = Image.new('RGB', picture.size, 'white')
                    background.paste(picture, mask=picture.getchannel('A'))
                    out = io.BytesIO()
                    background.save(out, 'JPEG', quality=85)
                    return out.getvalue(), 'image/jpeg', '.jpg'
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValidationError('This picture could not be read. Try a JPEG or PNG photo.')
    # Reject active content and label common browser recording containers accurately.
    if data.startswith(b'RIFF') and data[8:12] == b'WAVE':
        return data, 'audio/wav', '.wav'
    if data.startswith(b'\x1a\x45\xdf\xa3'):
        return data, 'audio/webm', '.webm'
    if data.startswith(b'OggS'):
        return data, 'audio/ogg', '.ogg'
    if len(data) >= 12 and data[4:8] == b'ftyp':
        return data, 'audio/mp4', '.m4a'
    if data.startswith(b'ID3') or (len(data) > 2 and data[0] == 255 and data[1] & 224 == 224):
        return data, 'audio/mpeg', '.mp3'
    raise ValidationError('Use a recording in WAV, WebM, Ogg, M4A or MP3 format.')


def write_upload(prepared, dictionary_id, created_paths):
    data, mime, suffix = prepared
    relative = f'{dictionary_id}/{uuid.uuid4().hex}{suffix}'
    destination = path_for(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        created_paths.append(relative)
        stream.write(data)
    return {'file_path': relative, 'mime_type': mime, 'file_size': len(data)}
