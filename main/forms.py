from django import forms
from django.forms import ModelForm

from main.models import Schedule


def validate_sku_format(value: str) -> None:
    if not value.isdigit() or len(value) < 5:
        raise forms.ValidationError("Неверный формат SKU.")


class ScrapeForm(forms.Form):
    skus = forms.CharField(
        label="SKUs",
        widget=forms.Textarea,
        help_text="Введите один или несколько артикулов через запятую, пробел или с новой строки.\n"
        "Например: 101231520, 109670641, 31299196",
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


# class ScrapeIntervalUpdateForm(ModelForm):
#     class Meta:
#         model = Schedule
