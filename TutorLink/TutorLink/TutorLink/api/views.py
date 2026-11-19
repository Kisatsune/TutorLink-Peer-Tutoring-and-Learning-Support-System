
import xml.etree.ElementTree as ET

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Avg, Count, ProtectedError, Sum
from django.views.decorators.csrf import csrf_exempt

from accounts.models import Profile
from tutoring.models import Booking, Feedback, Subject, TutoringSession

from .auth import token_required
from .forms import SessionApiForm, SubjectApiForm
from .models import ApiToken
from .utils import (
    add_text,
    error_response,
    form_errors_response,
    get_data,
    message_response,
    methods,
    to_xml_response,
)

User = get_user_model()


# Serializers: model object -> XML element

def user_element(user):
    profile = getattr(user, "profile", None)
    el = ET.Element("user")
    add_text(el, "id", user.pk)
    add_text(el, "username", user.username)
    add_text(el, "full_name", user.get_full_name())
    add_text(el, "email", user.email)
    add_text(el, "role", profile.role if profile else ("admin" if user.is_staff else ""))
    add_text(el, "course", profile.course if profile else "")
    add_text(el, "year_level", profile.year_level if profile else "")
    add_text(el, "approval_status", profile.approval_status if profile else "")
    add_text(el, "date_joined", user.date_joined.strftime("%Y-%m-%d"))
    return el


def subject_element(subject):
    el = ET.Element("subject")
    add_text(el, "id", subject.pk)
    add_text(el, "name", subject.name)
    add_text(el, "description", subject.description)
    return el


def session_element(session):
    el = ET.Element("session")
    add_text(el, "id", session.pk)
    add_text(el, "subject_id", session.subject_id)
    add_text(el, "subject", session.subject.name)
    add_text(el, "tutor_id", session.tutor_id)
    add_text(el, "tutor", session.tutor.username)
    add_text(el, "topic", session.topic)
    add_text(el, "date", session.date.isoformat())
    add_text(el, "start_time", session.start_time.strftime("%H:%M"))
    add_text(el, "duration_minutes", session.duration_minutes)
    add_text(el, "slots", session.slots)
    add_text(el, "booked", session.booked_count)
    add_text(el, "status", session.status)
    add_text(el, "location", session.location)
    return el


def booking_element(booking):
    el = ET.Element("booking")
    add_text(el, "id", booking.pk)
    add_text(el, "session_id", booking.session_id)
    add_text(el, "subject", booking.session.subject.name)
    add_text(el, "tutor", booking.session.tutor.username)
    add_text(el, "date", booking.session.date.isoformat())
    add_text(el, "student_id", booking.student_id)
    add_text(el, "student", booking.student.username)
    add_text(el, "status", booking.status)
    feedback = getattr(booking, "feedback", None)
    add_text(el, "rating", feedback.rating if feedback else "")
    return el


def list_response(root_tag, elements):
    root = ET.Element(root_tag)
    root.extend(elements)
    return to_xml_response(root)


# Authentication
@csrf_exempt
@methods("POST")
def login_view(request):
    """Exchange an administrator's username and password for an API token."""
    user = authenticate(
        request,
        username=request.POST.get("username", ""),
        password=request.POST.get("password", ""),
    )
    if user is None:
        return error_response("Invalid username or password.", 401)
    if not user.is_staff:
        return error_response("Only administrators can use the dashboard.", 403)

    token, _ = ApiToken.objects.get_or_create(user=user)
    root = ET.Element("login")
    add_text(root, "token", token.key)
    add_text(root, "username", user.username)
    return to_xml_response(root)


@token_required
@methods("POST")
def logout_view(request):
    ApiToken.objects.filter(user=request.api_user).delete()
    return message_response("Logged out.")


# Users and tutor approval
@token_required
@methods("GET")
def users_list(request):
    users = User.objects.select_related("profile").order_by("id")
    role = request.GET.get("role")
    status = request.GET.get("status")
    if role:
        users = users.filter(profile__role=role)
    if status:
        users = users.filter(profile__approval_status=status)
    return list_response("users", [user_element(u) for u in users])


@token_required
@methods("POST")
def user_approval(request, pk, decision):
    """Approve or reject a tutor application (decision is 'approved' or 'rejected')."""
    profile = Profile.objects.filter(user_id=pk, role=Profile.ROLE_TUTOR).first()
    if profile is None:
        return error_response("Tutor not found.", 404)
    profile.approval_status = decision
    profile.save(update_fields=["approval_status"])
    return message_response(f"Tutor {profile.user.username} {decision}.")


# Subjects (full CRUD)
@token_required
@methods("GET", "POST")
def subjects_collection(request):
    if request.method == "GET":
        return list_response("subjects", [subject_element(s) for s in Subject.objects.all()])

    form = SubjectApiForm(request.POST)
    if not form.is_valid():
        return form_errors_response(form)
    return to_xml_response(subject_element(form.save()), 201)


