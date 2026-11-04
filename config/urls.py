from django.urls import include, path

from accounts import views as account_views

urlpatterns = [
    path("", account_views.home, name="home"),
    path("accounts/", include("django.contrib.auth.urls")),
]
