"""
Task scheduling and management utilities for periodic tasks and scheduling.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIRequest
from django_celery_beat.models import PeriodicTask

from accounts.models import Tenant, PaymentPlan
from main.exceptions import PlanScheduleLimitationException

logger = logging.getLogger(__name__)
User = get_user_model()


def task_name(user: User) -> str:
    """Get the task name for a user.

    Args:
        user: The user object.

    Returns:
        The task name string.
    """
    return f"task_tenant_{user.tenant.id}"


def periodic_task_exists(request: WSGIRequest) -> bool:
    """Checks for the existence of a periodic task with the given name.

    Args:
        request: The WSGI request object.

    Returns:
        True if the task exists, False otherwise.
    """
    try:
        PeriodicTask.objects.get(
            name=task_name(request),
        )
        return True
    except PeriodicTask.DoesNotExist:
        return False


def get_interval_russian_translation(periodic_task: PeriodicTask) -> str:
    """
    Translates the interval of a periodic task into Russian.

    It takes into account the grammatical rules of the Russian language for numbers and units of time.
    The function supports translation for seconds, minutes, hours, and days.

    Args:
        periodic_task (PeriodicTask): The periodic task object which contains the interval to be translated.

    Returns:
        str: A string in Russian that represents the interval of the periodic task.
             The string is in the format: "{every} {time_unit_number} {time_unit_name}" (e.g. "каждые 25 минут")
    """
    time_unit_number: int = periodic_task.interval.every
    time_unit_name: str = periodic_task.interval.period

    translations = {
        "seconds": ["секунду", "секунды", "секунд"],
        "minutes": ["минуту", "минуты", "минут"],
        "hours": ["час", "часа", "часов"],
        "days": ["день", "дня", "дней"],
    }

    every = "каждые"

    # 1, 21, 31, etc
    if time_unit_number % 10 == 1 and time_unit_number % 100 != 11:
        every = "каждую" if time_unit_name in ["seconds", "minutes"] else "каждый"
        time_unit_name = translations[time_unit_name][0]

    # 2-4, 22-24, 32-34, etc, excluding numbers ending in 12-14 (e.g. 12-14, 112-114, etc)
    elif 2 <= time_unit_number % 10 <= 4 and (time_unit_number % 100 < 12 or time_unit_number % 100 > 14):
        time_unit_name = translations[time_unit_name][1]

    else:
        time_unit_name = translations[time_unit_name][2]

    if time_unit_number == 1:
        return f"{every} {time_unit_name}"
    else:
        return f"{every} {time_unit_number} {time_unit_name}"


def check_plan_schedule_limitations(tenant: Tenant, period: str, interval: int) -> None:
    """Checks if the user has violated the plan limitations.

    Args:
        tenant: The tenant object.
        period: The time unit (e.g., "hours", "days")
        interval: The interval value (e.g., 7, 24, 48)

    Raises:
        PlanScheduleLimitationException: If the user has violated the plan limitations.
    """
    # Currently, we only have schedule limitations for the FREE plan
    if tenant.payment_plan.name == PaymentPlan.PlanName.FREE.value:
        if period == "hours" and interval < 24:
            raise PlanScheduleLimitationException(
                tenant,
                plan=tenant.payment_plan.name,
                period=period,
                interval=interval,
                message="Ограничения бесплатного тарифа. Установите интервал не менее 24 часов",
            )
