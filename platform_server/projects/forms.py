from zoneinfo import available_timezones
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from django.forms import modelformset_factory

from .models import (
    Community,
    CommunityMembership,
    OpenAIModelPricing,
    Project,
    Profile,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImageStyle,
    IssueSuggestion,
    IssueUpdateSuggestion,
)


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProjectForm(forms.ModelForm):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("ar", "Arabic"),
        ("da", "Danish"),
        ("de", "German"),
        ("dre", "Drehu"),
        ("nl", "Dutch"),
        ("fa", "Persian"),
        ("fr", "French"),
        ("hi", "Hindi"),
        ("iai", "Iaai"),
        ("is", "Icelandic"),
        ("it", "Italian"),
        ("ja", "Japanese"),
        ("xkk", "Kok Kaper"),
        ("ko", "Korean"),
        ("zh", "Mandarin Chinese"),
        ("non", "Old Norse"),
        ("no", "Norwegian"),
        ("pl", "Polish"),
        ("pt", "Portuguese"),
        ("ru", "Russian"),
        ("sk", "Slovak"),
        ("es", "Spanish"),
        ("sv", "Swedish"),
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
            "audio_mode",
            "access_scope",
            "community",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "source_text": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(self.instance, "pk", None):
            self.fields["input_mode"].initial = Project.INPUT_DESCRIPTION
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
        if cleaned.get("access_scope") == Project.ACCESS_COMMUNITY and not cleaned.get("community"):
            self.add_error("community", "Please select a community for community-only access.")

        return cleaned


TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(available_timezones())]
LANGUAGE_CHOICES = ProjectForm.LANGUAGE_CHOICES


class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)
    dialogue_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, label="Dialogue language")
    dialogue_memory_enabled = forms.BooleanField(
        required=False,
        label="Enable dialogue personalization memory",
        help_text="Store a compact summary of your latest discovery preferences across sessions.",
    )
    use_personal_openai_key = forms.BooleanField(
        required=False,
        label="Use my OpenAI API key (BYOK)",
        help_text="When enabled, eligible OpenAI calls use your key instead of platform credits.",
    )
    openai_api_key = forms.CharField(
        required=False,
        label="OpenAI API key",
        widget=forms.PasswordInput(render_value=True),
        help_text="Stored for your account and used only when BYOK is enabled.",
    )

    class Meta:
        model = Profile
        fields = ["timezone", "dialogue_language", "dialogue_memory_enabled", "use_personal_openai_key", "openai_api_key"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("use_personal_openai_key") and not (cleaned.get("openai_api_key") or "").strip():
            self.add_error("openai_api_key", "Enter an OpenAI API key to enable BYOK.")
        return cleaned


class ProjectDiscoveryMetadataForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["discovery_summary", "discovery_keywords", "discovery_keywords_en", "discovery_level", "discovery_word_count"]
        widgets = {
            "discovery_summary": forms.Textarea(attrs={"rows": 3}),
        }

    discovery_keywords = forms.CharField(required=False, help_text="Comma-separated keywords")
    discovery_keywords_en = forms.CharField(required=False, help_text="Comma-separated English keywords")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        keywords = self.instance.discovery_keywords if getattr(self.instance, "pk", None) else []
        keywords_en = self.instance.discovery_keywords_en if getattr(self.instance, "pk", None) else []
        self.fields["discovery_keywords"].initial = ", ".join(keywords or [])
        self.fields["discovery_keywords_en"].initial = ", ".join(keywords_en or [])

    def clean_discovery_keywords(self):
        raw = (self.cleaned_data.get("discovery_keywords") or "").strip()
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]

    def clean_discovery_keywords_en(self):
        raw = (self.cleaned_data.get("discovery_keywords_en") or "").strip()
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]


class ProjectImageStyleForm(forms.ModelForm):
    class Meta:
        model = ProjectImageStyle
        fields = [
            "style_brief",
            "expanded_style_description",
            "sample_image_prompt",
            "ai_model",
            "sample_image_model",
            "discourage_text_in_images",
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
    extra=1,
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


class IssueSuggestionForm(forms.ModelForm):
    class Meta:
        model = IssueSuggestion
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"style": "width: 100%;"}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }


