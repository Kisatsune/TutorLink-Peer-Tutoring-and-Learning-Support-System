from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="api_login"),
    path("logout/", views.logout_view, name="api_logout"),
    path("users/", views.users_list, name="api_users"),
    path("users/<int:pk>/approve/", views.user_approval, {"decision": "approved"}, name="api_user_approve"),
    path("users/<int:pk>/reject/", views.user_approval, {"decision": "rejected"}, name="api_user_reject"),
    path("subjects/", views.subjects_collection, name="api_subjects"),
    path("subjects/<int:pk>/", views.subject_detail, name="api_subject_detail"),
    path("sessions/", views.sessions_collection, name="api_sessions"),
    path("sessions/<int:pk>/", views.session_detail, name="api_session_detail"),
    path("bookings/", views.bookings_list, name="api_bookings"),
    path("stats/", views.stats, name="api_stats"),
]
