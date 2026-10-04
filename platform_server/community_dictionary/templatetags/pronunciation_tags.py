from django import template
from community_dictionary.pronunciation import homographs

register = template.Library()


@register.inclusion_tag('community_dictionary/pronunciation_warning.html')
def pronunciation_warning(text, language):
    return {'english_homographs': homographs(text or '', language or '')}
