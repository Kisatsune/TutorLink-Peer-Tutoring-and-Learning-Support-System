"""Root URL configuration: web pages, accounts, and the XML API for the Tkinter dashboard."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),          # XML API used by the Tkinter dashboard
    path("accounts/", include("accounts.urls")),  # register / login / logout
    path("", include("tutoring.urls")),         # student & tutor web app
]
