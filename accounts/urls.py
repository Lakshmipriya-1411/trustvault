from django.urls import path

from . import views

urlpatterns = [
    path("", views.user_list, name="user_list"),
    path("new/", views.user_create, name="user_create"),
    path("<int:pk>/toggle/", views.user_toggle, name="user_toggle"),
]
