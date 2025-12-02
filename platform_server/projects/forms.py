from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Project


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProjectForm(forms.ModelForm):
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
