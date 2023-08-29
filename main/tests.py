from django.test import SimpleTestCase
from django.urls import reverse, resolve

from .views import IndexView


class IndexPageTests(SimpleTestCase):
    def setUp(self):
        url = reverse("index")
        self.response = self.client.get(url)

    def test_url_exists_at_correct_location(self):
        self.assertEqual(self.response.status_code, 200)

    def test_index_template(self):
        self.assertTemplateUsed(self.response, "main/item_list.html")

    def test_index_page_contains_correct_html(self):
        self.assertContains(self.response, "Main Page")

    def test_index_page_does_not_contain_incorrect_html(self):
        self.assertNotContains(self.response, "Hi! I should not be on the page.")

    def test_index_page_url_resolves_index_view(self):
        view = resolve("/")
        self.assertEqual(view.func.__name__, IndexView.as_view().__name__)
