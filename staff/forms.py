from django import forms

from accounts.models import User
from config.forms import StyledModelForm
from .models import StaffBankDetail, StaffDocument, StaffMember


class StaffMemberForm(StyledModelForm):
    class Meta:
        model = StaffMember
        fields = (
            "user", "first_name", "last_name", "other_names", "gender", "date_of_birth",
            "phone", "alternate_phone", "email", "national_id", "address", "photo",
            "department", "job_title", "qualification", "employment_type", "hire_date",
            "contract_end_date", "salary", "is_teaching_staff", "status",
            "emergency_contact_name", "emergency_contact_phone", "notes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        linked = StaffMember.objects.exclude(pk=self.instance.pk).exclude(user=None).values_list("user_id", flat=True)
        self.fields["user"].queryset = User.objects.filter(is_deleted=False).exclude(role__in=("student", "parent")).exclude(pk__in=linked)


class StaffBankDetailForm(StyledModelForm):
    class Meta:
        model = StaffBankDetail
        fields = ("bank_name", "branch", "account_name", "account_number", "mobile_money_number")


class StaffDocumentForm(StyledModelForm):
    class Meta:
        model = StaffDocument
        fields = ("document_type", "title", "file", "expiry_date")
