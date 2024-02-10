import logging

import pytest
from django.test import Client
from django.urls import reverse

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestAccountsTemplates:
    @pytest.fixture
    def client(self):
        return Client()

    def test_login_template(self, client):
        response = client.get(reverse("account_login"))
        logger.debug("Login response: %s", response)
        assert response.status_code == 200

        assert "account/login.html" in [t.name for t in response.templates]

    @pytest.mark.skip(reason="Skipped until fixed for new frontend")
    def test_logout_redirect(self, client):
        response = client.get(reverse("account_logout"), follow=True)  # follow the redirect
        logger.debug("Logout response: %s", response)
        assert response.status_code == 200

        logger.info("Checking for the name of the resolved view after following the redirect...")
        assert response.resolver_match.url_name == "item_list"

    def test_signup_template(self, client):
        response = client.get(reverse("account_signup"))
        logger.debug("Signup rResponse: %s", response)
        assert response.status_code == 200
        assert "account/signup.html" in [t.name for t in response.templates]
