import os
from datetime import timedelta

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mp_monitor.settings")

app = Celery("mp_monitor")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html#entries
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls the function every 1 hour
    sender.add_periodic_task(timedelta(hours=1), check_expired_demo_users, name="Check expired demo users")


# Setting this to no cover because accounts.views.check_expired_demo_users is a mirror of this task
# and is covered by tests
@app.task
def check_expired_demo_users():  # pragma: no cover
    """
    Checks if any demo users are expired and deletes the corresponding periodic tasks, deactivates the user and
    the parser for all items belonging to the user.
    Duplicate of accounts.views.check_expired_demo_users
    """
    import logging
    from django_celery_beat.models import PeriodicTask
    from django.contrib.auth import get_user_model
    from main.models import Item
    from main.utils import task_name
    from django.db import transaction

    logger = logging.getLogger(__name__)
    user = get_user_model()

    print("Checking expired demo users...")
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


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")  # pragma: no cover
