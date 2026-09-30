"""Account password forms using Django's hashing and password validation."""

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.exceptions import ValidationError


class _PasswordPolicy:
    """Use configured validators, or Django's usual policy for these new forms.

    Older installations have AUTH_PASSWORD_VALIDATORS=[]; leave registration
    and existing passwords alone while protecting newly chosen passwords here.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_validators = []
        if not password_validation.get_default_password_validators():
            self.fallback_validators = [
                password_validation.UserAttributeSimilarityValidator(),
                password_validation.MinimumLengthValidator(),
                password_validation.CommonPasswordValidator(),
                password_validation.NumericPasswordValidator(),
            ]
            self.fields["new_password1"].help_text = (
                password_validation.password_validators_help_text_html(self.fallback_validators)
            )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("new_password2")
        if password and self.fallback_validators:
            try:
                password_validation.validate_password(password, self.user, self.fallback_validators)
            except ValidationError as error:
                self.add_error("new_password2", error)
        return cleaned


class AccountPasswordChangeForm(_PasswordPolicy, PasswordChangeForm):
    pass


class AdminSetPasswordForm(_PasswordPolicy, SetPasswordForm):
    pass


class PasswordResetUserForm(forms.Form):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.none(), label="User")

    def __init__(self, *args, users, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = users
