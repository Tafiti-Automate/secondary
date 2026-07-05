from django.contrib import admin

from .models import StaffBankDetail, StaffDocument, StaffMember

admin.site.register((StaffMember, StaffBankDetail, StaffDocument))
