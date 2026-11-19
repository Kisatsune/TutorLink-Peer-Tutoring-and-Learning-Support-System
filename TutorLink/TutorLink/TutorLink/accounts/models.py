from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extra information attached to every Django User: role, course, year level.

    Tutors must be approved by an administrator (through the Tkinter dashboard)
    before they are allowed to post sessions.
    """

    ROLE_STUDENT = "student"
    ROLE_TUTOR = "tutor"
    ROLE_CHOICES = [
        (ROLE_STUDENT, "Student"),
        (ROLE_TUTOR, "Tutor"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    course = models.CharField(max_length=100, blank=True)
    year_level = models.PositiveSmallIntegerField(default=1)
    approval_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_APPROVED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == self.ROLE_STUDENT

    @property
    def is_tutor(self):
        return self.role == self.ROLE_TUTOR

    @property
    def can_post_sessions(self):
        """Only approved tutors may post sessions."""
        return self.is_tutor and self.approval_status == self.STATUS_APPROVED
