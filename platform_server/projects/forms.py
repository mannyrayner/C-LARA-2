from zoneinfo import available_timezones
from decimal import Decimal

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
        ("fa", "Persian"),
        ("nl", "Dutch"),
        ("is", "Icelandic"),
        ("non", "Old Norse"),
        ("sk", "Slovak"),
        ("iai", "Iaai"),
        ("dre", "Drehu"),
        ("xkk", "Kok Kaper"),
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


class ClozeExerciseSetForm(forms.Form):
    theme = forms.ChoiceField(
        choices=[
            ("vocabulary", "Vocabulary"),
            ("grammar", "Grammar"),
            ("morphology", "Morphology"),
            ("grammar_morphology", "Grammar/Morphology"),
        ],
        initial="vocabulary",
    )
    item_count = forms.IntegerField(min_value=1, max_value=50, initial=10)
    ai_model = forms.ChoiceField(choices=[], required=False)

    def __init__(self, *args, ai_model_choices: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = ai_model_choices or ["gpt-4o"]
        self.fields["ai_model"].choices = [(m, m) for m in choices]
        self.fields["ai_model"].initial = choices[0]


class FlashcardExerciseSetForm(forms.Form):
    FLASHCARD_MODE_CHOICES = [
        ("form_to_meaning", "Form → meaning"),
        ("meaning_to_form", "Meaning → form"),
    ]

    theme = forms.ChoiceField(
        choices=[
            ("vocabulary", "Vocabulary"),
            ("grammar", "Grammar"),
            ("morphology", "Morphology"),
            ("grammar_morphology", "Grammar/Morphology"),
        ],
        initial="vocabulary",
    )
    flashcard_mode = forms.ChoiceField(choices=FLASHCARD_MODE_CHOICES, initial="form_to_meaning")
    item_count = forms.IntegerField(min_value=1, max_value=50, initial=10)
    ai_model = forms.ChoiceField(choices=[], required=False)

    def __init__(self, *args, ai_model_choices: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = ai_model_choices or ["gpt-4o"]
        self.fields["ai_model"].choices = [(m, m) for m in choices]
        self.fields["ai_model"].initial = choices[0]


class DeleteCachedWordAudioForm(forms.Form):
    language = forms.ChoiceField(choices=[], label="Language")

    def __init__(self, *args, language_choices: list[tuple[str, str]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = language_choices or []
        self.fields["language"].choices = choices


class GrantAdminPrivilegesForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none(), label="User")

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if queryset is None:
            queryset = User.objects.filter(is_staff=False).order_by("username")
        self.fields["user"].queryset = queryset


class AdminAdjustCreditsForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all().order_by("username"), label="User")
    amount_usd = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        label="Amount (USD)",
        help_text="Use positive values to recharge and negative values to deduct credits.",
    )
    reason = forms.CharField(max_length=255, required=False)

    def clean_amount_usd(self):
        value = Decimal(self.cleaned_data["amount_usd"])
        if value == Decimal("0"):
            raise forms.ValidationError("Amount must be non-zero.")
        return value
