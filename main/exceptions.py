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
