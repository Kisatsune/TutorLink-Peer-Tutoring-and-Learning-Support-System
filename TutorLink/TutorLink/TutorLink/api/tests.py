import xml.etree.ElementTree as ET
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from tutoring.models import Booking, Feedback, Subject, TutoringSession

User = get_user_model()


class ApiTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", password="admin-pass-1", is_staff=True)
        self.student_user = User.objects.create_user("stud", password="pass12345")
        Profile.objects.create(user=self.student_user, role=Profile.ROLE_STUDENT)
        self.tutor = User.objects.create_user("tut", password="pass12345")
        Profile.objects.create(
            user=self.tutor, role=Profile.ROLE_TUTOR, approval_status=Profile.STATUS_PENDING
        )

    def token(self, username="boss", password="admin-pass-1"):
        response = self.client.post(reverse("api_login"), {"username": username, "password": password})
        return ET.fromstring(response.content).findtext("token")

    def auth(self):
        return {"HTTP_AUTHORIZATION": "Token " + self.token()}

    def xml(self, response):
        return ET.fromstring(response.content)


class AuthTests(ApiTestBase):
    def test_login_returns_xml_token_for_admin(self):
        response = self.client.post(reverse("api_login"), {"username": "boss", "password": "admin-pass-1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("xml", response["Content-Type"])
        self.assertEqual(len(self.xml(response).findtext("token")), 40)

    def test_wrong_password_rejected(self):
        response = self.client.post(reverse("api_login"), {"username": "boss", "password": "nope"})
        self.assertEqual(response.status_code, 401)

    def test_non_admin_cannot_log_in(self):
        response = self.client.post(reverse("api_login"), {"username": "stud", "password": "pass12345"})
        self.assertEqual(response.status_code, 403)

    def test_endpoints_need_token(self):
        self.assertEqual(self.client.get(reverse("api_users")).status_code, 401)
        bad = self.client.get(reverse("api_users"), HTTP_AUTHORIZATION="Token wrong")
        self.assertEqual(bad.status_code, 401)

    def test_responses_are_never_json(self):
        response = self.client.get(reverse("api_users"), **self.auth())
        self.assertNotIn("json", response["Content-Type"])


class UserApprovalTests(ApiTestBase):
    def test_list_pending_tutors(self):
        response = self.client.get(reverse("api_users"), {"status": "pending"}, **self.auth())
        usernames = [u.findtext("username") for u in self.xml(response)]
        self.assertEqual(usernames, ["tut"])

    def test_approve_and_reject(self):
        auth = self.auth()
        self.client.post(reverse("api_user_approve", args=[self.tutor.pk]), **auth)
        self.tutor.profile.refresh_from_db()
        self.assertEqual(self.tutor.profile.approval_status, Profile.STATUS_APPROVED)

        self.client.post(reverse("api_user_reject", args=[self.tutor.pk]), **auth)
        self.tutor.profile.refresh_from_db()
        self.assertEqual(self.tutor.profile.approval_status, Profile.STATUS_REJECTED)

    def test_students_cannot_be_approved(self):
        response = self.client.post(reverse("api_user_approve", args=[self.student_user.pk]), **self.auth())
        self.assertEqual(response.status_code, 404)


class SubjectCrudTests(ApiTestBase):
    def test_full_crud(self):
        auth = self.auth()
        created = self.client.post(reverse("api_subjects"), {"name": "Physics", "description": "Motion"}, **auth)
        self.assertEqual(created.status_code, 201)
        pk = self.xml(created).findtext("id")

        listing = self.client.get(reverse("api_subjects"), **auth)
        self.assertEqual([s.findtext("name") for s in self.xml(listing)], ["Physics"])

        updated = self.client.put(
            reverse("api_subject_detail", args=[pk]), "name=Physics+101&description=Forces",
            content_type="application/x-www-form-urlencoded", **auth)
        self.assertEqual(self.xml(updated).findtext("name"), "Physics 101")

        deleted = self.client.delete(reverse("api_subject_detail", args=[pk]), **auth)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(Subject.objects.exists())

    def test_validation_errors_are_xml(self):
        response = self.client.post(reverse("api_subjects"), {"name": ""}, **self.auth())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.xml(response).tag, "errors")


class SessionCrudAndStatsTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.tutor.profile.approval_status = Profile.STATUS_APPROVED
        self.tutor.profile.save()
        self.subject = Subject.objects.create(name="Mathematics")

    def session_data(self, **extra):
        data = {
            "tutor": self.tutor.pk, "subject": self.subject.pk, "topic": "Algebra",
            "date": (timezone.localdate() + timedelta(days=3)).isoformat(), "start_time": "15:00",
            "duration_minutes": 90, "slots": 3, "status": "open", "location": "Room 5",
        }
        data.update(extra)
        return data

    def test_create_update_delete_session(self):
        auth = self.auth()
        created = self.client.post(reverse("api_sessions"), self.session_data(), **auth)
        self.assertEqual(created.status_code, 201)
        pk = self.xml(created).findtext("id")

        body = "&".join(f"{k}={v}" for k, v in self.session_data(slots=5).items())
        updated = self.client.put(reverse("api_session_detail", args=[pk]), body,
                                  content_type="application/x-www-form-urlencoded", **auth)
        self.assertEqual(self.xml(updated).findtext("slots"), "5")

        self.client.delete(reverse("api_session_detail", args=[pk]), **auth)
        self.assertFalse(TutoringSession.objects.exists())

    def test_pending_tutor_cannot_own_session(self):
        self.tutor.profile.approval_status = Profile.STATUS_PENDING
        self.tutor.profile.save()
        response = self.client.post(reverse("api_sessions"), self.session_data(), **self.auth())
        self.assertEqual(response.status_code, 400)

    def test_subject_with_sessions_cannot_be_deleted(self):
        auth = self.auth()
        self.client.post(reverse("api_sessions"), self.session_data(), **auth)
        response = self.client.delete(reverse("api_subject_detail", args=[self.subject.pk]), **auth)
        self.assertEqual(response.status_code, 409)

    def test_statistics(self):
        done = TutoringSession.objects.create(
            tutor=self.tutor, subject=self.subject, date=timezone.localdate(),
            start_time="09:00", duration_minutes=90, slots=2, status=TutoringSession.STATUS_COMPLETED)
        booking = Booking.objects.create(
            student=self.student_user, session=done, status=Booking.STATUS_ATTENDED)
        Feedback.objects.create(booking=booking, rating=5, comment="Great")

        root = self.xml(self.client.get(reverse("api_stats"), **self.auth()))
        self.assertEqual(root.findtext("tutoring_hours/total_hours"), "1.5")
        self.assertEqual(root.findtext("sessions_per_subject/subject/sessions"), "1")
        self.assertEqual(root.findtext("top_tutors/tutor/average_rating"), "5.0")
        self.assertEqual(root.findtext("totals/feedback"), "1")

    def test_bookings_list(self):
        session = TutoringSession.objects.create(
            tutor=self.tutor, subject=self.subject, date=timezone.localdate(),
            start_time="09:00", slots=2)
        Booking.objects.create(student=self.student_user, session=session)
        root = self.xml(self.client.get(reverse("api_bookings"), **self.auth()))
        self.assertEqual(root[0].findtext("student"), "stud")
