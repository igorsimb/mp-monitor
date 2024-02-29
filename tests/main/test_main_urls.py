import logging

import pytest
from django.urls import reverse, resolve

from main.views import (
    ItemListView,
    ItemDetailView,
    scrape_items,
    create_scrape_interval_task,
    destroy_scrape_interval_task,
)

logger = logging.getLogger(__name__)


class TestMainUrls:
    def test_item_list_url(self):
        url = reverse("item_list")
        logger.info("Resolving URL: %s to view class: %s", url, ItemListView)
        assert resolve(url).func.view_class == ItemListView

    def test_item_detail_url(self):
        slug = "145823738"
        url = reverse("item_detail", args=[slug])
        logger.info("Resolving URL: %s to view class: %s", url, ItemDetailView)
        assert resolve(url).func.view_class == ItemDetailView

    def test_scrape_items_url(self):
        skus = "145823738"
        url = reverse("scrape_item", args=[skus])
        logger.info("Resolving URL: %s to view function: %s", url, scrape_items)
        assert resolve(url).func == scrape_items

    def test_create_scrape_interval_task_url(self):
        url = reverse("create_scrape_interval")
        logger.info(
            "Resolving URL: %s to view function: %s", url, create_scrape_interval_task
        )
        assert resolve(url).func == create_scrape_interval_task

    def test_destroy_scrape_interval_task_url(self):
        url = reverse("destroy_scrape_interval")
        logger.info(
            "Resolving URL: %s to view function: %s", url, destroy_scrape_interval_task
        )
        assert resolve(url).func == destroy_scrape_interval_task

    @pytest.mark.parametrize(
        "expected_view",
        [ItemListView, ItemDetailView, scrape_items, create_scrape_interval_task],
    )
    def test_incorrect_url_does_not_resolve(self, expected_view):
        url = reverse("destroy_scrape_interval")
        logger.info(
            "Resolving incorrect URL: %s to view function: %s",
            url,
            create_scrape_interval_task,
        )
        assert (
            resolve(url).func != expected_view
        ), f"URL {url} resolved to {expected_view} when it should not have!"
