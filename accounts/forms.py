from django import forms

from .models import User, PaymentPlan, Profile


# class CustomUserCreationForm(UserCreationForm):
#     class Meta:
#         model = User
#         fields = ("email", "password1", "password2")
#
#
# class CustomUserChangeForm(UserChangeForm):
#     class Meta:
#         model = User
#         fields = ("email", "password")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        exclude = ["user"]
        widgets = {
            "image": forms.FileInput(),
            "display_name": forms.TextInput(attrs={"placeholder": "Введите имя"}),
            "info": forms.Textarea(attrs={"rows:": 3, "placeholder": "Введите описание"}),
        }


class EmailChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["email"]


class SwitchPlanForm(forms.Form):
    """
    Form for switching plans.
    """

    plan = forms.CharField(widget=forms.HiddenInput())

    def clean_plan(self) -> PaymentPlan:
        """
        Validates that plan ID exists in the database
        """
        plan_id = self.cleaned_data["plan"]
        try:
            return PaymentPlan.objects.get(name=plan_id)
        except PaymentPlan.DoesNotExist:
            raise forms.ValidationError("Выбранный тариф не существует.")
