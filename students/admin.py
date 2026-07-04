from django.contrib import admin

from .models import Enrollment, Guardian, Student, StudentAccommodation, StudentAchievement, StudentGuardian, StudentInterest, StudentMovement, StudentPromotion, StudentSubjectRegistration


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_number", "admission_number", "full_name", "stream", "status", "date_admitted")
    list_filter = ("status", "gender", "is_boarding", "stream")
    search_fields = ("student_number", "admission_number", "first_name", "last_name", "other_names")


admin.site.register([Guardian, StudentGuardian, Enrollment, StudentSubjectRegistration, StudentMovement, StudentPromotion, StudentAccommodation, StudentInterest, StudentAchievement])
