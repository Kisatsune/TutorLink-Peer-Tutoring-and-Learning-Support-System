"""Validation for data sent by the Tkinter dashboard (reuses Django's ModelForm validation)."""
from django import forms
from django.contrib.auth import get_user_model

from accounts.models import Profile
from tutoring.models import Subject, TutoringSession

User = get_user_model()


class SubjectApiForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "description"]


class SessionApiForm(forms.ModelForm):
    class Meta:
        model = TutoringSession
        fields = [
            "tutor", "subject", "topic", "date", "start_time",
            "duration_minutes", "slots", "status", "location",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only approved tutors can own sessions.
        self.fields["tutor"].queryset = User.objects.filter(
            profile__role=Profile.ROLE_TUTOR, profile__approval_status=Profile.STATUS_APPROVED
        )
