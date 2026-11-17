"""Only the controls for the chosen starting route are validated."""
from django import forms
from django.utils.translation import gettext_lazy as _
from .localisation import language_label
from .storage import prepare_upload

STYLES = [
    ('photo', _('Photorealistic'), 'Photorealistic photography, natural lighting and a clear composition.'),
    ('illustration', _('Simple colour illustration'), 'Simple colour illustration, clear shapes and an uncluttered background.'),
    ('cartoon', _('Cartoon'), 'Friendly cartoon illustration, clear outlines and expressive shapes.'),
    ('watercolour', _('Watercolour'), 'Watercolour painting, soft colours and a simple background.'),
]


class WordStartForm(forms.Form):
    start_with = forms.ChoiceField(required=False, choices=[('picture', _('Start with a picture')),
        ('words', _('Start with words'))], widget=forms.RadioSelect)
    words_mode = forms.ChoiceField(required=False, label=_('How would you like to enter your words?'),
        choices=[('text', _('Type')), ('voice', _('Speak'))], widget=forms.RadioSelect)
    words_language = forms.ChoiceField(required=False, label=_('Language I am using'))
    words = forms.CharField(required=False, max_length=255, label=_('What I want to say'),
        widget=forms.Textarea(attrs={'rows': 3, 'dir': 'auto', 'spellcheck': 'true'}))
    audio = forms.FileField(required=False)
    picture_style = forms.ChoiceField(required=False, label=_('Picture style'))
    style_name = forms.CharField(required=False, max_length=60, label=_('Style name'))
    style_description = forms.CharField(required=False, max_length=2000, label=_('Style description'),
        widget=forms.Textarea(attrs={'rows': 3}))
    words_permission = forms.BooleanField(required=False, label=_(
        'I agree to send my words, recording if used, and style description to OpenAI, generate a picture, and pay the estimated costs shown here.'))
    words_quote = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, dictionary, choices, existing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.dictionary, self.choices, self.existing = dictionary, choices, existing
        self.fields['words_language'].choices = list(dict.fromkeys((x, language_label(x)) for x in [
            dictionary.language, dictionary.explanation_language or 'English']))
        self.fields['picture_style'].choices = [(k, label) for k, label, _description in STYLES] + [
            (k, v['name']) for k, v in choices.get('styles', {}).items()] + [('custom', _('Describe another style…'))]
        # Hidden controls from the other route must not validate or enter a request.
        if self.is_bound:
            selected = self.data.get('start_with', 'picture')
            used = {'start_with'}
            if selected == 'words' and not existing:
                used |= {'words_mode', 'words_language', 'picture_style', 'words_permission', 'words_quote'}
                used.add('audio' if self.data.get('words_mode') == 'voice' else 'words')
                if self.data.get('picture_style') == 'custom': used |= {'style_name', 'style_description'}
            self.data, self.files = self.data.copy(), self.files.copy()
            for key in set(self.fields) - used:
                self.data.pop(key, None)
                self.files.pop(key, None)

    def clean(self):
        data = super().clean()
        if data.get('start_with') != 'words': return data
        if self.existing:
            raise forms.ValidationError(_('Start with a picture when using an existing picture.'))
        if not self.dictionary.image_generation_enabled:
            raise forms.ValidationError(_('The owner can enable AI picture generation in Settings.'))
        for key in ['words_mode', 'words_language', 'picture_style', 'words_permission']:
            if not data.get(key) and key not in self.errors: self.add_error(key, _('This field is required.'))
        if data.get('words_mode') == 'voice':
            if data.get('audio'): data['prepared_audio'] = prepare_upload(data['audio'], 'audio')
            else: self.add_error('audio', _('Record or upload your description.'))
        elif not data.get('words'):
            self.add_error('words', _('Write a short description first.'))
        style = data.get('picture_style')
        if style == 'custom':
            for key in ['style_name', 'style_description']:
                if not data.get(key): self.add_error(key, _('This field is required.'))
        elif style:
            preset = next(((str(label), description) for key, label, description in STYLES if key == style), None)
            saved = self.choices.get('styles', {}).get(style)
            if preset: data['style_name'], data['style_description'] = preset
            elif saved: data['style_name'], data['style_description'] = saved['name'], saved['description']
        return data
