"""Small, authenticated account-management workflows."""

from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .password_forms import AccountPasswordChangeForm, AdminSetPasswordForm, PasswordResetUserForm
from .views import _require_admin


@sensitive_post_parameters()
@never_cache
@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def change_password(request):
    form = AccountPasswordChangeForm(request.user, data=request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed. You are still signed in.")
        return redirect("profile")
    return render(request, "projects/password_change.html", {"form": form})


def _resettable_users(admin):
    users = get_user_model().objects.filter(is_active=True).exclude(pk=admin.pk)
    # C-LARA staff can administer accounts, but must not acquire a Django
    # superuser's broader permissions by choosing that user's password.
    if not admin.is_superuser:
        users = users.filter(is_superuser=False)
    return users.order_by("username")


@never_cache
@login_required
@require_http_methods(["GET"])
def password_reset_users(request):
    _require_admin(request.user)
    form = PasswordResetUserForm(request.GET or None, users=_resettable_users(request.user))
    if form.is_bound and form.is_valid():
        return redirect("admin-reset-password", user_id=form.cleaned_data["user"].pk)
    return render(request, "projects/password_reset_users.html", {"form": form})


@sensitive_post_parameters()
@never_cache
@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def reset_user_password(request, user_id):
    _require_admin(request.user)
    target = get_object_or_404(_resettable_users(request.user), pk=user_id)
    form = AdminSetPasswordForm(target, data=request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.save(update_fields=["password"])
            LogEntry.objects.create(
                user_id=request.user.pk,
                content_type=ContentType.objects.get_for_model(user),
                object_id=str(user.pk),
                object_repr=user.get_username(),
                action_flag=CHANGE,
                change_message="Password reset using C-LARA admin tools.",
            )
        messages.success(request, f"Password reset for {target.get_username()}. They can now sign in with the new password.")
        return redirect("admin-password-reset-users")
    return render(request, "projects/password_reset.html", {"form": form, "target_user": target})
