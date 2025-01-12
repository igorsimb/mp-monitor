import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_htmx.http import trigger_client_event, retarget

from main.models import Item
from notifier.forms import PriceAlertForm
from notifier.models import PriceAlert

logger = logging.getLogger(__name__)


@login_required
def create_price_alert(request, item_id):
    """Create a new price alert for an item."""
    item = get_object_or_404(Item, id=item_id, tenant=request.user.tenant)
    price_alerts = PriceAlert.objects.filter(items=item)
    alert = price_alerts.first()

    if request.method == "POST":
        form = PriceAlertForm(data=request.POST, item=item)
        if form.is_valid():
            form.save()
            return render(request, "notifier/partials/alert_list.html", {"price_alerts": price_alerts})
        else:
            messages.error(request, _("Уведомление не создано"))
            return redirect("item_detail", slug=item.sku)

    form = PriceAlertForm(item=item)
    context = {
        "price_alert_form": form,
        "alert": alert,
        "item": item,
        "price_alerts": price_alerts,
    }
    return render(request, "notifier/partials/offcanvas_body.html", context)


@login_required
def edit_price_alert(request, alert_id: int):
    """Edit a price alert."""
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    item = alert.items.first()
    price_alerts = PriceAlert.objects.filter(items=item)

    if request.method == "POST":
        form = PriceAlertForm(data=request.POST, instance=alert, item=item)
        if form.is_valid():
            form.save()
            context = {
                "price_alert_form": form,
                "alert": alert,
                "item": item,
                "price_alerts": price_alerts,
            }
            response = render(request, "notifier/partials/offcanvas_body.html", context)
            retarget(response, "#offcanvas-body")
            return response

        else:
            logger.error("Form is invalid: %s", form.errors)
            return render(
                request,
                "notifier/partials/edit_alert_form.html",  # Same form with errors
                {"price_alert_form": form, "alert": alert, "item": item},
            )

    form = PriceAlertForm(instance=alert, item=item)
    context = {
        "price_alert_form": form,
        "alert": alert,
        "selected_alert_id": alert.id,  # Used in alert_list.html to highlight the alert that is being edited
        "item": item,
        "price_alerts": price_alerts,
    }
    response = render(request, "notifier/partials/offcanvas_body.html", context)
    retarget(response, "#offcanvas-body")
    return response


@login_required
@require_http_methods(["DELETE"])
def delete_price_alert(request, alert_id: int) -> HttpResponse:
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    items = alert.items.all()

    # to be used in the context of the template
    remaining_alerts = list(PriceAlert.objects.filter(items__in=items).exclude(id=alert.id).distinct())

    alert.delete()
    response = render(request, "notifier/partials/alert_list.html", {"price_alerts": remaining_alerts})
    trigger_client_event(response, "alert-deleted", {})  # used in alert_list.html to trigger optimistic update
    return response
