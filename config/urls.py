from django.http import HttpResponse
from django.urls import include, path


def home(request):
    return HttpResponse("TrustVault is running")


urlpatterns = [
    path("", home),
    path("accounts/", include("django.contrib.auth.urls")),
]
