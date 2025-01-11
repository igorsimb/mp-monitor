from django.urls import path

from . import views

urlpatterns = [
    path("items/<int:item_id>/alerts/create/", views.create_price_alert, name="create_price_alert"),
    path("alerts/<int:alert_id>/edit/", views.edit_price_alert, name="edit_price_alert"),
    path("alerts/<int:alert_id>/delete/", views.delete_price_alert, name="delete_price_alert"),
]
