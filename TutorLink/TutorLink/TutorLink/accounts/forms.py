from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Profile

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Registration form: Django's UserCreationForm plus the Profile fields."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, help_text="Tutors need admin approval.")
    course = forms.CharField(max_length=100)
    year_level = forms.IntegerField(min_value=1, max_value=6)

    field_order = [
        "username", "first_name", "last_name", "email",
        "role", "course", "year_level", "password1", "password2",
    ]

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            role = self.cleaned_data["role"]
            # Students are active right away; tutors wait for administrator approval.
            status = (
                Profile.STATUS_PENDING if role == Profile.ROLE_TUTOR else Profile.STATUS_APPROVED
            )
            Profile.objects.create(
                user=user,
                role=role,
                course=self.cleaned_data["course"],
                year_level=self.cleaned_data["year_level"],
                approval_status=status,
            )
        return user
