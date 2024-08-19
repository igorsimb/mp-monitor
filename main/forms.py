from django import forms
from django.contrib.auth import get_user_model
from django.forms import ModelForm

from main.models import Schedule, Payment

user = get_user_model()


# Currently not used because sku format validation is done by is_sku_format_valid utility function
def validate_sku_format(value: str) -> None:
    if not value.isdigit() or len(value) < 5:
        raise forms.ValidationError("Неверный формат SKU.")


class ScrapeForm(forms.Form):
    skus = forms.CharField(
        label="SKUs",
        widget=forms.Textarea,
        help_text=(
            "Введите один или несколько артикулов через запятую, пробел или с новой строки.\n"
            "Например: 101231520, 109670641, 31299196"
        ),
    )


class UpdateItemsForm(forms.Form):
    pass


class TaskForm(forms.Form):
    interval = forms.FloatField(min_value=1, label="Interval (seconds)")


class ScrapeIntervalFormOld(forms.Form):
    interval = forms.FloatField(min_value=1, label="Interval (seconds)")


class ScrapeIntervalForm(ModelForm):
    class Meta:
        model = Schedule
        fields = ["interval_value", "period"]

    def __init__(self, *args, **kwargs):
        """
        Remove seconds and minutes choices for non-staff and non-superusers
        Make sure to pass `user` when instantiating the form,
        e.g. form = ScrapeIntervalForm(request.POST or None, user=request.user)
        """
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # seconds and minutes choices are only for staff and superusers
        if user is not None and not user.is_staff and not user.is_superuser:
            self.fields["period"].choices = [
                choice
                for choice in self.fields["period"].choices
                if choice[0] not in [Schedule.Period.SECONDS, Schedule.Period.MINUTES]
            ]


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "merchant",
            "unix_timestamp",
            "amount",
            "testing",
            "description",
            "order_id",
            "client_email",
            "success_url",
            "receipt_items",
            "signature",
        ]
        widgets = {
            # "merchant": forms.HiddenInput(),
            # "unix_timestamp": forms.HiddenInput(),
            # "amount": forms.HiddenInput(),
            # "testing": forms.HiddenInput(),
            # "description": forms.HiddenInput(),
            # "order_id": forms.HiddenInput(),
            # "client_email": forms.HiddenInput(),
            # "success_url": forms.HiddenInput(),
            # "receipt_items": forms.HiddenInput(),
            # "signature": forms.HiddenInput(),
        }


# TODO: add payment form to billing_tab_payment_plans