@token_required
@methods("GET", "PUT", "DELETE")
def subject_detail(request, pk):
    subject = Subject.objects.filter(pk=pk).first()
    if subject is None:
        return error_response("Subject not found.", 404)

    if request.method == "GET":
        return to_xml_response(subject_element(subject))

    if request.method == "PUT":
        form = SubjectApiForm(get_data(request), instance=subject)
        if not form.is_valid():
            return form_errors_response(form)
        return to_xml_response(subject_element(form.save()))

    try:  # DELETE
        subject.delete()
    except ProtectedError:
        return error_response("This subject still has sessions and cannot be deleted.", 409)
    return message_response("Subject deleted.")


# Sessions (full CRUD)
@token_required
@methods("GET", "POST")
def sessions_collection(request):
    if request.method == "GET":
        sessions = TutoringSession.objects.select_related("tutor", "subject").order_by("-date", "-start_time")
        return list_response("sessions", [session_element(s) for s in sessions])

    form = SessionApiForm(request.POST)
    if not form.is_valid():
        return form_errors_response(form)
    session = form.save()
    session.refresh_status()
    return to_xml_response(session_element(session), 201)


@token_required
@methods("GET", "PUT", "DELETE")
def session_detail(request, pk):
    session = TutoringSession.objects.select_related("tutor", "subject").filter(pk=pk).first()
    if session is None:
        return error_response("Session not found.", 404)

    if request.method == "GET":
        return to_xml_response(session_element(session))

    if request.method == "PUT":
        form = SessionApiForm(get_data(request), instance=session)
        if not form.is_valid():
            return form_errors_response(form)
        session = form.save()
        session.refresh_status()
        return to_xml_response(session_element(session))

    session.delete()  # DELETE (bookings are removed with it)
    return message_response("Session deleted.")


# Bookings (read-only monitoring)
@token_required
@methods("GET")
def bookings_list(request):
    bookings = Booking.objects.select_related("student", "session__subject", "session__tutor")
    session_id = request.GET.get("session")
    if session_id and session_id.isdigit():
        bookings = bookings.filter(session_id=int(session_id))
    return list_response("bookings", [booking_element(b) for b in bookings.order_by("-created_at")])


# Statistics
@token_required
@methods("GET")
def stats(request):
    root = ET.Element("statistics")

    totals = ET.SubElement(root, "totals")
    add_text(totals, "students", Profile.objects.filter(role=Profile.ROLE_STUDENT).count())
    add_text(totals, "tutors", Profile.objects.filter(
        role=Profile.ROLE_TUTOR, approval_status=Profile.STATUS_APPROVED).count())
    add_text(totals, "pending_tutors", Profile.objects.filter(
        role=Profile.ROLE_TUTOR, approval_status=Profile.STATUS_PENDING).count())
    add_text(totals, "subjects", Subject.objects.count())
    add_text(totals, "sessions", TutoringSession.objects.count())
    add_text(totals, "bookings", Booking.objects.exclude(status=Booking.STATUS_CANCELLED).count())
    add_text(totals, "feedback", Feedback.objects.count())

    # Sessions per subject
    per_subject = ET.SubElement(root, "sessions_per_subject")
    for subject in Subject.objects.annotate(total=Count("sessions")).order_by("-total", "name"):
        item = ET.SubElement(per_subject, "subject")
        add_text(item, "name", subject.name)
        add_text(item, "sessions", subject.total)

    # Top-rated tutors (average of all feedback received)
    top = ET.SubElement(root, "top_tutors")
    tutors = (
        User.objects.filter(tutoring_sessions__bookings__feedback__isnull=False)
        .annotate(
            avg_rating=Avg("tutoring_sessions__bookings__feedback__rating"),
            reviews=Count("tutoring_sessions__bookings__feedback"),
        )
        .order_by("-avg_rating", "-reviews")[:5]
    )
    for tutor in tutors:
        item = ET.SubElement(top, "tutor")
        add_text(item, "id", tutor.pk)
        add_text(item, "name", tutor.get_full_name() or tutor.username)
        add_text(item, "average_rating", round(tutor.avg_rating, 2))
        add_text(item, "reviews", tutor.reviews)

    # Total tutoring hours (completed sessions only)
    completed = TutoringSession.objects.filter(status=TutoringSession.STATUS_COMPLETED)
    minutes = completed.aggregate(total=Sum("duration_minutes"))["total"] or 0
    hours = ET.SubElement(root, "tutoring_hours")
    add_text(hours, "completed_sessions", completed.count())
    add_text(hours, "total_hours", round(minutes / 60, 2))

    return to_xml_response(root)
