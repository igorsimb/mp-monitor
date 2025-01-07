import logging
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.templatetags.static import static
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

        TEST = "0", _("ТЕСТОВЫЙ")
        FREE = "1", _("БЕСПЛАТНЫЙ")
        BUSINESS = "2", _("БИЗНЕС")
        PRO = "3", _("ПРОФЕССИОНАЛ")
        CORPORATE = "4", _("КОРПОРАТИВНЫЙ")

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
        For plan names see class PlanName.

        Args:
            new_plan (str): The name of the new plan to switch to.

        Raises:
            DoesNotExist: If the specified plan does not exist.
            ValueError: If an invalid plan is provided.

        :Example:
            tenant.switch_plan("2")
            Switching plan to PaymentPlan.PlanName.BUSINESS
        """
        try:
            new_plan = PaymentPlan.objects.get(name=new_plan)
        except PaymentPlan.DoesNotExist:
            logger.error("Attempted to switch to non-existent plan: %s", new_plan)
            raise ValueError(f"Invalid plan: {new_plan}") from None

        if self.payment_plan == new_plan:
            logger.info("Plan is already set to %s", new_plan.get_name_display())
            return

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

    def add_to_balance(self, amount: Decimal) -> None:
        """
        Add the given amount to the tenant's balance. Only allows positive amounts.
        """
        if amount < 0:
            raise ValueError("Cannot add a negative amount to the balance.")
        self.balance += amount
        self.save()

    def deduct_from_balance(self, amount: Decimal) -> None:
        """
        Deduct the given amount from the tenant's balance, ensuring the balance doesn't go negative.
        """
        if amount < 0:
            raise ValueError("Cannot deduct a negative amount from the balance.")
        if self.balance < amount:
            raise ValueError("Insufficient balance to deduct the requested amount.")
        self.balance -= amount
        self.save()


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
        if not self.tenant:
            # django-guardian creates AnonymousUser by default, setting status to CANCELED for now until
            # https://github.com/igorsimb/mp-monitor/issues/73 is resolved
            if self.username == "AnonymousUser":
                tenant, created = Tenant.objects.get_or_create(
                    name="django_guardian_tenant", defaults={"status": TenantStatus.CANCELED}
                )
                self.tenant = tenant
                # If tenant already exists, return
                if not created:
                    return
            else:
                self.tenant = Tenant.objects.create(name=f"{self.email}_{Tenant.objects.count() + 1}")
        super().save(*args, **kwargs)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="avatars/", null=True, blank=True)
    display_name = models.CharField(max_length=40, null=True, blank=True)
    info = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.user)

    @property
    def name(self):
        if self.display_name:
            name = self.display_name
        else:
            name = self.user.username
        return name

    @property
    def avatar(self):
        if self.image:
            return self.image.url
        return static("img/blank_avatar.svg")
