from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse
from guardian.shortcuts import assign_perm


class Tenant(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"

    def __str__(self):
        return self.name


class Product(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_without_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.URLField(null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    brand = models.CharField(max_length=255, null=True, blank=True)
    seller_name = models.CharField(max_length=255, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    num_reviews = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

        constraints = [models.UniqueConstraint(fields=['tenant', 'sku'], name="unique_tenant_sku")]
        default_permissions = ("add", "change", "delete")
        permissions = (("view_product", "Can view product"),)
        
    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self):
        return reverse("product", kwargs={"slug": self.sku})

    def save(self, *args, **kwargs):
        group, created = Group.objects.get_or_create(name=self.tenant)
        super(Product, self).save(*args, **kwargs)
        assign_perm("view_product", group, self)
