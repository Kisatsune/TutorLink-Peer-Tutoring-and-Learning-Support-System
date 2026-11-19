from django.contrib import admin

from .models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
