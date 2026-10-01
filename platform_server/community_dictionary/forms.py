from django import forms

from .models import Dictionary, Entry, Partnership, Request
from .storage import prepare_upload
from .voices import VOICE_CHOICES


class DictionaryForm(forms.ModelForm):
    photo_ai_enabled = forms.BooleanField(required=False, initial=True, label='Enable Learn from a photo (OpenAI)', help_text='Members can choose to send a photo and the language names to OpenAI. Each request requires confirmation and incurs API costs. Uncheck if your community does not permit this processing.')
    tts_enabled = forms.BooleanField(required=False, initial=True, label='Enable saved spoken audio (OpenAI)', help_text='Members can generate synthetic audio from accepted words in supported languages, with confirmation and API costs. Human microphone recording works whether this is enabled or not.')

    class Meta:
        model = Dictionary
        fields = ['name', 'language', 'explanation_language', 'photo_ai_enabled', 'tts_enabled']
        labels = {'language': 'Language we are collecting', 'explanation_language': 'Language for explanations (optional)'}

    def clean(self):
        data = super().clean()
        if data.get('tts_enabled'):
            from .tts import language_code
            if not language_code(data.get('language', '')):
                self.add_error('tts_enabled', 'Saved TTS is not configured for this language. Keep using human recordings.')
        return data


class DictionarySettingsForm(DictionaryForm):
    class Meta(DictionaryForm.Meta):
        fields = ['name', 'language', 'explanation_language', 'text_direction', 'photo_ai_enabled', 'tts_enabled']


class PhotoStudyForm(forms.Form):
    photo = forms.FileField(label='Take or choose a photo', widget=forms.FileInput(attrs={'accept': 'image/*', 'capture': 'environment'}))
    ai_consent = forms.BooleanField(label='I have permission to send this photo to OpenAI for this analysis, at the cost shown above.')

    def clean_photo(self):
        return prepare_upload(self.cleaned_data['photo'], 'image')

    def __init__(self, *args, existing_image=False, **kwargs):
        super().__init__(*args, **kwargs)
        if existing_image:
            self.fields.pop('photo')
            self.fields['base_version'] = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class PhotoSaveForm(forms.Form):
    word = forms.CharField(max_length=255)
    meaning = forms.CharField(max_length=3000, required=False, label='Meaning or translation')
    consent = forms.BooleanField(label='I have permission to share this photo with the dictionary.')
    publish_now = forms.BooleanField(required=False, label='Accept this entry now (editors only)')


class AudioGenerateForm(forms.Form):
    source_text_id = forms.IntegerField(widget=forms.HiddenInput)
    source_text_version = forms.IntegerField(widget=forms.HiddenInput)
    voice = forms.ChoiceField(choices=VOICE_CHOICES, help_text='Your selection is remembered for this dictionary. Generate a preview to hear it before saving. Choosing another voice and generating again is a new paid request.')
    ai_consent = forms.BooleanField(label='I have permission to send this wording and language to OpenAI to generate audio, at the cost shown above.')


class AudioSaveForm(forms.Form):
    consent = forms.BooleanField(label='I have listened to this synthetic recording and have permission to share it with the dictionary.')
    publish_now = forms.BooleanField(required=False, label='Accept this recording now (editors only)')


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


class WordChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, entry):
        meaning = ' '.join(entry.meaning.split())
        return f'{entry.word} — {meaning[:90]}' if meaning else entry.word


class LinkWordForm(forms.Form):
    word_entry = WordChoiceField(queryset=Entry.objects.none(), label='Existing word or phrase', empty_label='Choose a word…')

    def __init__(self, *args, dictionary, source_entry_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['word_entry'].queryset = dictionary.entries.exclude(word='').exclude(pk=source_entry_id).order_by('word', 'pk')


class EntryAudioForm(UploadForm):
    label = forms.CharField(max_length=200, required=False, label='About this recording (optional)')
    publish_now = forms.BooleanField(required=False)

    def clean(self):
        data = super().clean()
        if not data.get('audio'):
            self.add_error('audio', 'Record or choose an audio file before saving.')
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
