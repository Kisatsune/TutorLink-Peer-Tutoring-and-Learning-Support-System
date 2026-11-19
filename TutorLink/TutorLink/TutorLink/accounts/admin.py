from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "course", "year_level", "approval_status")
    list_filter = ("role", "approval_status")
    search_fields = ("user__username", "user__first_name", "user__last_name", "course")
