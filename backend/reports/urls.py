from django.urls import path

from . import views

urlpatterns = [
    # Reporting (anonymous)
    path("reports/", views.ReportCreateView.as_view(), name="report-create"),
    path("reports/track/<str:receipt_code>/", views.ReportTrackView.as_view(), name="report-track"),
    # Auth
    path("auth/login/", views.LoginView.as_view(), name="login"),
    # Reviewer
    path("review/reports/", views.ReviewerReportListView.as_view(), name="review-list"),
    path("review/reports/<int:pk>/", views.ReviewerReportDetailView.as_view(), name="review-detail"),
    path("review/attachments/<int:pk>/", views.AttachmentDownloadView.as_view(), name="attachment"),
    # Public
    path("public/reports/", views.PublicReportListView.as_view(), name="public-reports"),
    path("public/stats/", views.PublicStatsView.as_view(), name="public-stats"),
    path("meta/", views.MetaView.as_view(), name="meta"),
    path("health/", views.HealthView.as_view(), name="health"),
]
