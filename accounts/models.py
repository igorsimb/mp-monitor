from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

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

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

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
