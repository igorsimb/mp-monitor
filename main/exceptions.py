from accounts.models import Tenant


class InvalidSKUException(Exception):
    """Exception raised for invalid SKUs."""

    def __init__(self, message: str, sku: str):
        super().__init__(message)
        self.message = message
        self.sku = sku

    def __str__(self):
        return f"Invalid SKU: {self.sku} - {self.message}"


class QuotaExceededException(Exception):
    """Exception raised for exceeding user quota.
    Valid quota types are "skus", "manual_updates", and "scheduled_updates".

    Attributes:
        message (str): The error message.
        quota_type (str): The type of quota that was exceeded.
    """

    VALID_QUOTA_TYPES = ["max_allowed_skus", "manual_updates", "scheduled_updates", "allowed_parse_units"]

    def __init__(self, message: str | tuple, quota_type: str):
        super().__init__(message)
        self.message = message
        self.quota_type = quota_type

        if quota_type not in self.VALID_QUOTA_TYPES:
            raise ValueError(
                f"Invalid quota type: {quota_type}. Valid quota types are: {', '.join(self.VALID_QUOTA_TYPES)}"
            )

    def __str__(self):
        return f"Quota exceeded: {self.quota_type} - Message: {self.message}"


class PlanScheduleLimitationException(Exception):
    """
    Exception raised for violating plan schedule limitations.

    Attributes:
        tenant (Tenant): The tenant associated with the plan limitation.
        plan (str): The name of the plan associated with the plan limitation.
        period (str): The time unit (e.g., "hours", "days")
        interval (int): The interval value (e.g., 7, 24, 48)
        message (str): The error message.

    Example:
        if request.user.tenant.payment_plan.name == PaymentPlan.PlanName.FREE.value:
            if period == "hours" and interval < 24:
                raise PlanScheduleLimitationException(
                    request.user.tenant,
                    plan=request.user.tenant.payment_plan.name,
                    period=period,
                    interval=interval,
                    message="Ограничения бесплатного тарифа. Установите интервал не менее 24 часов",
                    )
    """

    def __init__(self, tenant: Tenant, plan: str, period: str, interval: int, message: str = None):
        super().__init__(tenant, period, interval)
        self.tenant = tenant
        self.plan = plan
        self.period = period
        self.interval = interval
        self.message = message

    def __str__(self):
        return self.message
