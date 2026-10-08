from django import forms
from .models import LanguagePort
from .voices import DEFAULT_VOICE, VOICE_CHOICES


class PortForm(forms.ModelForm):
    submission_id = forms.UUIDField(widget=forms.HiddenInput)
    class Meta:
        model = LanguagePort
        fields = ['name','language','explanation_language','voice']
        labels = {'name':'Name for the new dictionary', 'language':'Target language',
                  'explanation_language':'Commenting language', 'voice':'Voice for new recordings'}
        help_texts = {'language':'Leave unchanged to translate only the explanations.',
                      'explanation_language':'Leave unchanged to keep the existing explanations.',
                      'voice':'Used only when the target language changes.'}
    def clean(self):
        data = super().clean()
        from .tts import language_code
        from .porting import same_language
        if data.get('language') and not language_code(data['language']) and not same_language(data['language'],self.source.language):
            self.add_error('language','This first version needs a target language with configured TTS. You can keep the existing target language.')
        return data


class PortApproveForm(forms.Form):
    approve = forms.BooleanField(label='I approve this cost estimate and have permission to send these pictures and texts to OpenAI and reuse them in the new dictionary.')


class PortReviewForm(forms.Form):
    word = forms.CharField(max_length=255,label='Word or phrase')
    meaning = forms.CharField(max_length=3000,required=False,label='Translation or explanation',widget=forms.Textarea(attrs={'rows':2}))
    category = forms.CharField(max_length=80,required=False)
    needs_attention = forms.BooleanField(required=False,label='Keep flagged for attention after saving')
    attention_note = forms.CharField(max_length=500,required=False,label='Note for later (optional)',
                                    widget=forms.Textarea(attrs={'rows':2}))

    def __init__(self,*args,change_target=True,change_explanation=True,entry_type="word",**kwargs):
        super().__init__(*args,**kwargs)
        if entry_type == 'sentence':
            self.fields['word'].label = 'Sentence'
            self.fields['word'].widget = forms.Textarea(attrs={'rows': 3})
        self.fields['word'].disabled = not change_target
        self.fields['meaning'].disabled = not change_explanation
        self.fields['category'].help_text = 'Check the proposed category; you can keep or change it.'


class PortAttentionForm(forms.Form):
    attention_note = forms.CharField(max_length=500,required=False,label='Note for later (optional)',
                                    widget=forms.Textarea(attrs={'rows':2}))
