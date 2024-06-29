from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from config import DEMO_USER_EXPIRATION_HOURS
from main.models import PaymentPlan


class TenantManager(models.Manager):
    """A manager to provide custom methods for Tenant"""

    def active(self) -> models.QuerySet:
        """
        Returns only active tenants.
        Can be used in ORM like so: Tenant.objects.active()
        """
        qs = self.get_queryset()
        return qs.filter(status__in=self.model.ACTIVE_STATUSES)  # type: ignore


class TenantStatus(models.IntegerChoices):
    TRIALING = 1, _("Trialing")
    ACTIVE = 2, _("Active")
    EXEMPT = 3, _("Exempt")  # # for using service without paying, e.g. admins, etc
    CANCELED = 4, _("Canceled")
    TRIAL_EXPIRED = 5, _("Trial expired")


class Tenant(models.Model):
    ACTIVE_STATUSES = (
        TenantStatus.TRIALING,
        TenantStatus.ACTIVE,
        TenantStatus.EXEMPT,
    )
    name = models.CharField(max_length=255, unique=True)
    status = models.IntegerField(choices=TenantStatus.choices, default=TenantStatus.ACTIVE)
    # Ensure a tenant cannot be associated with a non-existent payment plan.
    payment_plan = models.ForeignKey(
        PaymentPlan, on_delete=models.SET_NULL, default=PaymentPlan.get_default_payment_plan, null=True
    )
    quota = models.ForeignKey(
        "accounts.TenantQuota", on_delete=models.PROTECT, related_name="tenants", null=True, blank=True
    )

    objects = TenantManager()
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        # speeds up database queries (https://docs.djangoproject.com/en/5.0/ref/models/options/#indexes)
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):  # pylint: disable=invalid-str-returned
        return self.name


# To be used in signals.py. Create a TenantQuota object for each tenant upon creation.
# @receiver(post_save, sender=Tenant)
# def create_tenant_quota(sender, instance, created, **kwargs):  # type: ignore  # pylint: disable=[unused-argument]
#     if created:
#         TenantQuota.objects.create

# To be used in signals.py
# @receiver(post_save, sender=Tenant)
# def set_default_payment_plan(sender, instance, created, **kwargs):  # type: ignore  # pylint: disable=[unused-argument]
#     if created:
#         PaymentPlan.objects.create(name="Free", pa)


class User(AbstractUser):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Организация",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_demo_user = models.BooleanField(default=False)
    is_demo_active = models.BooleanField(default=False)

    @property
    def is_demo_expired(self):
        return timezone.now() > (self.created_at + timezone.timedelta(hours=DEMO_USER_EXPIRATION_HOURS))

    @property
    def is_active_demo_user(self):
        return self.is_demo_user and not self.is_demo_expired

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def save(self, *args, **kwargs):  # type: ignore
        if not self.tenant and self.username != "AnonymousUser":
            self.tenant = Tenant.objects.create(name=self.email)
        # django-guardian creates AnonymousUser by default, setting status to CANCELED for now until
        # https://github.com/igorsimb/mp-monitor/issues/73 is resolved
        elif self.username == "AnonymousUser":
            self.tenant = Tenant.objects.create(status=TenantStatus.CANCELED)
        super().save(*args, **kwargs)


# Add user to the Tenant group upon creation
@receiver(post_save, sender=User)
def add_user_to_group(sender, instance, created, **kwargs):  # type: ignore  # pylint: disable=[unused-argument]
    if instance.is_superuser:
        return
    if created:
        try:
            group, created = Group.objects.get_or_create(name=instance.tenant.name)
            instance.groups.add(group)
        except AttributeError as e:
            print(f"An error occurred: {e}. Tenant does not exist.")
    else:
        old_groups = instance.groups.all()
        new_group, created = Group.objects.get_or_create(name=instance.tenant.name)
        if new_group not in old_groups:
            instance.groups.clear()
            instance.groups.add(new_group)


class TenantQuota(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    total_hours_allowed = models.PositiveIntegerField(default=10, blank=True, null=True)
    skus_limit = models.PositiveIntegerField(default=10, blank=True, null=True)
    manual_updates_limit = models.PositiveIntegerField(default=10, blank=True, null=True)
    scheduled_updates_limit = models.PositiveIntegerField(default=10, blank=True, null=True)
    parse_units_limit = models.PositiveIntegerField(default=10, blank=True, null=True)

    class Meta:
        verbose_name = "Квота"
        verbose_name_plural = "Квоты"

    def __str__(self):
        return self.name if self.name else f"SKUs: {self.skus_limit}, PUs:{self.parse_units_limit}"
