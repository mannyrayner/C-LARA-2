from django import forms


class ImageGenerateForm(forms.Form):
    style_id = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    policy_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    subject = forms.CharField(max_length=2000, label='What should the picture show?',
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Use your explanation language. Only this description and the shared style description will be sent.')
    ai_consent = forms.BooleanField(label='I have permission to send these descriptions to OpenAI and generate this picture at the cost described above.')

    def __init__(self, *args, style_sample=False, **kwargs):
        super().__init__(*args, **kwargs)
        if style_sample:
            self.fields['style_description'] = forms.CharField(max_length=2000,
                label='Visual style for this dictionary', widget=forms.Textarea(attrs={'rows': 3}),
                help_text='For example: clear watercolour illustrations, warm natural colours, simple backgrounds. Add any community-specific guidance you want.')
            self.fields['subject'].label = 'What should the sample picture show?'
            self.order_fields(['style_id', 'policy_revision', 'style_description', 'subject', 'ai_consent'])


class ImageSaveForm(forms.Form):
    consent = forms.BooleanField(label='I have checked this AI-generated picture and have permission to share it with the dictionary.')
    publish_now = forms.BooleanField(required=False, initial=True, label='Accept this picture now')

    def __init__(self, *args, style_sample=False, **kwargs):
        super().__init__(*args, **kwargs)
        if style_sample:
            self.fields.pop('publish_now')
            self.fields['consent'].label = 'I have checked this sample and approve this style for the dictionary.'
