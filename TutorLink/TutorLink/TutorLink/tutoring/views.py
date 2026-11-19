from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Profile

from .forms import FeedbackForm, SessionForm
from .models import Booking, Feedback, Subject, TutoringSession


# Role-based access helpers
def role_required(role, approved_only=False):
    """Allow only logged-in users with the given role (tutors can also be required to be approved)."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if profile is None or profile.role != role:
                raise PermissionDenied("This page is only for " + role + "s.")
            if approved_only and not profile.can_post_sessions:
                raise PermissionDenied("Your tutor account is not approved yet.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


student_required = role_required(Profile.ROLE_STUDENT)
approved_tutor_required = role_required(Profile.ROLE_TUTOR, approved_only=True)


def with_booking_counts(queryset):
    """Annotate sessions with the number of active bookings (one query instead of one per row)."""
    return queryset.annotate(
        active_bookings=Count("bookings", filter=~Q(bookings__status=Booking.STATUS_CANCELLED))
    )


# Public pages
def home(request):
    """Browse and search upcoming sessions."""
    sessions = with_booking_counts(
        TutoringSession.objects.select_related("tutor", "subject").filter(
            date__gte=timezone.localdate(),
            status__in=[TutoringSession.STATUS_OPEN, TutoringSession.STATUS_FULL],
            tutor__profile__approval_status=Profile.STATUS_APPROVED,
        )
    )

    query = request.GET.get("q", "").strip()
    subject_id = request.GET.get("subject", "")
    if query:
        sessions = sessions.filter(
            Q(subject__name__icontains=query)
            | Q(topic__icontains=query)
            | Q(tutor__username__icontains=query)
            | Q(tutor__first_name__icontains=query)
            | Q(tutor__last_name__icontains=query)
        )
    if subject_id.isdigit():
        sessions = sessions.filter(subject_id=int(subject_id))

    context = {
        "sessions": sessions,
        "subjects": Subject.objects.all(),
        "query": query,
        "selected_subject": int(subject_id) if subject_id.isdigit() else None,
    }
    return render(request, "tutoring/home.html", context)


def about(request):
    return render(request, "tutoring/about.html")


def session_detail(request, pk):
    session = get_object_or_404(
        with_booking_counts(TutoringSession.objects.select_related("tutor", "subject")), pk=pk
    )
    booking = None
    if request.user.is_authenticated:
        booking = Booking.objects.filter(session=session, student=request.user).first()

    is_owner = request.user.is_authenticated and request.user == session.tutor
    roster = None
    if is_owner:
        roster = session.bookings.exclude(status=Booking.STATUS_CANCELLED).select_related("student")

    feedback_list = Feedback.objects.filter(booking__session=session).select_related("booking__student")
    average = feedback_list.aggregate(avg=Avg("rating"))["avg"]

    return render(
        request,
        "tutoring/session_detail.html",
        {
            "session": session,
            "booking": booking,
            "is_owner": is_owner,
            "roster": roster,
            "feedback_list": feedback_list,
            "average_rating": round(average, 1) if average else None,
        },
    )


# Tutor views: post / edit / delete / complete sessions
@approved_tutor_required
def session_create(request):
    form = SessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.tutor = request.user
        session.save()
        messages.success(request, "Your session has been posted.")
        return redirect("session_detail", pk=session.pk)
    return render(request, "tutoring/session_form.html", {"form": form, "heading": "Post a session"})


@approved_tutor_required
def session_edit(request, pk):
    session = get_object_or_404(TutoringSession, pk=pk, tutor=request.user)
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        form.save()
        session.refresh_status()
        messages.success(request, "Session updated.")
        return redirect("session_detail", pk=session.pk)
    return render(request, "tutoring/session_form.html", {"form": form, "heading": "Edit session"})


@require_POST
@approved_tutor_required
def session_delete(request, pk):
    session = get_object_or_404(TutoringSession, pk=pk, tutor=request.user)
    session.delete()
    messages.success(request, "Session deleted.")
    return redirect("dashboard")


@require_POST
@approved_tutor_required
def session_complete(request, pk):
    """Mark a session as completed; everyone who was booked counts as attended and can leave feedback."""
    session = get_object_or_404(TutoringSession, pk=pk, tutor=request.user)
    with transaction.atomic():
        session.status = TutoringSession.STATUS_COMPLETED
        session.save(update_fields=["status"])
        session.bookings.filter(status=Booking.STATUS_BOOKED).update(status=Booking.STATUS_ATTENDED)
    messages.success(request, "Session marked as completed.")
    return redirect("session_detail", pk=session.pk)


# Student views: book / cancel / feedback
@require_POST
@student_required
def book_session(request, pk):
    # atomic + select_for_update: two students cannot take the last slot at the same time.
    with transaction.atomic():
        session = get_object_or_404(TutoringSession.objects.select_for_update(), pk=pk)

        if session.status != TutoringSession.STATUS_OPEN or session.date < timezone.localdate():
            messages.error(request, "This session is not open for booking.")
            return redirect("session_detail", pk=pk)
        if session.slots_left <= 0:
            messages.error(request, "Sorry, this session is already full.")
            return redirect("session_detail", pk=pk)

        booking, created = Booking.objects.get_or_create(
            student=request.user, session=session, defaults={"status": Booking.STATUS_BOOKED}
        )
        if not created:
            if booking.status == Booking.STATUS_CANCELLED:
                booking.status = Booking.STATUS_BOOKED  # re-book a cancelled booking
                booking.save(update_fields=["status"])
            else:
                messages.info(request, "You have already booked this session.")
                return redirect("session_detail", pk=pk)
        session.refresh_status()

    messages.success(request, "Session booked! See you there.")
    return redirect("session_detail", pk=pk)


@require_POST
@student_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, student=request.user)
    if booking.status != Booking.STATUS_BOOKED:
        messages.error(request, "Only upcoming bookings can be cancelled.")
    else:
        booking.status = Booking.STATUS_CANCELLED
        booking.save(update_fields=["status"])
        booking.session.refresh_status()  # a freed slot re-opens a full session
        messages.success(request, "Booking cancelled.")
    return redirect("dashboard")


@student_required
def feedback_create(request, booking_pk):
    booking = get_object_or_404(
        Booking.objects.select_related("session__subject", "session__tutor"),
        pk=booking_pk,
        student=request.user,
    )
    if booking.status != Booking.STATUS_ATTENDED:
        messages.error(request, "You can only rate a session after it has been completed.")
        return redirect("dashboard")
    if hasattr(booking, "feedback"):
        messages.info(request, "You already left feedback for this session.")
        return redirect("dashboard")

    form = FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        feedback = form.save(commit=False)
        feedback.booking = booking
        feedback.save()
        messages.success(request, "Thank you for your feedback!")
        return redirect("dashboard")
    return render(request, "tutoring/feedback_form.html", {"form": form, "booking": booking})


# Personal dashboard ("My Bookings" / "My Sessions")
@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    if profile is None:  # e.g. a superuser created with createsuperuser
        messages.info(request, "Administrator accounts are managed in the admin site.")
        return redirect("/admin/")

    context = {"profile": profile}
    if profile.is_student:
        context["bookings"] = (
            Booking.objects.filter(student=request.user)
            .select_related("session__subject", "session__tutor")
            .order_by("-session__date", "-session__start_time")
        )
    else:
        context["sessions"] = with_booking_counts(
            TutoringSession.objects.filter(tutor=request.user).select_related("subject")
        ).order_by("-date", "-start_time")
        rating = Feedback.objects.filter(booking__session__tutor=request.user).aggregate(
            avg=Avg("rating"), total=Count("id")
        )
        context["average_rating"] = round(rating["avg"], 2) if rating["avg"] else None
        context["review_count"] = rating["total"]
    return render(request, "tutoring/dashboard.html", context)
