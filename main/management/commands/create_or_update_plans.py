from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import PaymentPlan, TenantQuota
from config import PlanType, DEFAULT_QUOTAS, PLAN_PRICES


class Command(BaseCommand):
    help = "Create new payment plans or update existing ones with current values from config"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Creating/updating payment plans and quotas...")

        for plan_type in PlanType:
            if plan_type == PlanType.TEST:
                continue  # Skip TEST plan

            # Create or update quota for the plan
            quota = TenantQuota.objects.get_or_create(
                name=plan_type.value,
                defaults={
                    "total_hours_allowed": DEFAULT_QUOTAS[plan_type.value]["total_hours_allowed"],
                    "skus_limit": DEFAULT_QUOTAS[plan_type.value]["skus_limit"],
                    "parse_units_limit": DEFAULT_QUOTAS[plan_type.value]["parse_units_limit"],
                },
            )[0]

            # Create or update payment plan
            plan, created = PaymentPlan.objects.get_or_create(
                name=plan_type.value,
                defaults={
                    "quotas": quota,
                    "price": PLAN_PRICES[plan_type.value],
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created new plan: {plan.get_name_display()} with price {plan.price}")
                )
            else:
                old_price = plan.price
                plan.quotas = quota
                plan.price = PLAN_PRICES[plan_type.value]
                plan.save()
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated plan: {plan.get_name_display()} " f"(price changed from {old_price} to {plan.price})"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Successfully created/updated all plans and quotas"))
