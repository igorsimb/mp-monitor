from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms

from .models import User, PaymentPlan


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "password1", "password2")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "password")


class SwitchPlanForm(forms.Form):
    """
    Form for switching plans.
    """

    plan = forms.CharField(widget=forms.HiddenInput())

    def clean_plan(self):
        """
        Validates that plan ID exists in the database
        """
        plan_id = self.cleaned_data["plan"]
        try:
            return PaymentPlan.objects.get(name=plan_id)
        except PaymentPlan.DoesNotExist:
            raise forms.ValidationError("Выбранный тариф не существует.")
