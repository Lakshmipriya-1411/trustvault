from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path

from accounts import views as account_views

urlpatterns = [
    path("accounts/login/", login_not_required(account_views.LoginView.as_view()), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("users/", include("accounts.urls")),
    path("", include("documents.urls")),
]
