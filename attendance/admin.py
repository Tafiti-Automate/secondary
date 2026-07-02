from django.contrib import admin
from .models import AttendanceRecord, AttendanceSession, TeacherAttendance

admin.site.register([AttendanceSession, AttendanceRecord, TeacherAttendance])
