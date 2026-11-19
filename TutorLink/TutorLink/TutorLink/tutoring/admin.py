from django.contrib import admin

from .models import Booking, Feedback, Subject, TutoringSession


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(TutoringSession)
class TutoringSessionAdmin(admin.ModelAdmin):
    list_display = ("subject", "tutor", "date", "start_time", "slots", "status")
    list_filter = ("status", "subject")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "status", "created_at")
    list_filter = ("status",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("booking", "rating", "created_at")
