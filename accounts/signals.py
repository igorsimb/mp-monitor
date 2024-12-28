from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.models import Tenant, TenantQuota, PaymentPlan, User, Profile


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


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):  # type: ignore  # pylint: disable=[unused-argument]
    user = instance
    if created:
        Profile.objects.create(user=user)
    else:
        # update allauth email_address if exists
        try:
            email_address = EmailAddress.objects.get_primary(user)
            if email_address.email != user.email:
                email_address.email = user.email
                email_address.verified = False
                email_address.save()
        except EmailAddress.DoesNotExist:
            # if allauth email_address doesn't exist, create one
            EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)


@receiver(pre_save, sender=User)
def lower_case_username(sender, instance, **kwargs):  # type: ignore  # pylint: disable=[unused-argument]
    """
    Convert username to lowercase.
    """
    if instance.username:
        instance.username = instance.username.lower()
