"""
Price-related UI enhancement utilities for displaying and formatting price data.
"""

import logging
from decimal import InvalidOperation, DivisionByZero

from django.core.paginator import Page

logger = logging.getLogger(__name__)


def calculate_percentage_change(prices: Page) -> None:
    """Calculate percentage change between consecutive prices.

    Args:
        prices: list of Price objects.
    """
    for i in range(len(prices)):
        try:
            previous_price = prices[i + 1].value
            current_price = prices[i].value
            percent_change = ((current_price - previous_price) / previous_price) * 100
            prices[i].percent_change = round(percent_change, 2)
        except (IndexError, InvalidOperation, DivisionByZero):
            prices[i].percent_change = 0
        except TypeError:
            logger.warning("Can't compare price to NoneType")


def add_table_class(prices: Page) -> None:
    """Add Bootstrap table classes based on price changes.

    Args:
        prices: Paginated list of Price objects.
    """
    for i in range(len(prices)):
        try:
            if prices[i].percent_change > 0:
                prices[i].table_class = "table-danger"
            elif prices[i].percent_change < 0:
                prices[i].table_class = "table-success"
            else:
                prices[i].table_class = ""
        except (AttributeError, TypeError):
            prices[i].table_class = ""


def add_price_trend_indicator(prices: Page) -> None:
    """Add trend indicators to a list of Price objects based on price comparison.

    Iterates through a list of Price objects and assigns trend indicators
    ('trend' attribute) based on price comparisons.

    Args:
        prices: Paginated list of Price objects.

    Example of use in a template:
        {% for price in prices %}
            <tr>
                <td>{{ price.trend }}</td>
                ...
            </tr>
        {% endfor %}
    """
    for i in range(len(prices)):
        try:
            if prices[i].value < prices[i + 1].value:
                prices[i].trend = "↓"
            elif prices[i].value > prices[i + 1].value:
                prices[i].trend = "↑"
            else:
                prices[i].trend = ""

        # the original price is the last price in the list, so no comparison is possible
        except IndexError:
            prices[i].table_class = ""
        except TypeError:
            logger.warning("Can't compare price to NoneType")
