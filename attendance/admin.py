from django.contrib import admin
from .models import AttendanceAlert, AttendanceIdentity, AttendanceIntervention, AttendanceRecord, AttendanceSession, TeacherAttendance

admin.site.register([AttendanceSession, AttendanceRecord, TeacherAttendance, AttendanceIdentity, AttendanceAlert, AttendanceIntervention])
