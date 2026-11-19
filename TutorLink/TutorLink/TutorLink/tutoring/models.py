from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TutoringSession(models.Model):
    
    STATUS_OPEN = "open"
    STATUS_FULL = "full"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_FULL, "Full"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutoring_sessions"
    )
    # PROTECT: a subject that still has sessions cannot be deleted by accident.
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="sessions")
    topic = models.CharField(max_length=150, blank=True, help_text="What will be covered?")
    date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(15), MaxValueValidator(480)]
    )
    slots = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    location = models.CharField(
        max_length=150, blank=True, help_text="Room or online meeting link"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.subject} on {self.date} by {self.tutor.username}"

    # slot bookkeeping 
    @property
    def booked_count(self):
        """Number of active (not cancelled) bookings."""
        if hasattr(self, "active_bookings"):  # filled in by annotate() to avoid extra queries
            return self.active_bookings
        return self.bookings.exclude(status=Booking.STATUS_CANCELLED).count()

    @property
    def slots_left(self):
        return max(self.slots - self.booked_count, 0)

    @property
    def duration_hours(self):
        return round(self.duration_minutes / 60, 2)

    def refresh_status(self):
        """Switch between open and full depending on free slots.
        Completed and cancelled sessions never change automatically."""
        if self.status in (self.STATUS_COMPLETED, self.STATUS_CANCELLED):
            return
        new_status = self.STATUS_FULL if self.slots_left <= 0 else self.STATUS_OPEN
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status"])

    def clean(self):
        # A tutor cannot shrink the session below the number of students already booked.
        if self.pk and self.slots is not None and self.slots < self.booked_count:
            raise ValidationError(
                {"slots": f"{self.booked_count} students are already booked; slots cannot be lower."}
            )


class Booking(models.Model):
    STATUS_BOOKED = "booked"
    STATUS_CANCELLED = "cancelled"
    STATUS_ATTENDED = "attended"
    STATUS_CHOICES = [
        (STATUS_BOOKED, "Booked"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_ATTENDED, "Attended"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    session = models.ForeignKey(
        TutoringSession, on_delete=models.CASCADE, related_name="bookings"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_BOOKED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One booking row per student per session (cancelled ones can be re-activated).
            models.UniqueConstraint(fields=["student", "session"], name="unique_student_session"),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.session} ({self.status})"


class Feedback(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="feedback")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}/5 for {self.booking.session}"
