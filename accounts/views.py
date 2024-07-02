import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django_celery_beat.models import PeriodicTask
from django_htmx.http import HttpResponseClientRedirect

import config
from main.models import Item
from main.utils import task_name, create_demo_user, create_demo_items, no_active_demo_user, set_tenant_quota

logger = logging.getLogger(__name__)
user = get_user_model()


def logout_view(request):
    logout(request)
    next_url = request.GET.get("next")
    if next_url:  # if template contains "next"
        return redirect(next_url)
    return redirect("index")


@user_passes_test(no_active_demo_user, redirect_field_name="item_list")
@transaction.atomic
def demo_view(request) -> HttpResponse | HttpResponseRedirect:
    """
    Creates a demo user and logs them in.
    Demo is expired after DEMO_USER_EXPIRATION_HOURS hours (see accounts/models.py).
    """
    try:
        demo_user, password_uuid = create_demo_user()
        set_tenant_quota(tenant=demo_user.tenant)
        demo_items = create_demo_items(demo_user)
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
