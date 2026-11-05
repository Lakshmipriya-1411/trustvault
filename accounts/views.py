from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit import service as audit

from .decorators import role_required
from .forms import NewUserForm, ThrottledAuthenticationForm
from .models import User


class LoginView(auth_views.LoginView):
    authentication_form = ThrottledAuthenticationForm
    redirect_authenticated_user = True


@role_required(User.Role.ADMIN)
def user_list(request):
    return render(request, "accounts/user_list.html", {"users": User.objects.order_by("username")})


@role_required(User.Role.ADMIN)
def user_create(request):
    form = NewUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        user = User.objects.create_user(data["username"], password=data["password"], role=data["role"])
        audit.log(request, "user_created", target=user.username, detail=f"role={user.role}")
        messages.success(request, f"Created {user.username}.")
        return redirect("user_list")
    return render(request, "accounts/user_new.html", {"form": form})


@role_required(User.Role.ADMIN)
@require_POST
def user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("user_list")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])  # takes effect on the user's very next request
    audit.log(request, "user_activated" if user.is_active else "user_deactivated", target=user.username)
    messages.success(request, f"{user.username} is now {'active' if user.is_active else 'deactivated'}.")
    return redirect("user_list")
