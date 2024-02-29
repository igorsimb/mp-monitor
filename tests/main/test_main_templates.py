import logging

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from main.models import Item

logger = logging.getLogger(__name__)

User = get_user_model()


class TestMainTemplates:
    @pytest.fixture
    def client(self) -> Client:
        return Client()

    @pytest.fixture
    def logged_in_user(self, client: Client) -> User:
        user = User.objects.create_user(
            username="testuser", email="testuser@test.com", password="testpassword"
        )
        client.login(username="testuser", password="testpassword")
        return user

    @pytest.fixture
    def item(self, logged_in_user: User) -> Item:
        return Item.objects.create(
            tenant=logged_in_user.tenant,
            name="Test Item",
            sku="12345",
            price=100,
        )

    def test_item_list_template(self, client: Client) -> None:
        response = client.get(reverse("item_list"))
        logger.debug("Main page response: %s", response)
        assert response.status_code == 200
        assert "main/item_list.html" in [t.name for t in response.templates]

    def test_item_detail_template(self, client: Client, item: Item) -> None:
        response = client.get(reverse("item_detail", kwargs={"slug": item.sku}))
        logger.debug("Item Detail page response: %s", response)
        assert response.status_code == 200
        assert "main/item_detail.html" in [t.name for t in response.templates]
