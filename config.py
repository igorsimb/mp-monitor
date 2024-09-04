"""
Configuration settings for the project.
Stores constants and other settings that are used throughout the project.
"""

from enum import Enum

DEMO_USER_HOURS_ALLOWED = 12
DEMO_USER_MAX_ALLOWED_SKUS = 10
DEMO_USER_ALLOWED_PARSE_UNITS = 150
HOURS_ALLOWED = 24 * 30 * 12 * 10  # 10 years, should reset every month, so it's effectively infinite
MAX_ITEMS_ON_SCREEN = 10  # used in the messages when many items are scraped
MAX_RETRIES = 10


class PlanType(Enum):
    # can be accessed like so: PaymentPlan.FREE.value, etc
    TEST = "0"
    FREE = "1"
    BUSINESS = "2"
    PROFESSIONAL = "3"
    CORPORATE = "4"


DEFAULT_QUOTAS = {
    PlanType.FREE.value: {
        "total_hours_allowed": HOURS_ALLOWED,
        "skus_limit": 50,
        "parse_units_limit": 5000,
    },
    PlanType.BUSINESS.value: {
        "total_hours_allowed": HOURS_ALLOWED,
        "skus_limit": 500,
        "parse_units_limit": 35_000,
    },
    PlanType.PROFESSIONAL.value: {
        "total_hours_allowed": HOURS_ALLOWED,
        "skus_limit": 1000,
        "parse_units_limit": 100_000,
    },
    PlanType.CORPORATE.value: {
        "total_hours_allowed": HOURS_ALLOWED,
        "skus_limit": 5000,
        "parse_units_limit": 500_000,
    },
}
