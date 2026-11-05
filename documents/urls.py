from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.document_list, name="home"),
    path("documents/upload/", views.document_upload, name="document_upload"),
    path("documents/<uuid:pk>/", views.document_detail, name="document_detail"),
    path("documents/<uuid:pk>/download/", views.document_download, name="document_download"),
    path("documents/<uuid:pk>/edit/", views.document_edit, name="document_edit"),
    path("documents/<uuid:pk>/delete/", views.document_delete, name="document_delete"),
    path("documents/<uuid:pk>/share/", views.document_share, name="document_share"),
    path("documents/<uuid:pk>/revoke/<int:grant_id>/", views.document_revoke, name="document_revoke"),
    path("activity/", include("audit.urls")),
]
