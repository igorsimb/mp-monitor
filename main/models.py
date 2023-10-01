import logging

from django.contrib.auth.models import Group
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule
from guardian.shortcuts import assign_perm, get_perms

logger = logging.getLogger(__name__)


class Tenant(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"

    def __str__(self):
        return self.name


class Item(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, validators=[MinValueValidator(float("0.00"))]
    )
    image = models.URLField(null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    brand = models.CharField(max_length=255, null=True, blank=True)
    seller_name = models.CharField(max_length=255, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    num_reviews = models.IntegerField(null=True, blank=True)
    parser_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

        constraints = [models.UniqueConstraint(fields=["tenant", "sku"], name="unique_tenant_sku"),
                       models.CheckConstraint(check=models.Q(price__gte=float("0.00")), name="no_negative_price"),]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_item", "Can view item"),)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self):
        return reverse("item_detail", kwargs={"slug": self.sku})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Price.objects.create(item=self, value=self.price, date_added=timezone.now())


# Having post_save signal solves "Object needs to be persisted first" if adding perms on save, resulting in failure to
# add a scraped item to db. This is because Django adds ManyToMany related fields after saving.
# Source: https://stackoverflow.com/a/23772575
@receiver(post_save, sender=Item)
def add_perms_to_group(sender, instance, created, **kwargs):
    group, created = Group.objects.get_or_create(name=instance.tenant)
    if not group.permissions.filter(codename="view_item").exists():
        logger.info("Adding 'view_item' permission for item '%s' to group '%s'", instance.name, group.name)
        assign_perm("view_item", group, instance)
        # get_perms: https://django-guardian.readthedocs.io/en/stable/userguide/check.html#get-perms
        if "view_item" not in get_perms(group, instance):
            logger.error("Failed to add 'view_item' permission for item '%s' to group '%s'", instance.name, group.name)


class Price(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")
    value = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, validators=[MinValueValidator(float("0.00"))]
    )
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Цена"
        verbose_name_plural = "Цены"
        ordering = ["-date_added"]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_item", "Can view item"),)

        constraints = [
            models.CheckConstraint(
                check=models.Q(value__gte=0),
                name="no_negative_price_value",
            ),
        ]

    def __str__(self):
        return f"{self.item.name}'s price"


class Printer(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


# 2 Models: Product and Parcer.
# Product would have a parcer = models.ForeignKey(Parcer, on_delete=models.SET_NULL); is_enabled =
# models.BooleanField(default=True)
# Parcer would have interval = models.IntegerField()
# So we would start a parser with an interval and pick what products to do it for.

# TODO:
# 1. Use enums for choices for seconds, minutes, hours
# 2. Use Custom models manager for queryset of enabled products
