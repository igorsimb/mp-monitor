from django import forms
from django.utils.translation import gettext_lazy as _

from notifier.models import PriceAlert


class PriceAlertForm(forms.ModelForm):
    """
    Form for creating price alerts from the item detail page.
    """

    target_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(),
    )

    message = forms.CharField(
        required=False,
        widget=forms.Textarea(),
    )

    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput())

    class Meta:
        model = PriceAlert
        fields = ["target_price", "message", "is_active"]

    def __init__(self, item=None, *args, **kwargs):
        self.item = item
        super().__init__(*args, **kwargs)

    def clean_target_price(self):
        target_price = self.cleaned_data.get("target_price")

        if target_price <= 0:
            raise forms.ValidationError(_("Целевая цена должна быть больше 0"))

        if target_price == "":
            raise forms.ValidationError(_("Целевая цена не может быть пустой"))

        if self.item and target_price == self.item.price:
            raise forms.ValidationError(_("Целевая цена не может быть равна текущей цене"))

        return target_price

    def save(self, commit=True):
        instance = super().save(commit=False)
        # update target_price_direction
        if instance.target_price > self.item.price:
            instance.target_price_direction = PriceAlert.TargetPriceDirection.UP
        elif instance.target_price < self.item.price:
            instance.target_price_direction = PriceAlert.TargetPriceDirection.DOWN
        if self.item:
            instance.tenant = self.item.tenant
            if commit:
                instance.save()
                instance.items.add(self.item)
        return instance
