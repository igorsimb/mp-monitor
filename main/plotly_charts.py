from datetime import datetime

import plotly.express as px
import plotly.graph_objects as go
from babel.dates import format_date
from django.db.models import QuerySet
from django.utils import timezone


# Fixes the following error:
# DateTimeField Price.created_at received a naive datetime (2024-09-08 00:00:00) while time zone support is active.
def convert_dates_to_datetime_objects(start_date: str, end_date: str) -> (datetime, datetime):
    """Converts the given start and end dates to datetime objects.
    :param start_date: A string representing the start date for filtering the prices.
    :param end_date: A string representing the end date for filtering the prices.
    :return: A tuple of datetime objects representing the start and end dates.
    """
    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        start_date = timezone.make_aware(start_date)  # Make it timezone-aware
    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        end_date = timezone.make_aware(end_date)  # Make it timezone-aware

    return start_date, end_date


def create_price_history_chart(prices: QuerySet, start_date: str, end_date: str) -> str:
    """Creates a Plotly chart for the given price queryset and returns the chart's HTML.
    :param prices: A list of Price objects.
    :param start_date: A string representing the start date for filtering the prices.
    :param end_date: A string representing the end date for filtering the prices.
    :return: A string representing the Plotly chart's HTML.

    Source: https://plotly.com/python/line-charts/
    """

    # changing the default ordering for plotly chart to be chronological
    prices_ordered_for_plotly = prices.order_by("created_at")
    start_date, end_date = convert_dates_to_datetime_objects(start_date, end_date)

    if start_date:
        prices_ordered_for_plotly = prices_ordered_for_plotly.filter(created_at__gte=start_date)
    if end_date:
        prices_ordered_for_plotly = prices_ordered_for_plotly.filter(created_at__lte=end_date)

    price_count = prices_ordered_for_plotly.count()

    # Check if there's only one data point (or zero) after filtering
    if price_count == 0:
        return (
            '<div class="text-danger text-center"><span class="material-symbols-sharp">error</span> Нет данных для'
            " отображения на этом интервале</div>"
        )
    else:
        formatted_dates = [
            format_date(price.created_at, format="d MMM, y", locale="ru") for price in prices_ordered_for_plotly
        ]

        if price_count > 1:
            fig = go.Figure(layout={"title": "История цен"})
            fig.add_trace(
                go.Scatter(
                    x=formatted_dates, y=[price.value for price in prices_ordered_for_plotly], mode="lines+markers"
                )
            )
        else:
            fig = px.scatter(
                x=formatted_dates,
                y=[price.value for price in prices_ordered_for_plotly],
                title="История цен",
                labels={"x": "Дата", "y": "Цена"},
            )

        fig.update_layout(
            title={
                "font_size": 21,
            },
            paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                showgrid=False,  # Remove grid lines
                showline=True,  # Show x-axis line
                linecolor="lightgrey",
                linewidth=2,
            ),
            yaxis=dict(showgrid=True, gridcolor="lightgrey", griddash="dash", zeroline=False),
            # xaxis_tickangle=-45,
            xaxis_nticks=20,
        )

        return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True})
