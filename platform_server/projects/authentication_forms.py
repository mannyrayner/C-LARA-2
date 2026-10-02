"""Consistent mobile keyboard hints for account username fields."""

from django.contrib.auth.forms import AuthenticationForm


class UsernameInputMixin:
    """Keep phone keyboards from rewriting usernames without disabling autofill."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "autocapitalize": "none",
            "autocorrect": "off",
            "spellcheck": "false",
            "autocomplete": "username",
        })


class LoginForm(UsernameInputMixin, AuthenticationForm):
    """Use Django authentication with the shared username input hints."""
