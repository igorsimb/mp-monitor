from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import Tenant
from main.models import Item


class PriceAlert(models.Model):
    class TargetPriceDirection(models.TextChoices):
        UP = ">=", "Above or Equal"
        DOWN = "<=", "Below or Equal"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    items = models.ManyToManyField(Item, related_name="price_alerts")
    target_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Target price to trigger notification",
    )
    target_price_direction = models.CharField(
        max_length=2,
        choices=TargetPriceDirection.choices,
        default=TargetPriceDirection.UP,
        help_text="Direction of the target price",
    )
    message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Включено")
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Price Alert"
        verbose_name_plural = "Price Alerts"
        ordering = ["-is_active"]

    def __str__(self):
        return f"Price Alert for {self.tenant} #{self.pk}"
