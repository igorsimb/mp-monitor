from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from main.models import Item
from notifier.forms import PriceAlertForm
from notifier.models import PriceAlert


@login_required
def create_price_alert(request, item_id):
    """Create a new price alert for an item."""
    item = get_object_or_404(Item, id=item_id, tenant=request.user.tenant)

    if request.method == "POST":
        form = PriceAlertForm(data=request.POST, item=item)
        if form.is_valid():
            form.save()
            # messages.success(request, _("Уведомление создано"))

            return render(
                request, "notifier/partials/alert_list.html", {"price_alerts": PriceAlert.objects.filter(items=item)}
            )

    # If GET request or form invalid, return form
    form = PriceAlertForm(item=item)
    messages.error(request, _("Уведомление не создано"))
    return redirect("item_detail", slug=item.sku)


@login_required
def edit_price_alert(request, alert_id: int):
    """Edit a price alert."""
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    form = PriceAlertForm(instance=alert)
    return render(request, "notifier/alert_form.html", {"form": form, "item": alert.items.first()})


@login_required
@require_http_methods(["DELETE"])
def delete_price_alert(request, alert_id: int) -> HttpResponse:
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    items = alert.items.all()

    # to be used in the context of the template
    remaining_alerts = list(PriceAlert.objects.filter(items__in=items).exclude(id=alert.id).distinct())

    alert.delete()
    return render(request, "notifier/partials/alert_list.html", {"price_alerts": remaining_alerts})


@login_required
def toggle_price_alert(request, alert_id):
    """Toggle a price alert's active status."""
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    alert.is_active = not alert.is_active
    alert.save()

    status = _("Активно") if alert.is_active else _("Неактивно")
    messages.success(request, _("Уведомление %(status)s") % {"status": status.lower()})

    # if request.htmx:
    #     return HttpResponse(status)
    return redirect("item_detail", slug=alert.items.first().sku)
