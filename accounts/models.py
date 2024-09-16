import logging

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from config import DEMO_USER_HOURS_ALLOWED, DEFAULT_QUOTAS, PlanType

logger = logging.getLogger(__name__)


class TenantQuota(models.Model):
    class QuotaName(models.TextChoices):
        TEST = "0", _("КВОТА ТЕСТОВАЯ")
        FREE = "1", _("КВОТА БЕСПЛАТНАЯ")
        BUSINESS = "2", _("КВОТА БИЗНЕС")
        PRO = "3", _("КВОТА ПРОФЕССИОНАЛ")
        CORPORATE = "4", _("КВОТА КОРПОРАТИВНАЯ")

    name = models.CharField(max_length=255, choices=QuotaName.choices, blank=True, null=True)
    total_hours_allowed = models.PositiveIntegerField(default=24 * 60, blank=True, null=True)
    skus_limit = models.PositiveIntegerField(default=10, blank=True, null=True)
    parse_units_limit = models.PositiveIntegerField(default=10, blank=True, null=True)

    class Meta:
        verbose_name = "Квота"
        verbose_name_plural = "Квоты"

    # @classmethod
    # def get_default_quota(cls) -> "TenantQuota":
    #     quota, created = TenantQuota.objects.get_or_create(
    #         name=PlanType.FREE.value,
    #         defaults={
    #             "total_hours_allowed": DEFAULT_QUOTAS[PlanType.FREE]["total_hours_allowed"],
    #             "skus_limit": DEFAULT_QUOTAS[PlanType.FREE]["skus_limit"],
    #             "parse_units_limit": DEFAULT_QUOTAS[PlanType.FREE]["parse_units_limit"],
    #         },
    #     )
    #     return quota

    @classmethod
    def get_quota(cls, plan: str):
        quota, created = TenantQuota.objects.get_or_create(
            name=plan,
            defaults={
                "total_hours_allowed": DEFAULT_QUOTAS[plan]["total_hours_allowed"],
                "skus_limit": DEFAULT_QUOTAS[plan]["skus_limit"],
                "parse_units_limit": DEFAULT_QUOTAS[plan]["parse_units_limit"],
            },
        )
        return quota

    @classmethod
    def get_default_quota(cls):
        return cls.get_quota(plan=PlanType.FREE.value)

    def __str__(self):
        return f"{self.name} - {self.get_name_display()}"


class PaymentPlan(models.Model):
    class PlanName(models.TextChoices):
        """
        Plan names for the payment plans. To get the readable name, use payment_plan.get_name_display()
        To compare plan names:
        if payment_plan.name == PaymentPlan.PlanName.FREE
        """

        TEST = "0", _("ПЛАН ТЕСТОВЫЙ")
        FREE = "1", _("ПЛАН БЕСПЛАТНЫЙ")
        BUSINESS = "2", _("ПЛАН БИЗНЕС")
        PRO = "3", _("ПЛАН ПРОФЕССИОНАЛ")
        CORPORATE = "4", _("ПЛАН КОРПОРАТИВНЫЙ")

    name = models.CharField(max_length=20, choices=PlanName.choices)
    quotas = models.ForeignKey(TenantQuota, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    @classmethod
    def get_default_payment_plan(cls) -> "PaymentPlan":
        plan, created = cls.objects.get_or_create(name=cls.PlanName.FREE)
        return plan

    def __str__(self):
        return f"{self.name} - {self.get_name_display()}"  # pragma: no cover


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
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    quota = models.ForeignKey(
        TenantQuota,
        on_delete=models.SET_NULL,
        default=TenantQuota.get_default_quota,
        related_name="tenants",
        null=True,
        blank=True,
    )
    billing_start_date = models.DateField(blank=True, null=True)

    price_change_threshold = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.00, help_text="Процент изменения цены для уведомлений (напр, 5.00%)"
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

    @transaction.atomic
    def switch_plan(self, new_plan: str) -> None:
        """
        Switches the tenant's payment plan to the specified plan.

        Args:
            new_plan (str): The name of the new plan to switch to.

        Raises:
            DoesNotExist: If the specified plan does not exist.
            ValueError: If an invalid plan is provided.
        """
        try:
            new_plan = PaymentPlan.objects.get(name=new_plan)
        except PaymentPlan.DoesNotExist:
            logger.error("Attempted to switch to non-existent plan: %s", new_plan)
            raise ValueError(f"Invalid plan: {new_plan}") from None

        old_plan_name = self.payment_plan.get_name_display()
        logger.info("Switching plan from '%s' to '%s'", old_plan_name, new_plan.get_name_display())

        self.payment_plan = new_plan
        self._update_quota_for_plan(new_plan)
        self.save()
        logger.info("Successfully switched plan for tenant '%s' to '%s'", self.name, new_plan.get_name_display())

    def _update_quota_for_plan(self, new_plan) -> None:
        """
        Update the tenant's quota based on the new payment plan.

        Args:
            new_plan (PaymentPlan): The new plan object.
        """
        if new_plan.name == PaymentPlan.PlanName.FREE.value:
            self.quota = TenantQuota.get_default_quota()  # Default quota for free plans
        else:
            self.quota = TenantQuota.get_quota(plan=new_plan.name)


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
        return timezone.now() > (self.created_at + timezone.timedelta(hours=DEMO_USER_HOURS_ALLOWED))

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