class IssueUpdateSuggestionForm(forms.ModelForm):
    issue_id = forms.ChoiceField(choices=[])

    class Meta:
        model = IssueUpdateSuggestion
        fields = ["issue_id", "update_description"]
        labels = {
            "issue_id": "Issue to update",
            "update_description": "Suggested update",
        }
        widgets = {
            "update_description": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, issue_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["issue_id"].choices = issue_choices or []


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
        ("image_to_form", "Image → form (picture dictionary)"),
        ("form_to_image", "Form → image (picture dictionary)"),
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


class WordScrambleExerciseSetForm(forms.Form):
    theme = forms.ChoiceField(
        choices=[
            ("vocabulary", "Vocabulary"),
        ],
        initial="vocabulary",
        help_text="Word scrambles currently use picture-dictionary vocabulary items.",
    )
    item_count = forms.IntegerField(
        min_value=1,
        max_value=15,
        initial=8,
        help_text="Number of picture-clue words to hide in the grid.",
    )
    grid_rows = forms.IntegerField(min_value=6, max_value=16, initial=10)
    grid_cols = forms.IntegerField(min_value=6, max_value=16, initial=10)


class CrosswordExerciseSetForm(forms.Form):
    theme = forms.ChoiceField(
        choices=[
            ("vocabulary", "Vocabulary"),
        ],
        initial="vocabulary",
        help_text="Picture crosswords currently use picture-dictionary vocabulary items.",
    )
    item_count = forms.IntegerField(
        min_value=2,
        max_value=20,
        initial=10,
        help_text="Number of picture-clue words to try to place in the crossword.",
    )
    max_grid_size = forms.IntegerField(
        min_value=6,
        max_value=20,
        initial=12,
        help_text="Maximum width/height before the occupied crossword is cropped.",
    )



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


class CreditTransferForm(forms.Form):
    recipient = forms.ModelChoiceField(queryset=User.objects.none(), label="Recipient")
    amount_usd = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        label="Amount (USD)",
        help_text="Transfer amount must be positive.",
    )
    note = forms.CharField(max_length=255, required=False, label="Note (optional)")

    def __init__(self, *args, sender=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.order_by("username")
        if sender is not None and getattr(sender, "pk", None):
            qs = qs.exclude(pk=sender.pk)
        self.fields["recipient"].queryset = qs


class ProjectUnderstandingForm(forms.Form):
    VISIBILITY_CHOICES = [
        ("private", "Private (visible only to me)"),
        ("public", "Public to other C-LARA-2 users/reviewers"),
    ]

    question = forms.CharField(
        max_length=4000,
        label="Project-understanding question",
        help_text="Ask a high-level question about the C-LARA-2 repository. Codex will inspect the configured checkout in read-only mode.",
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "style": "width: 100%; font-family: monospace;",
                "placeholder": "Summarise the repository in three bullet points; cite files if possible.",
            }
        ),
    )
    visibility = forms.ChoiceField(
        choices=VISIBILITY_CHOICES,
        initial="private",
        label="Log visibility",
        help_text="Private runs stay visible only to you; public runs can be reviewed by other C-LARA-2 users/reviewers.",
    )


class AdminOpenAIPricingForm(forms.ModelForm):
    class Meta:
        model = OpenAIModelPricing
        fields = ["model_name", "input_usd_per_1m", "output_usd_per_1m", "source_url", "status", "notes"]


class AdminCommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ["name", "language", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"] = forms.ChoiceField(
            choices=ProjectForm.LANGUAGE_CHOICES,
            initial=self.instance.language if getattr(self.instance, "pk", None) else "en",
        )


class AdminCommunityMembershipForm(forms.Form):
    community = forms.ModelChoiceField(queryset=Community.objects.none(), label="Community")
    user = forms.ModelChoiceField(queryset=User.objects.none(), label="User")
    role = forms.ChoiceField(choices=CommunityMembership.ROLE_CHOICES, initial=CommunityMembership.ROLE_MEMBER)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["community"].queryset = Community.objects.filter(is_active=True).order_by("name")
        self.fields["user"].queryset = User.objects.order_by("username")


class CommunityOrganiserMembershipForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none(), label="User")

    def __init__(self, *args, community: Community | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.order_by("username")


class AdminDeleteCommunityForm(forms.Form):
    community = forms.ModelChoiceField(queryset=Community.objects.none(), label="Community")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["community"].queryset = Community.objects.order_by("name")
