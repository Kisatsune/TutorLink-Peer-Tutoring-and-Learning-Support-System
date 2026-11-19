"""Create demo data for the video demonstration: python manage.py seed_demo

Plain Python (no fixture files), safe to run more than once.
"""
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile
from tutoring.models import Booking, Feedback, Subject, TutoringSession

User = get_user_model()

ADMIN_PASSWORD = "admin12345"
DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Create demo users, subjects, sessions, bookings, and feedback."

    def make_user(self, username, first, last, role, course, year, status):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com"},
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        Profile.objects.update_or_create(
            user=user,
            defaults={"role": role, "course": course, "year_level": year, "approval_status": status},
        )
        return user

    def handle(self, *args, **options):
        today = timezone.localdate()

        # Administrator (used to log in to the Tkinter dashboard)
        admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@example.com"}
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password(ADMIN_PASSWORD)
        admin_user.save()

        subjects = {}
        for name, description in [
            ("Mathematics", "Algebra, geometry, trigonometry, and calculus."),
            ("Programming", "Python, algorithms, and problem solving."),
            ("English", "Grammar, academic writing, and reading comprehension."),
            ("Science", "General science, physics, and chemistry basics."),
        ]:
            subjects[name], _ = Subject.objects.get_or_create(
                name=name, defaults={"description": description}
            )

        approved, pending = Profile.STATUS_APPROVED, Profile.STATUS_PENDING
        maria = self.make_user("maria_t", "Maria", "Santos", Profile.ROLE_TUTOR, "BS Mathematics", 4, approved)
        john = self.make_user("john_t", "John", "Reyes", Profile.ROLE_TUTOR, "BS Computer Science", 3, approved)
        self.make_user("ana_t", "Ana", "Cruz", Profile.ROLE_TUTOR, "BSE English", 3, pending)  # waits for admin
        paolo = self.make_user("paolo_s", "Paolo", "Garcia", Profile.ROLE_STUDENT, "BS Information Technology", 1, approved)
        lea = self.make_user("lea_s", "Lea", "Mendoza", Profile.ROLE_STUDENT, "BSE Mathematics", 2, approved)

        def session(tutor, subject, days, start, topic, slots, status, minutes=60):
            obj, _ = TutoringSession.objects.get_or_create(
                tutor=tutor,
                subject=subjects[subject],
                date=today + timedelta(days=days),
                start_time=start,
                defaults={
                    "topic": topic,
                    "slots": slots,
                    "status": status,
                    "duration_minutes": minutes,
                    "location": "Library Room 2",
                },
            )
            return obj

        done = TutoringSession.STATUS_COMPLETED
        open_ = TutoringSession.STATUS_OPEN
        past_math = session(maria, "Mathematics", -3, time(15, 0), "Quadratic equations", 3, done, 90)
        past_prog = session(john, "Programming", -2, time(16, 0), "Python loops and functions", 3, done)
        session(maria, "Mathematics", 2, time(14, 0), "Intro to derivatives", 4, open_)
        session(john, "Programming", 3, time(15, 30), "Debugging with print and the debugger", 3, open_)
        session(john, "Programming", 5, time(10, 0), "Django basics", 2, open_, 120)

        # Past sessions: students attended and rated them.
        for student, sess, rating, comment in [
            (paolo, past_math, 5, "Maria explained every step clearly."),
            (lea, past_math, 4, "Very helpful, I finally understand factoring."),
            (paolo, past_prog, 5, "John made loops easy to follow."),
        ]:
            booking, _ = Booking.objects.get_or_create(
                student=student, session=sess, defaults={"status": Booking.STATUS_ATTENDED}
            )
            Feedback.objects.get_or_create(
                booking=booking, defaults={"rating": rating, "comment": comment}
            )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(f"  Admin (Tkinter dashboard): admin / {ADMIN_PASSWORD}")
        self.stdout.write(f"  Tutors: maria_t, john_t (approved), ana_t (pending) / {DEMO_PASSWORD}")
        self.stdout.write(f"  Students: paolo_s, lea_s / {DEMO_PASSWORD}")
