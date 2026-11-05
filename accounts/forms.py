from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.conf import settings
from django.core.exceptions import ValidationError

from audit import service as audit

from .models import User


class ThrottledAuthenticationForm(AuthenticationForm):
    """Refuses further attempts for a username after too many recent failures."""

    def clean(self):
        username = self.cleaned_data.get("username", "")
        if username and audit.recent_failed_logins(username, settings.LOGIN_LOCK_MINUTES) \
                >= settings.LOGIN_MAX_FAILURES:
            raise ValidationError(
                "Too many failed attempts. Try again in %(m)s minutes.",
                code="locked", params={"m": settings.LOGIN_LOCK_MINUTES},
            )
        return super().clean()


class NewUserForm(forms.Form):
    username = forms.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    role = forms.ChoiceField(choices=User.Role.choices)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            validate_password(password, user=User(username=cleaned.get("username", "")))
        return cleaned
