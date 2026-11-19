"""Tests for the web application: python manage.py test tutoring"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile

from .models import Booking, Feedback, Subject, TutoringSession

User = get_user_model()


def make_user(username, role, status=Profile.STATUS_APPROVED):
    user = User.objects.create_user(username=username, password="pass12345")
    Profile.objects.create(user=user, role=role, course="BSIT", year_level=1, approval_status=status)
    return user


class TutoringTestBase(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Mathematics")
        self.tutor = make_user("tutor1", Profile.ROLE_TUTOR)
        self.student = make_user("student1", Profile.ROLE_STUDENT)
        self.student2 = make_user("student2", Profile.ROLE_STUDENT)
        self.session = TutoringSession.objects.create(
            tutor=self.tutor, subject=self.subject, topic="Algebra",
            date=timezone.localdate() + timedelta(days=2), start_time="15:00", slots=1,
        )


class RegistrationTests(TestCase):
    def register(self, role):
        return self.client.post(reverse("register"), {
            "username": f"new_{role}", "first_name": "New", "last_name": "User",
            "email": "new@example.com", "role": role, "course": "BSIT", "year_level": 2,
            "password1": "Str0ng-pass-123", "password2": "Str0ng-pass-123",
        })

    def test_student_is_approved_immediately(self):
        self.register(Profile.ROLE_STUDENT)
        profile = Profile.objects.get(user__username="new_student")
        self.assertEqual(profile.approval_status, Profile.STATUS_APPROVED)

    def test_tutor_starts_pending(self):
        self.register(Profile.ROLE_TUTOR)
        profile = Profile.objects.get(user__username="new_tutor")
        self.assertEqual(profile.approval_status, Profile.STATUS_PENDING)
        self.assertFalse(profile.can_post_sessions)


class RoleAccessTests(TutoringTestBase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_pending_tutor_cannot_post_sessions(self):
        make_user("pending_tutor", Profile.ROLE_TUTOR, Profile.STATUS_PENDING)
        self.client.login(username="pending_tutor", password="pass12345")
        self.assertEqual(self.client.get(reverse("session_create")).status_code, 403)

    def test_student_cannot_post_sessions(self):
        self.client.login(username="student1", password="pass12345")
        self.assertEqual(self.client.get(reverse("session_create")).status_code, 403)

    def test_approved_tutor_can_post_session(self):
        self.client.login(username="tutor1", password="pass12345")
        response = self.client.post(reverse("session_create"), {
            "subject": self.subject.pk, "topic": "Geometry",
            "date": (timezone.localdate() + timedelta(days=4)).isoformat(),
            "start_time": "10:00", "duration_minutes": 60, "slots": 3, "location": "Room 1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TutoringSession.objects.filter(topic="Geometry", tutor=self.tutor).exists())

    def test_tutor_cannot_book_sessions(self):
        self.client.login(username="tutor1", password="pass12345")
        response = self.client.post(reverse("book_session", args=[self.session.pk]))
        self.assertEqual(response.status_code, 403)


class BookingTests(TutoringTestBase):
    def book(self, username):
        self.client.login(username=username, password="pass12345")
        return self.client.post(reverse("book_session", args=[self.session.pk]))

    def test_student_can_book(self):
        self.book("student1")
        self.assertTrue(Booking.objects.filter(student=self.student, session=self.session).exists())

    def test_cannot_book_twice(self):
        self.book("student1")
        self.book("student1")
        self.assertEqual(Booking.objects.filter(student=self.student, session=self.session).count(), 1)

    def test_full_session_rejects_extra_student_and_reopens_on_cancel(self):
        self.book("student1")
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, TutoringSession.STATUS_FULL)

        self.book("student2")  # the only slot is taken
        self.assertFalse(Booking.objects.filter(student=self.student2).exists())

        booking = Booking.objects.get(student=self.student)
        self.client.login(username="student1", password="pass12345")
        self.client.post(reverse("cancel_booking", args=[booking.pk]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, TutoringSession.STATUS_OPEN)


class FeedbackTests(TutoringTestBase):
    def test_feedback_needs_attended_booking(self):
        booking = Booking.objects.create(student=self.student, session=self.session)
        self.client.login(username="student1", password="pass12345")
        self.client.post(reverse("feedback_create", args=[booking.pk]), {"rating": 5, "comment": "Great"})
        self.assertFalse(Feedback.objects.exists())

    def test_complete_session_then_leave_feedback(self):
        booking = Booking.objects.create(student=self.student, session=self.session)
        self.client.login(username="tutor1", password="pass12345")
        self.client.post(reverse("session_complete", args=[self.session.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_ATTENDED)

        self.client.login(username="student1", password="pass12345")
        self.client.post(reverse("feedback_create", args=[booking.pk]), {"rating": 5, "comment": "Great"})
        self.assertEqual(Feedback.objects.get(booking=booking).rating, 5)


class SearchTests(TutoringTestBase):
    def test_search_by_topic(self):
        found = self.client.get(reverse("home"), {"q": "Algebra"})
        self.assertContains(found, "Algebra")
        missing = self.client.get(reverse("home"), {"q": "Chemistry"})
        self.assertNotContains(missing, "Algebra")

    def test_pending_tutor_sessions_are_hidden(self):
        self.tutor.profile.approval_status = Profile.STATUS_PENDING
        self.tutor.profile.save()
        self.assertNotContains(self.client.get(reverse("home")), "Algebra")
