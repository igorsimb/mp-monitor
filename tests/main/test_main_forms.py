import logging

import pytest
from django.contrib.auth import get_user_model

from main.forms import ScrapeForm, TaskForm, ScrapeIntervalForm

logger = logging.getLogger(__name__)

User = get_user_model()


class TestScrapeForm:
    def test_form_valid_with_one_sku(self):
        form_data = {"skus": "12345"}
        form = ScrapeForm(data=form_data)
        assert form.is_valid()

    def test_form_valid_with_comma_separated_skus(self):
        form_data = {"skus": "12345, 67890, 54321"}
        form = ScrapeForm(data=form_data)
        assert form.is_valid()

    def test_form_valid_with_space_separated_skus(self):
        form_data = {"skus": "12345 67890 54321"}
        form = ScrapeForm(data=form_data)
        assert form.is_valid()

    def test_form_valid_with_newline_separated_skus(self):
        form_data = {"skus": "12345\n67890\n54321"}
        form = ScrapeForm(data=form_data)
        assert form.is_valid()

    def test_form_valid_with_combination_of_formats(self):
        form_data = {"skus": "12345, 67890\n54321 98765"}
        form = ScrapeForm(data=form_data)
        assert form.is_valid()

    # TODO: Add tests for invalid formats when https://github.com/igorsimb/mp-monitor/issues/18 is resolved
    # def test_form_invalid_with_invalid_skus(self):
    #     form_data = {'skus': '12345, abcde, 54321'}
    #     form = ScrapeForm(data=form_data)
    #     assert not form.is_valid()


class TestTaskForm:
    class TestTaskForm:
        @pytest.mark.parametrize(
            "interval, expected_validity",
            [
                (5.0, True),  # Valid interval
                (-1.0, False),  # Negative interval
                (0.0, False),  # Zero interval
                ("not_a_float", False),  # Non-float interval
            ],
            ids=[
                "valid_interval",
                "negative_interval",
                "zero_interval",
                "non_float_interval",
            ],
        )
        def test_task_form_validation(self, interval, expected_validity):
            form_data = {"interval": interval}
            form = TaskForm(data=form_data)

            assert form.is_valid() == expected_validity


class TestScrapeIntervalForm:
    @pytest.mark.parametrize(
        "interval, period, expected_validity",
        [
            (5.0, "seconds", True),  # Valid interval
            (-1.0, "seconds", False),  # Negative interval
            (0.0, "seconds", False),  # Zero interval
            ("not_a_float", "seconds", False),  # Non-float interval
        ],
        ids=[
            "valid_interval",
            "negative_interval",
            "zero_interval",
            "non_float_interval",
        ],
    )
    def test_form_validity(self, interval, period, expected_validity):
        form_data = {"interval_value": interval, "period": period}
        form = ScrapeIntervalForm(data=form_data)
        assert form.is_valid() == expected_validity
