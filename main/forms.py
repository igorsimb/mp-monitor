from django import forms


def validate_sku_format(value):
    if not value.isdigit() or len(value) < 5:
        raise forms.ValidationError("Неверный формат SKU.")


class ScrapeForm(forms.Form):
    skus = forms.CharField(
        label="SKUs",
        widget=forms.Textarea,
        help_text="Введите один или несколько артикулов через запятую, пробел или с новой строки.",
    )


class TaskForm(forms.Form):
    interval = forms.FloatField(min_value=1, label="Interval (seconds)")


class ScrapeIntervalForm(forms.Form):
    interval = forms.FloatField(min_value=1, label="Interval (seconds)")
