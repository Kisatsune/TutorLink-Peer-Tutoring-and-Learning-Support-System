from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # sessions
    path("sessions/new/", views.session_create, name="session_create"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    path("sessions/<int:pk>/complete/", views.session_complete, name="session_complete"),
    path("sessions/<int:pk>/book/", views.book_session, name="book_session"),
    # bookings & feedback
    path("bookings/<int:pk>/cancel/", views.cancel_booking, name="cancel_booking"),
    path("bookings/<int:booking_pk>/feedback/", views.feedback_create, name="feedback_create"),
]
