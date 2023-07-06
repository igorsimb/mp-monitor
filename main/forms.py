from django import forms

def validate_sku_format(value):
    if not value.isdigit() or len(value) <5:
        raise forms.ValidationError("Неверный формат SKU.")

class ScrapeForm(forms.Form):
    sku = forms.CharField(label="SKU", max_length=9, validators=[validate_sku_format])