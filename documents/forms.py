from django import forms

from .models import Category, Level


class UploadForm(forms.Form):
    file = forms.FileField()
    name = forms.CharField(max_length=150, required=False, help_text="Optional. Defaults to the file name.")
    category = forms.ChoiceField(choices=Category.choices)


class EditForm(forms.Form):
    name = forms.CharField(max_length=150)
    category = forms.ChoiceField(choices=Category.choices)
    file = forms.FileField(required=False, label="Replace file (optional)")


class ShareForm(forms.Form):
    username = forms.CharField(max_length=150)
    level = forms.ChoiceField(choices=Level.choices)


class SearchForm(forms.Form):
    q = forms.CharField(required=False, label="Name")
    owner = forms.CharField(required=False)
    category = forms.ChoiceField(required=False, choices=[("", "Any category")] + list(Category.choices))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
