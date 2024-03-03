class InvalidSKUException(Exception):
    """Exception raised for invalid SKUs."""

    def __init__(self, message: str, sku: str):
        super().__init__(message)
        self.message = message
        self.sku = sku

    def __str__(self):
        return f"Invalid SKU: {self.sku} - {self.message}"
