from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from config import DEMO_USER_EXPIRATION_HOURS
from main.models import Tenant


class CustomUser(AbstractUser):
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
            self.tenant = Tenant.objects.create(status=Tenant.Status.CANCELED)
        super().save(*args, **kwargs)


# Add user to the Tenant group upon creation
@receiver(post_save, sender=CustomUser)
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


# Create a UserQuota object for each user upon creation
@receiver(post_save, sender=CustomUser)
def create_user_quota(sender, instance, created, **kwargs):  # type: ignore  # pylint: disable=[unused-argument]
    if instance.is_superuser:
        return
    if created:
        UserQuota.objects.create(user=instance)


class UserQuota(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="user_quotas")
    user_lifetime_hours = models.PositiveIntegerField(default=0, blank=True, null=True)
    max_allowed_skus = models.PositiveIntegerField(default=0, blank=True, null=True)
    manual_updates = models.PositiveIntegerField(default=0, blank=True, null=True)
    scheduled_updates = models.PositiveIntegerField(default=0, blank=True, null=True)

    class Meta:
        verbose_name = "Квота"
        verbose_name_plural = "Квоты"

    def __str__(self):
        return f"{self.user.username}'s quotas"  # pragma: no cover
