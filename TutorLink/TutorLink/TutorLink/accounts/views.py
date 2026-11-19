from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegisterForm
from .models import Profile


def register(request):
    """Create a Student or Tutor account and log the new user in."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if user.profile.role == Profile.ROLE_TUTOR:
                messages.info(
                    request,
                    "Welcome! Your tutor application is pending administrator approval. "
                    "You can post sessions once you are approved.",
                )
            else:
                messages.success(request, "Welcome to TutorLink! Browse sessions and book one.")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})
