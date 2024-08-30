from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Tenant, TenantQuota, PaymentPlan


@receiver(post_save, sender=Tenant)
@transaction.atomic
def assign_default_plan(sender, instance, created, **kwargs):
    if created:
        instance.payment_plan = PaymentPlan.get_default_payment_plan()
        instance.save()


@receiver(post_save, sender=Tenant)
@transaction.atomic
def assign_default_plan_quota(sender, instance, created, **kwargs):
    if created:
        instance.quota = TenantQuota.get_default_quota()
        instance.save()
