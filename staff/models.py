from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from config.models import BaseModel


class StaffMember(BaseModel):
    EMPLOYMENT_TYPES = [
        ("permanent", "Permanent"),
        ("contract", "Contract"),
        ("part_time", "Part time"),
        ("volunteer", "Volunteer"),
    ]
    STATUSES = [
        ("active", "Active"),
        ("leave", "On leave"),
        ("suspended", "Suspended"),
        ("former", "Former staff"),
    ]

    staff_number = models.CharField(max_length=24, unique=True, blank=True)
    user = models.OneToOneField("accounts.User", related_name="staff_profile", on_delete=models.SET_NULL, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=12, choices=[("male", "Male"), ("female", "Female"), ("other", "Other")], blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30)
    alternate_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    national_id = models.CharField("NIN", max_length=30, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to="staff/photos/%Y/", null=True, blank=True)
    department = models.ForeignKey("academics.Department", related_name="staff_members", on_delete=models.SET_NULL, null=True, blank=True)
    job_title = models.CharField(max_length=100)
    qualification = models.CharField(max_length=180, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default="permanent")
    hire_date = models.DateField(default=timezone.localdate)
    contract_end_date = models.DateField(null=True, blank=True)
    salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_teaching_staff = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUSES, default="active")
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [models.Index(fields=["staff_number"]), models.Index(fields=["status", "department"])]

    def clean(self):
        if self.date_of_birth and self.date_of_birth >= timezone.localdate():
            raise ValidationError({"date_of_birth": "Date of birth must be in the past."})
        if self.contract_end_date and self.hire_date and self.contract_end_date <= self.hire_date:
            raise ValidationError({"contract_end_date": "Contract end date must be after the hire date."})
        if self.user_id and self.user.role in {"student", "parent"}:
            raise ValidationError({"user": "A student or parent account cannot be linked to a staff member."})

    def save(self, *args, **kwargs):
        if not self.staff_number:
            prefix = "STF-"
            latest = StaffMember.objects.filter(staff_number__startswith=prefix).order_by("staff_number").last()
            try:
                sequence = int(latest.staff_number.removeprefix(prefix)) + 1 if latest else 1
            except (AttributeError, ValueError):
                sequence = StaffMember.objects.filter(staff_number__startswith=prefix).count() + 1
            candidate = f"{prefix}{sequence:05d}"
            while StaffMember.objects.filter(staff_number=candidate).exclude(pk=self.pk).exists():
                sequence += 1
                candidate = f"{prefix}{sequence:05d}"
            self.staff_number = candidate
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return " ".join(filter(None, [self.first_name, self.other_names, self.last_name]))

    def __str__(self):
        return f"{self.staff_number} · {self.full_name}"


class StaffBankDetail(BaseModel):
    staff = models.OneToOneField(StaffMember, related_name="bank_detail", on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=120)
    branch = models.CharField(max_length=120, blank=True)
    account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=60)
    mobile_money_number = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.staff.full_name} · {self.bank_name}"


class StaffDocument(BaseModel):
    DOCUMENT_TYPES = [
        ("contract", "Employment contract"),
        ("identity", "Identity document"),
        ("qualification", "Academic qualification"),
        ("appointment", "Appointment letter"),
        ("other", "Other"),
    ]
    staff = models.ForeignKey(StaffMember, related_name="documents", on_delete=models.CASCADE)
    document_type = models.CharField(max_length=24, choices=DOCUMENT_TYPES, default="other")
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to="staff/documents/%Y/")
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey("accounts.User", related_name="uploaded_staff_documents", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
