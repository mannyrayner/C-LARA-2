from django import forms
from .storage import prepare_upload
from .voices import VOICE_CHOICES
from .capture_vocabulary import MAX_EDITED_WORDS, aligned_surface

MODES = [('text', 'Type'), ('voice', 'Speak'), ('ai', 'Suggest a description')]


class DescriptionModeForm(forms.Form):
    input_mode = forms.ChoiceField(choices=MODES, label='How would you like to describe it?',
                                  widget=forms.RadioSelect)


class CaptureForm(DescriptionModeForm):
    photo=forms.FileField(required=False,widget=forms.FileInput(attrs={'accept':'image/*'}))
    description=forms.CharField(max_length=1000,required=False,widget=forms.Textarea(attrs={'rows':3,'placeholder':'What would you like to say about this picture?'}))
    input_language=forms.ChoiceField(label='Language I am using')
    audio=forms.FileField(required=False)
    voice=forms.ChoiceField(choices=VOICE_CHOICES,label='AI voice')
    ai_consent=forms.BooleanField(label='I have permission to send this picture, description and dictionary vocabulary to OpenAI and approve the estimated API costs shown here.')
    def __init__(self,*args,dictionary,existing=False,**kwargs):
        # Ignore unused controls before validation. A recovered typed draft or
        # recording must not silently become input to the picture-only route.
        args=list(args)
        data=args[0] if args else kwargs.get('data')
        if data is not None:
            data=data.copy()
            if data.get('input_mode') in {'voice','ai'}:
                data['description']=''
            if args: args[0]=data
            else: kwargs['data']=data
            if data.get('input_mode') != 'voice':
                files=args[1] if len(args)>1 else kwargs.get('files')
                if files is not None:
                    files=files.copy(); files.pop('audio',None)
                    if len(args)>1: args[1]=files
                    else: kwargs['files']=files
        super().__init__(*args,**kwargs)
        self.existing=existing
        self.fields['input_language'].choices=list(dict.fromkeys([
            (dictionary.language,dictionary.language),
            (dictionary.explanation_language or 'English',dictionary.explanation_language or 'English')]))
    def clean(self):
        d=super().clean()
        if not self.existing:
            if not d.get('photo'):
                self.add_error('photo','Take or choose a picture.')
            else:
                d['prepared_photo']=prepare_upload(d['photo'],'image')
        if d.get('input_mode')=='voice':
            if not d.get('audio'):
                self.add_error('audio','Record or upload your description.')
            else:
                d['prepared_audio']=prepare_upload(d['audio'],'audio')
        elif d.get('input_mode')=='text' and not d.get('description'):
            self.add_error('description','Say what you mean by this picture.')
        return d


class VocabularyForm(forms.Form):
    lemma = forms.CharField(label='Word or expression', max_length=100)
    meaning = forms.CharField(label='Translation / meaning', max_length=300)
    surface = forms.CharField(label='As used in the sentence (optional)', max_length=100,
                              required=False, help_text='Use … between separated parts, or leave blank.')


class VocabularyFormSet(forms.BaseFormSet):
    def __init__(self, *args, sentence, **kwargs):
        self.sentence = sentence
        super().__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields['DELETE'].label = 'Remove'

    def clean(self):
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get('DELETE'):
                continue
            identity = tuple(' '.join(data[key].split()).casefold() for key in ('lemma', 'meaning'))
            if identity in seen:
                raise forms.ValidationError('This word and meaning appear twice. Remove one copy.')
            seen.add(identity)
            if data.get('surface') and not aligned_surface(data['surface'], self.sentence):
                form.add_error('surface', 'Copy the form from the sentence, use … for a gap, or leave this blank.')

    def words(self):
        return [{'lemma': f.cleaned_data['lemma'], 'meaning': f.cleaned_data['meaning'],
                 'surface': f.cleaned_data.get('surface', ''), 'existing_id': 0}
                for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE')]


VocabularyForms = forms.formset_factory(VocabularyForm, formset=VocabularyFormSet, extra=1,
    can_delete=True, max_num=MAX_EDITED_WORDS, validate_max=True, absolute_max=MAX_EDITED_WORDS)


IMAGE_COPY_STATUSES = {
    'accepted': ('accepted',), 'pending': ('pending',), 'both': ('accepted', 'pending')}


class ImageCopyForm(forms.Form):
    image_status = forms.ChoiceField(label='Images to copy', initial='both', required=False,
        choices=[('accepted', 'Accepted'), ('pending', 'Awaiting review'), ('both', 'Both')])

    def clean_image_status(self):
        # Old open forms without the new control use the same default.
        return self.cleaned_data['image_status'] or 'both'

    name = forms.CharField(label='Name of the new dictionary', max_length=160)
    permission = forms.BooleanField(label='I have permission to copy these images into a new dictionary.')
