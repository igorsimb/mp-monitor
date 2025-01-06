import logging

from allauth.account.utils import send_email_confirmation
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test, login_required
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django_celery_beat.models import PeriodicTask
from django_htmx.http import HttpResponseClientRedirect

import config
from accounts.forms import ProfileForm, EmailChangeForm
from main.models import Item
from utils import demo
from utils.billing import set_tenant_quota
from utils.task_utils import task_name

logger = logging.getLogger(__name__)
user = get_user_model()


def logout_view(request):
    logout(request)
    next_url = request.GET.get("next")
    if next_url:  # if template contains "next"
        return redirect(next_url)
    return redirect("index")


@user_passes_test(demo.no_active_demo_user, redirect_field_name="item_list")
@transaction.atomic
def demo_view(request) -> HttpResponse | HttpResponseRedirect:
    """
    Creates a demo user and logs them in.
    Demo is expired after DEMO_USER_HOURS_ALLOWED hours (see accounts/models.py).
    """
    try:
        demo_user, password_uuid = demo.create_demo_user()
        set_tenant_quota(tenant=demo_user.tenant)
        demo_items = demo.create_demo_items(demo_user)
        demo_user.tenant.quota.skus_limit = config.DEMO_USER_MAX_ALLOWED_SKUS - len(demo_items)
        demo_user.tenant.quota.save()
    except (IntegrityError, ValidationError):
        return render(request, "account/demo_error.html")
    except Exception as e:
        logger.error("Unexpected error in demo_view: %s", e)
        return render(request, "account/demo_error.html")

    demo_user = authenticate(request, username=demo_user.email, password=password_uuid)
    if demo_user is not None:
        login(request, demo_user, backend="django.contrib.auth.backends.ModelBackend")
    else:
        logger.error("Authentication failed for demo user %s", demo_user.email)
        return render(request, "account/demo_error.html")

    if request.htmx:
        # this is required to make the redirect work properly with htmx's hx-get
        return HttpResponseClientRedirect(reverse("item_list"))
    else:
        return HttpResponseRedirect(reverse("item_list"))


@user_passes_test(lambda u: u.is_superuser)
def check_expired_demo_users(request):
    """
    For superusers only.
    This is a mirror of mp_monitor.celery.check_expired_demo_users celery task. In case manual intervention is needed.
    Checks if any demo users are expired and deletes the corresponding periodic tasks, deactivates the user and
    the parser for all items belonging to the user.
    """
    if request.method == "POST":
        users_to_check = user.objects.filter(is_demo_user=True).filter(is_active=True).select_related("tenant")
        logger.info("Found %s active demo users", users_to_check.count())
        periodic_tasks_to_check = PeriodicTask.objects.filter(name__startswith="task_tenant_")
        users_to_update = []
        tenant_ids_for_items_deletion = []
        periodic_tasks_to_delete = []

        for user_to_check in users_to_check:
            if not user_to_check.is_active_demo_user:
                print(f"Checking if user {user_to_check} has an active periodic task...")

                # look for matching periodic task without querying the database
                matching_task = [task for task in periodic_tasks_to_check if task.name == task_name(user_to_check)]
                if matching_task:
                    tenant_ids_for_items_deletion.append(user_to_check.tenant.id)
                    periodic_tasks_to_delete.append(matching_task[0].id)

                # Update user status in memory
                logger.info("Preparing to deactivate user %s", user_to_check)
                user_to_check.is_demo_active = False
                user_to_check.is_active = False
                users_to_update.append(user_to_check)
            else:
                print(f"Demo not yet expired for {user_to_check} (id={user_to_check.id})")

        with transaction.atomic():
            # Perform bulk delete for items
            if tenant_ids_for_items_deletion:
                Item.objects.filter(tenant_id__in=tenant_ids_for_items_deletion).delete()

            # Perform bulk delete for periodic tasks
            if periodic_tasks_to_delete:
                PeriodicTask.objects.filter(id__in=periodic_tasks_to_delete).delete()

            # Perform bulk update for users
            if users_to_update:
                user.objects.bulk_update(users_to_update, ["is_demo_active", "is_active"])
        logger.info("Bulk update completed for expired demo users.")
    return redirect("index")


@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, "account/profile.html", {"profile": profile})


@login_required
def profile_edit_view(request):
    form = ProfileForm(instance=request.user.profile)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            return redirect("profile")

    if request.path == reverse("profile_onboarding"):
        onboarding = True
    else:
        onboarding = False

    context = {"form": form, "onboarding": onboarding}
    return render(request, "account/profile_edit.html", context)


@login_required
def profile_settings_view(request):
    return render(request, "account/profile_settings.html")


@login_required
def email_change_view(request):
    if request.htmx:
        form = EmailChangeForm(instance=request.user)
        return render(request, "account/partials/email_change_form.html", {"form": form})

    if request.method == "POST":
        form = EmailChangeForm(request.POST, instance=request.user)

        if form.is_valid():
            # Check if the email already exists
            email = form.cleaned_data["email"]
            if user.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.warning(request, "Пользователь с таким email уже существует.")
                return redirect("profile_settings")

            form.save()

            # Then Signal updates the email_address and sets "verified" to False

            # Then send confirmation email
            send_email_confirmation(request, request.user)

            return redirect("profile_settings")
        else:
            messages.warning(
                request, "Ошибка при обновлении email. Попробуйте еще раз или обратитесь к администратору."
            )
            return redirect("profile_settings")

    return redirect("item_list")


@login_required
def email_verify(request):
    """
    Send confirmation email to the user
    """
    send_email_confirmation(request, request.user)
    return redirect("profile_settings")


# WARNING: Deleting the account will cascade delete the associated tenant and all its data
# TODO(multitenancy): Currently safe to delete tenants as they are 1:1 with users.
# When implementing full multitenancy support:
# 1. Ensure tenant names are unique
# 2. Handle shared tenants (users belonging to same tenant)
# 3. Add proper tenant cleanup strategy
@login_required
def profile_delete_view(request):
    user = request.user
    if request.method == "POST":
        logout(request)
        user.tenant.delete()
        messages.success(request, "Аккаунт удалён. Очень жаль!")
        return redirect("index")

    return render(request, "account/profile_delete.html")
