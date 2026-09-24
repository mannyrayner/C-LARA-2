from django import forms

from .models import Dictionary, Partnership, Request
from .storage import prepare_upload


class DictionaryForm(forms.ModelForm):
    class Meta:
        model = Dictionary
        fields = ['name', 'language', 'explanation_language']
        labels = {'language': 'Language we are collecting', 'explanation_language': 'Language for explanations (optional)'}


class DictionarySettingsForm(DictionaryForm):
    class Meta(DictionaryForm.Meta):
        fields = DictionaryForm.Meta.fields + ['text_direction']


class UploadForm(forms.Form):
    audio = forms.FileField(required=False)
    consent = forms.BooleanField(required=False, label='I have permission to share these pictures or recordings with this dictionary.')

    def clean(self):
        data = super().clean()
        for field, kind in [('photo', 'image'), ('audio', 'audio')]:
            upload = data.get(field)
            if upload:
                if not data.get('consent'):
                    self.add_error('consent', 'Confirm permission to share your media with the dictionary.')
                try:
                    data['prepared_' + field] = prepare_upload(upload, kind)
                except forms.ValidationError as exc:
                    self.add_error(field, exc)
        return data


class ContributionForm(UploadForm):
    photo = forms.FileField(required=False)
    word = forms.CharField(max_length=255, required=False, label='Word or phrase (optional)')
    meaning = forms.CharField(max_length=3000, required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Meaning or context (optional)')
    category = forms.CharField(max_length=80, required=False, label='Category (optional)')
    label = forms.CharField(max_length=200, required=False, label='About this recording or picture (optional)')
    edit_text = forms.BooleanField(required=False)
    base_version = forms.IntegerField(min_value=0, required=False)
    publish_now = forms.BooleanField(required=False)

    def __init__(self, *args, dictionary=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['meaning'].label = 'Meaning or translation (optional)'
        self.fields['meaning'].widget.attrs.update(rows=2, placeholder='A translation or short explanation')
        self.fields['word'].widget.attrs['dir'] = dictionary.text_direction if dictionary else 'auto'
        if dictionary:
            self.fields['word'].label = f'Word or phrase in {dictionary.language} (optional)'
            if dictionary.explanation_language:
                self.fields['meaning'].label = f'Meaning or translation in {dictionary.explanation_language} (optional)'

    def clean(self):
        data = super().clean()
        if not any(data.get(k) for k in ['photo', 'audio', 'word', 'meaning', 'category', 'edit_text']):
            raise forms.ValidationError('Add a picture, recording or some written information.')
        return data


class NoteForm(UploadForm):
    body = forms.CharField(max_length=3000, required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Comment (optional if you record it)')

    def clean(self):
        data = super().clean()
        if not data.get('body') and not data.get('audio'):
            raise forms.ValidationError('Write or record a comment.')
        return data


class RequestForm(UploadForm):
    partnership = forms.ModelChoiceField(queryset=Partnership.objects.none(), label='Ask this partnership')
    kind = forms.ChoiceField(choices=Request.KINDS, label='What would help?')
    note = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Explain your request (optional)')

    def __init__(self, *args, user, dictionary, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['partnership'].queryset = Partnership.objects.filter(dictionary=dictionary, partners__user=user, partners__accepted=True)
