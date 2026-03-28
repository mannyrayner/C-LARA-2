from zoneinfo import available_timezones

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from django.forms import modelformset_factory

from .models import (
    Project,
    Profile,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImageStyle,
)


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProjectForm(forms.ModelForm):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("zh", "Mandarin Chinese"),
        ("hi", "Hindi"),
        ("es", "Spanish"),
        ("it", "Italian"),
        ("pt", "Portuguese"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("ar", "Arabic"),
        ("ru", "Russian"),
    ]

    class Meta:
        model = Project
        fields = [
            "title",
            "input_mode",
            "description",
            "source_text",
            "language",
            "target_language",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "source_text": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"] = forms.ChoiceField(
            choices=self.LANGUAGE_CHOICES,
            initial=self.instance.language if getattr(self.instance, "pk", None) else "en",
            label="Text language",
        )
        self.fields["target_language"] = forms.ChoiceField(
            choices=self.LANGUAGE_CHOICES,
            initial=self.instance.target_language if getattr(self.instance, "pk", None) else "fr",
            label="Glossing language",
        )

    def clean(self):  # type: ignore[override]
        cleaned = super().clean()
        mode = cleaned.get("input_mode")
        description = (cleaned.get("description") or "").strip()
        source_text = (cleaned.get("source_text") or "").strip()

        if mode == Project.INPUT_DESCRIPTION:
            if not description:
                self.add_error("description", "Please provide a description for text generation.")
            cleaned["source_text"] = ""
        elif mode == Project.INPUT_SOURCE:
            if not source_text:
                self.add_error("source_text", "Please provide source text for segmentation.")
            cleaned["description"] = description  # allow optional summary
        else:
            self.add_error("input_mode", "Select how you want to supply text.")

        if description and source_text:
            self.add_error(None, "Please provide either a description or source text, not both.")

        return cleaned


TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(available_timezones())]


class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)

    class Meta:
        model = Profile
        fields = ["timezone"]


class ProjectImageStyleForm(forms.ModelForm):
    class Meta:
        model = ProjectImageStyle
        fields = [
            "style_brief",
            "expanded_style_description",
            "sample_image_prompt",
            "ai_model",
            "sample_image_model",
            "status",
        ]
        widgets = {
            "style_brief": forms.Textarea(attrs={"rows": 3}),
            "expanded_style_description": forms.Textarea(attrs={"rows": 10}),
            "sample_image_prompt": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(
        self,
        *args,
        ai_model_choices: list[str] | None = None,
        image_model_choices: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        model_choices = ai_model_choices or []
        image_choices = image_model_choices or []
        self.fields["ai_model"] = forms.ChoiceField(
            choices=[(model, model) for model in model_choices],
            initial=self.instance.ai_model if getattr(self.instance, "pk", None) else None,
        )
        self.fields["sample_image_model"] = forms.ChoiceField(
            choices=[(model, model) for model in image_choices],
            initial=self.instance.sample_image_model if getattr(self.instance, "pk", None) else None,
        )

    def clean_style_brief(self):
        brief = (self.cleaned_data.get("style_brief") or "").strip()
        if not brief:
            raise forms.ValidationError("Please provide a brief image style description.")
        return brief


class ProjectImageElementForm(forms.ModelForm):
    class Meta:
        model = ProjectImageElement
        fields = [
            "name",
            "element_type",
            "page_refs",
            "why_consistency_matters",
            "expanded_description",
            "expanded_prompt",
            "image_model",
            "image_revised_prompt",
            "is_confirmed",
        ]
        widgets = {
            "why_consistency_matters": forms.Textarea(attrs={"rows": 2}),
            "expanded_description": forms.Textarea(attrs={"rows": 4}),
            "expanded_prompt": forms.Textarea(attrs={"rows": 4}),
            "image_revised_prompt": forms.Textarea(attrs={"rows": 2}),
        }


ProjectImageElementFormSet = modelformset_factory(
    ProjectImageElement,
    form=ProjectImageElementForm,
    can_delete=True,
    extra=0,
)


class ProjectImagePageForm(forms.ModelForm):
    class Meta:
        model = ProjectImagePage
        fields = [
            "page_number",
            "page_text",
            "generation_prompt",
            "image_model",
            "image_revised_prompt",
            "status",
        ]
        widgets = {
            "page_text": forms.Textarea(attrs={"rows": 4}),
            "generation_prompt": forms.Textarea(attrs={"rows": 6}),
            "image_revised_prompt": forms.Textarea(attrs={"rows": 2}),
        }


ProjectImagePageFormSet = modelformset_factory(
    ProjectImagePage,
    form=ProjectImagePageForm,
    can_delete=False,
    extra=0,
)
