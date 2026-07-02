from django.contrib import admin

from .models import AcademicYear, CalendarEvent, ClassLevel, Department, SchoolProfile, Stream, Subject, SubjectAllocation, SubjectCombination, Term


admin.site.register([SchoolProfile, AcademicYear, Term, Department, ClassLevel, Stream, Subject, SubjectCombination, SubjectAllocation, CalendarEvent])
