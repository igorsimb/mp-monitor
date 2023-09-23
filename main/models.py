from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule
from guardian.shortcuts import assign_perm


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
    price = models.DecimalField(max_digits=10, decimal_places=0, null=True)
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

        constraints = [models.UniqueConstraint(fields=["tenant", "sku"], name="unique_tenant_sku")]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_item", "Can view item"),)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self):
        return reverse("item_detail", kwargs={"slug": self.sku})

    def save(self, *args, **kwargs):
        group, created = Group.objects.get_or_create(name=self.tenant)
        if not group.permissions.filter(codename="view_item").exists():
            assign_perm("view_item", group, self)
        super().save(*args, **kwargs)
        Price.objects.create(item=self, value=self.price, date_added=timezone.now())


class Price(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")
    value = models.DecimalField(max_digits=10, decimal_places=0, null=True)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_added"]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_item", "Can view item"),)

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
