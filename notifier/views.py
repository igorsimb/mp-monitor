from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

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
            messages.success(request, _("Уведомление создано"))

            return render(
                request, "notifier/partials/alert_list.html", {"price_alerts": PriceAlert.objects.filter(items=item)}
            )
            # if request.htmx:
            #     return HttpResponse(status=204)  # Close modal
            # return redirect("item_detail", slug=item.sku)

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
def delete_price_alert(request, alert_id):
    """Delete a price alert."""
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)

    # Get the first item's SKU before deleting the alert
    first_item_sku = alert.items.first().sku if alert.items.exists() else None

    # Delete the alert
    alert.delete()
    messages.success(request, _("Уведомление удалено"))

    # Redirect appropriately
    if first_item_sku:
        return redirect("item_detail", slug=first_item_sku)
    return redirect("item_list")  # Define a fallback in case no items are related


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
