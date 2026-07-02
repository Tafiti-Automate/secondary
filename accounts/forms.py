from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User


class StyledFormMixin:
    def style_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-checkbox"
            else:
                field.widget.attrs["class"] = "form-control"
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput)):
                field.widget.attrs.setdefault("placeholder", field.label)


class LoginForm(StyledFormMixin, AuthenticationForm):
    remember_me = forms.BooleanField(required=False, label="Keep me signed in on this device")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class UserCreateForm(StyledFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "role", "profile_picture", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class UserUpdateForm(StyledFormMixin, UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "role", "profile_picture", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "profile_picture")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
