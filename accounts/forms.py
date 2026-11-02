"""
Custom User Administration Forms for MECHORA.
Provides styled user creation, role selection, and secure password fields.
"""

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, ReadOnlyPasswordHashField, UserCreationForm
from django.core.exceptions import ValidationError
from unfold.widgets import (
    UnfoldAdminEmailInputWidget,
    UnfoldAdminPasswordWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextInputWidget,
    UnfoldBooleanSwitchWidget,
)

from .roles import (
    ROLE_ADMIN,
    ROLE_CHOICES,
    ROLE_ENGINEER,
    ROLE_SUPERVISOR,
    assign_user_role,
    get_user_role,
)

User = get_user_model()


class MechoraPasswordToggleWidget(UnfoldAdminPasswordWidget):
    """
    Password input widget rendered with full width, crisp borders,
    and a show/hide toggle icon.
    """
    template_name = "accounts/widgets/password_toggle.html"


class RoleAuthenticationForm(AuthenticationForm):
    """Sign-in form that verifies the selected role server-side."""

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial=ROLE_ENGINEER,
        widget=forms.HiddenInput(),
    )

    def clean(self):
        cleaned_data = super().clean()
        if not self.errors and self.user_cache is not None:
            selected_role = cleaned_data.get("role")
            actual_role = get_user_role(self.user_cache)
            if actual_role == "Superuser":
                actual_role = ROLE_ADMIN
            if selected_role != actual_role:
                raise ValidationError(
                    "The selected role does not match this account. Choose the correct role and try again."
                )
        return cleaned_data


class PublicSignupForm(UserCreationForm):
    """Public registration for operational roles only."""

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    role = forms.ChoiceField(
        choices=(
            (ROLE_ENGINEER, "Engineer"),
            (ROLE_SUPERVISOR, "Supervisor"),
        ),
        initial=ROLE_ENGINEER,
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class MechoraUserCreationForm(forms.ModelForm):
    """
    Form for adding a new user through the Django Unfold Administration Panel.
    Enforces required fields, email uniqueness, password validation, and single role assignment.
    """
    username = forms.CharField(
        max_length=150,
        widget=UnfoldAdminTextInputWidget(
            attrs={"placeholder": "e.g., jsmith", "autocomplete": "off"}
        ),
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
    )
    email = forms.EmailField(
        required=True,
        widget=UnfoldAdminEmailInputWidget(
            attrs={"placeholder": "user@mechora.industrial"}
        ),
        help_text="Required. Unique contact email address.",
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=UnfoldAdminTextInputWidget(attrs={"placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=UnfoldAdminTextInputWidget(attrs={"placeholder": "Last name"}),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial=ROLE_ENGINEER,
        required=True,
        widget=UnfoldAdminSelectWidget,
        label="User Role",
        help_text="Assign exactly one designated operational role: Admin, Engineer, or Supervisor.",
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=UnfoldBooleanSwitchWidget,
        label="Active Status",
        help_text="Designates whether this account is active. Deselect to block access.",
    )
    password1 = forms.CharField(
        label="Password",
        widget=MechoraPasswordToggleWidget(
            attrs={
                "placeholder": "Enter secure password",
                "autocomplete": "new-password",
            }
        ),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=MechoraPasswordToggleWidget(
            attrs={
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
            }
        ),
        help_text="Enter the same password as above for verification.",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
        )

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            raise ValidationError("A valid username is required.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email address is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2:
            if p1 != p2:
                raise ValidationError("The two password fields didn't match.")
            password_validation.validate_password(p1, user=self.instance)
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_staff = True  # Grants Django Unfold access according to role permissions
        user.is_superuser = False

        role = self.cleaned_data.get("role")

        def save_m2m():
            if role:
                assign_user_role(user, role)

        self.save_m2m = save_m2m

        if commit:
            user.save()
            save_m2m()

        return user


class MechoraUserChangeForm(forms.ModelForm):
    """
    Form for editing an existing user. Allows role modification, account activation,
    and profile editing while protecting against privilege escalation.
    """
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored. Passwords can be changed via the password reset form."
        ),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=False,
        widget=UnfoldAdminSelectWidget,
        label="Assigned Role",
        help_text="Select one role. Updating will adjust assigned permissions immediately.",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "is_staff",
        )

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        # Style standard fields with Unfold widgets
        self.fields["username"].widget = UnfoldAdminTextInputWidget()
        self.fields["first_name"].widget = UnfoldAdminTextInputWidget()
        self.fields["last_name"].widget = UnfoldAdminTextInputWidget()
        self.fields["email"].widget = UnfoldAdminEmailInputWidget()
        self.fields["is_active"].widget = UnfoldBooleanSwitchWidget()
        self.fields["is_staff"].widget = UnfoldBooleanSwitchWidget()

        if self.instance and self.instance.pk:
            current_role = get_user_role(self.instance)
            if current_role in [ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR]:
                self.fields["role"].initial = current_role

            # Superusers retain separate root status
            if self.instance.is_superuser:
                self.fields["role"].help_text = "User is a Superuser (highest-level system administrator)."
                self.fields["role"].disabled = True

            # Prevent non-superusers from modifying their own role or staff status
            if (
                self.request_user
                and not self.request_user.is_superuser
                and self.instance == self.request_user
            ):
                self.fields["role"].disabled = True
                self.fields["is_staff"].disabled = True

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if self.instance and self.instance.pk:
            # Prevent non-superuser from changing their own role
            if (
                self.request_user
                and not self.request_user.is_superuser
                and self.instance == self.request_user
            ):
                return get_user_role(self.instance)

            # Prevent demoting superusers through this form
            if self.instance.is_superuser:
                return None

        return role

    def save(self, commit=True):
        user = super().save(commit=commit)
        new_role = self.cleaned_data.get("role")

        def save_m2m():
            if new_role and not user.is_superuser:
                assign_user_role(user, new_role)

        if hasattr(self, "save_m2m"):
            orig_save_m2m = self.save_m2m

            def combined_save_m2m():
                orig_save_m2m()
                save_m2m()

            self.save_m2m = combined_save_m2m
        else:
            self.save_m2m = save_m2m

        if commit and new_role and not user.is_superuser:
            assign_user_role(user, new_role)

        return user
