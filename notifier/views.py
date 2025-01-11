from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_htmx.http import retarget

from main.models import Item
from notifier.forms import PriceAlertForm
from notifier.models import PriceAlert


@login_required
def create_price_alert(request, item_id):
    """Create a new price alert for an item."""
    item = get_object_or_404(Item, id=item_id, tenant=request.user.tenant)
    print(f"\ncreate price {item=}")

    if request.method == "POST":
        form = PriceAlertForm(data=request.POST, item=item)
        print("1. Create POST data:", request.POST)  # Inspect POST data
        print("2. Create Form errors (detailed):", form.errors)  # See form error details
        print(f"3. Create Form data before cleaning: {form.data}")
        if form.is_valid():
            print(f"4. Form cleaned data: {form.cleaned_data}")
            form.save()
            # messages.success(request, _("Уведомление создано"))

            return render(
                request, "notifier/partials/alert_list.html", {"price_alerts": PriceAlert.objects.filter(items=item)}
            )
        else:
            messages.error(request, _("Уведомление не создано"))
            return redirect("item_detail", slug=item.sku)

    # If GET request or form invalid, return form
    form = PriceAlertForm(item=item)
    messages.error(request, _("Уведомление не создано"))
    return redirect("item_detail", slug=item.sku)


@login_required
def edit_price_alert(request, alert_id: int):
    """Edit a price alert."""
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    item = alert.items.first()
    print(f"\nedit price {item=}")

    if request.method == "POST":
        form = PriceAlertForm(data=request.POST, instance=alert, item=item)
        print("1. Edit POST data:", request.POST)  # Inspect POST data
        print("2. Edit Form errors (detailed):", form.errors)  # Log form error detai
        print(f"3. Edit Form data before cleaning: {form.data}")
        if form.is_valid():
            print(f"4. Form cleaned data: {form.cleaned_data}")
            form.save()
            print("IGOR1: form saved, going to alert_list.html")
            response = render(
                request, "notifier/partials/alert_list.html", {"price_alerts": PriceAlert.objects.filter(items=item)}
            )
            return retarget(response, "#alert-list-block")

        else:
            print(f"Form is invalid: {form.errors}")
            # print(f"Form dirty data: {form.cleaned_data}")
            return render(
                request,
                "notifier/partials/edit_alert.html",  # Same form with errors
                {"price_alert_form": form, "alert": alert, "item": item},
            )

    form = PriceAlertForm(instance=alert, item=item)
    context = {"price_alert_form": form, "alert": alert, "item": item}
    print("IGOR1: returning edit_alert.html")
    return render(request, "notifier/partials/edit_alert.html", context)
    # return render(
    #     request, "notifier/alerts_offcanvas.html", {"form": form, "alert": alert, "item": alert.items.first()}
    # )


@login_required
@require_http_methods(["DELETE"])
def delete_price_alert(request, alert_id: int) -> HttpResponse:
    alert = get_object_or_404(PriceAlert, id=alert_id, tenant=request.user.tenant)
    items = alert.items.all()

    # to be used in the context of the template
    remaining_alerts = list(PriceAlert.objects.filter(items__in=items).exclude(id=alert.id).distinct())

    alert.delete()
    response = render(request, "notifier/partials/alert_list.html", {"price_alerts": remaining_alerts})
    response["Hx-trigger"] = "alert-deleted"
    return response


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
