import logging
from datetime import datetime

from _decimal import InvalidOperation, DivisionByZero
from django.contrib.auth.models import Group
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Max, Min, Avg
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from guardian.shortcuts import assign_perm, get_perms

from accounts.models import Tenant

# from notifier.signals import price_updated

logger = logging.getLogger(__name__)


class Item(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=20)
    seller_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        help_text="Цена товара от продавца",
        validators=[MinValueValidator(float("0.00"))],
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        help_text="Цена товара в магазине с учетом СПП",
        validators=[MinValueValidator(float("0.00"))],
    )
    spp = models.IntegerField(null=True, blank=True)
    image = models.URLField(null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    brand = models.CharField(max_length=255, null=True, blank=True)
    seller_name = models.CharField(max_length=255, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    num_reviews = models.IntegerField(null=True, blank=True)
    is_parser_active = models.BooleanField(default=False)
    schedule = models.CharField(max_length=255, null=True, blank=True)
    is_in_stock = models.BooleanField(default=True)
    is_notifier_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

        constraints = [
            models.UniqueConstraint(fields=["tenant", "sku"], name="unique_tenant_sku"),
            models.CheckConstraint(check=models.Q(price__gte=float("0.00")), name="no_negative_price"),
        ]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_item", "Can view item"),)

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self) -> str:
        return reverse("item_detail", kwargs={"slug": self.sku})

    # TODO: test the properties below
    @property
    def max_price(self) -> float:
        # In detail template  {{ item.max_price }}
        return Price.objects.filter(item=self).aggregate(max_price=Max("value"))["max_price"]

    @property
    def max_price_date(self) -> datetime:
        # In detail template  {{ item.max_price_date }}
        max_price = Price.objects.filter(item=self).aggregate(max_price=Max("value"))["max_price"]
        max_price_date = Price.objects.filter(item=self, value=max_price).latest("created_at").created_at
        return max_price_date

    @property
    def min_price(self) -> float:
        # In detail template  {{ item.max_price }}
        return Price.objects.filter(item=self).aggregate(min_price=Min("value"))["min_price"]

    @property
    def avg_price(self) -> int:
        # In detail template  {{ item.avg_price }}
        return int(Price.objects.filter(item=self).aggregate(avg_price=Avg("value"))["avg_price"])

    @property
    def min_price_date(self) -> datetime:
        # In detail template  {{ item.min_price_date }}
        min_price = Price.objects.filter(item=self).aggregate(min_price=Min("value"))["min_price"]
        min_price_date = Price.objects.filter(item=self, value=min_price).latest("created_at").created_at
        return min_price_date

    # def price_percent_change(self) -> float:
    #     # In item list template  {{ item.price_percent_change }}
    #     prices = Price.objects.filter(Q(item=self))
    #     for i in range(len(prices)):
    #         try:
    #             previous_price = prices[i + 1].value
    #             current_price = prices[i].value
    #             percent_change = ((current_price - previous_price) / previous_price) * 100
    #             prices[i].percent_change = round(percent_change, 2)
    #             return prices[i].percent_change
    #         except (IndexError, InvalidOperation, DivisionByZero):
    #             prices[i].percent_change = 0
    #         except TypeError:
    #             logger.warning("Can't compare price to NoneType")

    def price_percent_change(self) -> float:
        """
        Calculates the percentage change in price for the item and compares it to the tenant's price_change_threshold.

        Returns:
            float: The percentage change in price.
        """
        prices = Price.objects.filter(Q(item=self)).order_by("-created_at")

        # Check if there are at least two price records to calculate a percent change
        if prices.count() < 2:
            return 0.0

        try:
            current_price = prices[0].value
            previous_price = prices[1].value

            percent_change = ((current_price - previous_price) / previous_price) * 100

            # Get tenant-specific threshold, default to 0
            threshold = self.tenant.price_change_threshold or 0.00

            # If the change exceeds the threshold, return it
            if abs(percent_change) >= threshold:
                return round(percent_change, 2)
            return 0.0
        except (InvalidOperation, DivisionByZero, TypeError) as e:
            logger.warning("Error calculating price percent change: %s", e)
            return 0.0

    def save(self, *args, **kwargs):  # type: ignore
        super().save(*args, **kwargs)
        Price.objects.create(item=self, value=self.price)
        # Trigger the custom signal after creating the Price, so that check_price_change works with the updated price
        # Without it, the signal would be triggered before the Price is created, and hence work with the old price
        from notifier.signals import price_updated  # Local import to avoid circular import

        price_updated.send(sender=self.__class__, instance=self)


# TODO: move to signals.py
# Having post_save signal solves "Object needs to be persisted first" if adding perms on save, resulting in failure to
# add a scraped item to db. This is because Django adds ManyToMany related fields after saving.
# Source: https://stackoverflow.com/a/23772575
@receiver(post_save, sender=Item)
def add_perms_to_group(sender, instance, created, **kwargs) -> None:  # type: ignore # pylint: disable=unused-argument
    group, created = Group.objects.get_or_create(name=instance.tenant)
    if not group.permissions.filter(codename="view_item").exists():
        logger.info(
            "Adding 'view_item' permission for item '%s' to group '%s'",
            instance.name,
            group.name,
        )
        assign_perm("view_item", group, instance)
        # get_perms: https://django-guardian.readthedocs.io/en/stable/userguide/check.html#get-perms
        if "view_item" not in get_perms(group, instance):
            logger.error(
                "Failed to add 'view_item' permission for item '%s' to group '%s'",
                instance.name,
                group.name,
            )


class Schedule(models.Model):
    class Period(models.TextChoices):
        SECONDS = "seconds", _("Секунды")
        MINUTES = "minutes", _("Минуты")
        HOURS = "hours", _("Часы")
        DAYS = "days", _("Дни")

    type = models.CharField(
        max_length=50,
        verbose_name="Тип расписания",
        default="interval",
        choices=[("interval", "Интервал"), ("cronjob", "CronJob")],
    )
    # TODO: https://github.com/igorsimb/mp-monitor/issues/195
    interval_value = models.IntegerField(
        verbose_name="Каждые", validators=[MinValueValidator(1)], blank=True, null=True
    )
    cronjob_value = models.CharField(max_length=100, verbose_name="CronJob", blank=True, null=True)
    period = models.CharField(max_length=100, choices=Period.choices, default=Period.HOURS, blank=True)


class Price(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")
    value = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        validators=[MinValueValidator(float("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Цена"
        verbose_name_plural = "Цены"
        ordering = ["-created_at"]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_item", "Can view item"),)

        constraints = [
            models.CheckConstraint(
                check=models.Q(value__gte=0),
                name="no_negative_price_value",
            ),
        ]

    def __str__(self) -> str:
        return str(self.value)


# Create Transaction model with ForeignKey to Tenant
# figure out what fields to add to Transaction model (see billing_form.html)


class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        PAID = "PAID", _("Paid")
        PROCESSING = "PROCESSING", _("Processing")
        COMPLETED = "COMPLETED", _("Completed")
        CANCELED = "CANCELED", _("Canceled")
        FAILED = "FAILED", _("Failed")
        REFUNDED = "REFUNDED", _("Refunded")

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=255, unique=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)

    def __str__(self) -> str:
        return f"Order {self.order_id} ({self.get_status_display()})"


class Payment(models.Model):
    TESTING_CHOICES = (
        ("1", _("1")),  # True
        ("0", _("0")),  # False
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    merchant = models.CharField(max_length=255, default="200000001392761")
    terminal_key = models.CharField(max_length=255, default="test")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=255, unique=True, blank=True)  # Unique id'er for payment processor
    # In the form: <input class="payform-tbank-row" type="text" placeholder="ФИО плательщика" name="name">
    client_name = models.CharField(max_length=255, null=True, blank=True, help_text="ФИО плательщика")
    client_email = models.CharField(max_length=255)  # in the form: name="email"
    client_phone = models.CharField(max_length=15, null=True, blank=True)  # in the form: name="phone"
    testing = models.CharField(max_length=1, default="0")
    is_successful = models.BooleanField(default=False)

    # currently not used
    # receipt_items = models.CharField(blank=True, null=True, max_length=2550)  # currently not used
    # success_url = models.CharField(max_length=255, default="https://securepay.tinkoff.ru/html/payForm/success.html")
    # fail_url = models.CharField(max_length=255, default="https://securepay.tinkoff.ru/html/payForm/fail.html")

    def __str__(self):
        return f"Payment {self.payment_id} for Order {self.order.order_id}"
