
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import EmployeeProfile

User = get_user_model()

ROLE_CHOICES = ["Administrator", "Manager", "Employee"]


def available_roles():
    return Group.objects.filter(name__in=ROLE_CHOICES).order_by("name")


class EmployeeForm(forms.Form):
    employee_id = forms.CharField(max_length=20)
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    department = forms.ChoiceField(
        choices=EmployeeProfile.DEPARTMENT_CHOICES
    )
    job_title = forms.CharField(max_length=100, required=False)
    role = forms.ModelChoiceField(queryset=available_roles())
    password = forms.CharField(
        min_length=12,
        widget=forms.PasswordInput,
        help_text="Use at least 12 characters.",
    )

    def clean_employee_id(self):
        employee_id = self.cleaned_data["employee_id"].strip()

        if EmployeeProfile.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("Employee ID already exists.")

        return employee_id

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already exists.")

        return email


class EmployeeEditForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    is_active = forms.BooleanField(
        required=False,
        label="Active Status",
    )
    role = forms.ModelChoiceField(queryset=available_roles())

    class Meta:
        model = EmployeeProfile
        fields = ["employee_id", "department", "job_title"]

    def __init__(self, *args, **kwargs):
        employee = kwargs.pop("employee", None)

        if employee is not None:
            kwargs.setdefault("instance", employee)

        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            user = self.instance.user

            self.fields["username"].initial = user.username
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
            self.fields["is_active"].initial = user.is_active

            current_role = user.groups.filter(
                name__in=ROLE_CHOICES
            ).first()

            if current_role:
                self.fields["role"].initial = current_role.pk

    def clean_employee_id(self):
        employee_id = self.cleaned_data["employee_id"].strip()

        profiles = EmployeeProfile.objects.filter(
            employee_id=employee_id
        )

        if self.instance and self.instance.pk:
            profiles = profiles.exclude(pk=self.instance.pk)

        if profiles.exists():
            raise forms.ValidationError("Employee ID already exists.")

        return employee_id

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        users = User.objects.filter(username__iexact=username)

        if self.instance and self.instance.pk:
            users = users.exclude(pk=self.instance.user_id)

        if users.exists():
            raise forms.ValidationError("Username already exists.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()

        if email:
            users = User.objects.filter(email__iexact=email)

            if self.instance and self.instance.pk:
                users = users.exclude(pk=self.instance.user_id)

            if users.exists():
                raise forms.ValidationError("Email already exists.")

        return email


class ADUserCreateForm(forms.Form):
    username = forms.RegexField(
        regex=r"^[a-zA-Z0-9._-]{1,20}$",
        max_length=20,
        label="Username (sAMAccountName)",
        error_messages={
            "invalid": (
                "Use 1–20 letters, numbers, dots, underscores, "
                "or hyphens."
            )
        },
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    first_name = forms.CharField(
        max_length=64,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=64,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    display_name = forms.CharField(
        max_length=256,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    department = forms.CharField(
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    job_title = forms.CharField(
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    description = forms.CharField(
        max_length=1024,
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3}
        ),
    )
    password = forms.CharField(
        min_length=12,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text="Use a password of at least 12 characters.",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Confirm password",
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error(
                "confirm_password",
                "The passwords do not match.",
            )

        return cleaned_data

