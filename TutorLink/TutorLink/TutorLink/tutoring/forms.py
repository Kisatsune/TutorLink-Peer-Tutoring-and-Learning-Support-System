from django import forms
from django.utils import timezone

from .models import Feedback, TutoringSession


class SessionForm(forms.ModelForm):
    """Used by tutors to post or edit a tutoring session."""

    class Meta:
        model = TutoringSession
        fields = ["subject", "topic", "date", "start_time", "duration_minutes", "slots", "location"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean_date(self):
        date = self.cleaned_data["date"]
        # New sessions must be in the future (editing an old session is still allowed).
        if not self.instance.pk and date < timezone.localdate():
            raise forms.ValidationError("The session date cannot be in the past.")
        return date


class FeedbackForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} - " + label) for i, label in
                 [(5, "Excellent"), (4, "Good"), (3, "Okay"), (2, "Poor"), (1, "Very poor")]],
        coerce=int,
    )

    class Meta:
        model = Feedback
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}
