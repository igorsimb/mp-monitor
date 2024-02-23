import logging

from django.contrib.auth import get_user_model

from accounts.forms import CustomUserCreationForm

logger = logging.getLogger(__name__)

User = get_user_model()


class TestCustomUserCreationForm:
    def test_form_valid_with_correct_data(self):
        form_data = {"email": "test@example.com", "password1": "validpassword123", "password2": "validpassword123"}
        form = CustomUserCreationForm(data=form_data)
        assert form.is_valid(), form.errors

    def test_user_created_with_email_and_password(self):
        form_data = {"email": "test@example.com", "password1": "validpassword123", "password2": "validpassword123"}
        form = CustomUserCreationForm(data=form_data)
        user = form.save()
        assert user.email == "test@example.com"
        assert user.check_password("validpassword123"), form.errors

    def test_form_fields_displayed_correctly(self):
        form = CustomUserCreationForm()
        assert "email" in form.fields
        assert "password1" in form.fields
        assert "password2" in form.fields

    def test_passwords_do_not_match(self):
        form_data = {"email": "test@example.com", "password1": "validpassword123", "password2": "validpassword456"}
        form = CustomUserCreationForm(data=form_data)
        assert not form.is_valid()
        assert "password2" in form.errors

    def test_signup_form_does_not_create_duplicate_user(self):
        User.objects.create_user(username="existing_user", email="test@example.com", password="validpassword123")

        form_data = {"email": "test@example.com", "password1": "validpassword123", "password2": "validpassword123"}
        form = CustomUserCreationForm(data=form_data)

        logger.info("Making sure form still looks valid and duplicate email is not revealed...")
        assert form.is_valid()
        assert not form.errors, form.errors

        logger.info("Ensuring that a user with the same email is not created...")
        assert User.objects.filter(email="test@example.com").count() == 1, (
            f"Additional user created with same email ({form_data['email']})! "
            f"User count should be 1, but it is {User.objects.filter(email='test@example.com').count()} instead."
        )

    def test_password_too_short(self):
        form_data = {"email": "test@example.com", "password1": "pass", "password2": "pass"}
        form = CustomUserCreationForm(data=form_data)
        assert not form.is_valid()
        assert "password2" in form.errors
        error_messages = form.errors.get("password2", [])
        assert any("Введённый пароль слишком короткий" in error for error in error_messages), form.errors
