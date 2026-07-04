from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from academics.models import CalendarEvent, ClassLevel, Stream, Subject, Term
from assessments.models import (
    Assessment,
    AssessmentResult,
    AssessmentType,
    Competency,
    CompetencyAssessment,
    CompetencyLevel,
    CurriculumValue,
    LearnerSkillRating,
    LearnerValueRating,
    LearningOutcome,
    LearningOutcomeAssessment,
    PortfolioItem,
    Skill,
    TeacherObservation,
)
from attendance.models import AttendanceRecord, AttendanceSession
from communications.models import Announcement, LearningResource, Notification
from exams.models import ExamSession, Examination, ExaminationResult, GradeScale
from reports.models import ReportCard
from students.models import Enrollment, Guardian, Student, StudentGuardian, StudentSubjectRegistration
from timetables.models import Room, TimeSlot, TimetableEntry


FIRST_NAMES = [
    "Joel", "Lydia", "Isaac", "Ruth", "Daniel", "Patience", "Samuel", "Mercy",
    "Emmanuel", "Sharon", "Caleb", "Fatuma", "Joshua", "Esther", "Mark", "Deborah",
    "Adrian", "Joan", "Paul", "Mariam", "Denis", "Gloria", "Noah", "Irene",
    "Andrew", "Brenda", "Hassan", "Agnes", "Stephen",
]
LAST_NAMES = [
    "Mukasa", "Namazzi", "Ssemanda", "Atim", "Kibazo", "Adoch", "Lwanga", "Nankya",
    "Ocen", "Auma", "Mwesigwa", "Nansubuga", "Kato", "Akello", "Tumusiime", "Nakitto",
    "Mugisha", "Namuli", "Wekesa", "Nakato", "Opio", "Asiimwe", "Walusimbi", "Nabirye",
    "Okot", "Namaganda", "Kiggundu", "Nambi", "Ouma",
]


class Command(BaseCommand):
    help = "Seed a production-safe, idempotent 30-learner demonstration dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-production",
            action="store_true",
            help="Required acknowledgement that the target database will be modified.",
        )

    def handle(self, *args, **options):
        if not options["confirm_production"]:
            raise CommandError("Pass --confirm-production to modify the target database.")

        with transaction.atomic():
            counts = self._seed()

        self.stdout.write(self.style.SUCCESS("Production demonstration data seeded successfully."))
        for label, count in counts.items():
            self.stdout.write(f"{label}: {count}")

    def _seed(self):
        year_term = Term.objects.select_related("academic_year").filter(
            academic_year__name="2026", number=2, is_deleted=False
        ).first()
        class_level = ClassLevel.objects.filter(name="S1", is_deleted=False).first()
        stream = Stream.objects.filter(
            name="A", class_level=class_level, academic_year=year_term.academic_year, is_deleted=False
        ).first() if year_term and class_level else None
        teacher = User.objects.filter(username="teacher", is_deleted=False).first()
        dos = User.objects.filter(username="dos", is_deleted=False).first()
        admin = User.objects.filter(username="admin", is_deleted=False).first()
        if not all([year_term, class_level, stream, teacher, dos, admin]):
            raise CommandError("Reference academic data is incomplete; run the base seed setup first.")

        subjects = list(Subject.objects.filter(
            code__in=["ENG", "MTC", "GSC", "GEO", "ICT"], is_deleted=False
        ).order_by("code"))
        if len(subjects) != 5:
            raise CommandError("The five S1 demonstration subjects are not available.")
        english = next(subject for subject in subjects if subject.code == "ENG")

        self._seed_students(stream)
        amina = Student.objects.filter(first_name="Amina", last_name="Nabirye", is_deleted=False).first()
        generated = list(Student.objects.filter(
            student_number__startswith="DEMO-STU-", is_deleted=False
        ).order_by("student_number"))
        students = ([amina] if amina else []) + generated
        students = students[:30]
        if len(students) != 30:
            raise CommandError(f"Expected a 30-learner cohort, found {len(students)}.")

        self._seed_guardians(students)
        self._seed_enrollments(students, year_term, stream, subjects)
        assessments = self._seed_assessments(year_term, stream, subjects, teacher)
        self._seed_assessment_evidence(students, assessments, year_term, english, teacher)
        examinations = self._seed_examinations(year_term, stream, subjects, teacher, dos)
        self._seed_attendance(students, year_term, stream, subjects, teacher)
        self._seed_reports(students, year_term, stream, dos)
        self._seed_communications(year_term, class_level, stream, subjects, teacher, dos, admin)
        self._seed_timetable(year_term, stream, subjects, teacher)

        return {
            "students": Student.objects.filter(pk__in=[student.pk for student in students]).count(),
            "guardians": Guardian.objects.filter(email__startswith="demo.guardian.").count() + 1,
            "assessments": Assessment.objects.filter(title__startswith="Demo learning task").count(),
            "assessment results": AssessmentResult.objects.filter(assessment__title__startswith="Demo learning task").count(),
            "examinations": Examination.objects.filter(title__startswith="Demo examination").count(),
            "examination results": ExaminationResult.objects.filter(examination__title__startswith="Demo examination").count(),
            "attendance records": AttendanceRecord.objects.filter(session__period_label__startswith="Demo session").count(),
            "portfolio items": PortfolioItem.objects.filter(title__startswith="Demo portfolio").count(),
            "report cards": ReportCard.objects.filter(student__in=students, term=year_term).count(),
            "announcements": Announcement.objects.filter(title__startswith="Demo bulletin").count(),
            "learning resources": LearningResource.objects.filter(title__startswith="Demo resource").count(),
            "timetable entries": TimetableEntry.objects.filter(term=year_term, stream=stream).count(),
        }

    def _seed_students(self, stream):
        numbers = [f"DEMO-STU-{index:04d}" for index in range(1, 30)]
        existing = set(Student.objects.filter(student_number__in=numbers).values_list("student_number", flat=True))
        rows = []
        for index, (first_name, last_name) in enumerate(zip(FIRST_NAMES, LAST_NAMES), 1):
            number = f"DEMO-STU-{index:04d}"
            if number in existing:
                continue
            rows.append(Student(
                student_number=number,
                admission_number=f"DEMO-2026-{index:03d}",
                first_name=first_name,
                last_name=last_name,
                gender="female" if index % 2 == 0 else "male",
                date_of_birth=date(2011 + index % 2, (index % 12) + 1, (index % 25) + 1),
                stream=stream,
                date_admitted=date(2026, 2, 2),
                previous_school="Partner Primary School",
                district="Kampala" if index % 2 else "Wakiso",
                status="active",
                is_active=True,
            ))
        Student.objects.bulk_create(rows, ignore_conflicts=True, batch_size=100)

    def _seed_guardians(self, students):
        generated_students = [student for student in students if student.student_number.startswith("DEMO-STU-")]
        emails = [f"demo.guardian.{student.student_number[-4:]}@school.test" for student in generated_students]
        existing = set(Guardian.objects.filter(email__in=emails).values_list("email", flat=True))
        Guardian.objects.bulk_create([
            Guardian(
                first_name=f"Guardian {student.first_name}",
                last_name=student.last_name,
                phone=f"+256700{index:06d}",
                email=email,
                occupation="Community member",
                address="Kampala, Uganda",
            )
            for index, (student, email) in enumerate(zip(generated_students, emails), 1)
            if email not in existing
        ], ignore_conflicts=True, batch_size=100)
        guardians = {
            guardian.email: guardian
            for guardian in Guardian.objects.filter(email__in=emails)
        }
        existing_links = set(StudentGuardian.objects.filter(
            student__in=generated_students, is_deleted=False
        ).values_list("student_id", "guardian_id"))
        links = []
        for student, email in zip(generated_students, emails):
            guardian = guardians[email]
            if (student.pk, guardian.pk) not in existing_links:
                links.append(StudentGuardian(
                    student=student, guardian=guardian, relationship="guardian", is_primary=True
                ))
        StudentGuardian.objects.bulk_create(links, ignore_conflicts=True, batch_size=100)

    def _seed_enrollments(self, students, term, stream, subjects):
        year = term.academic_year
        student_ids = [student.pk for student in students]
        enrolled = set(Enrollment.objects.filter(
            student_id__in=student_ids, academic_year=year, is_deleted=False
        ).values_list("student_id", flat=True))
        Enrollment.objects.bulk_create([
            Enrollment(student=student, academic_year=year, stream=stream, roll_number=index)
            for index, student in enumerate(students, 1) if student.pk not in enrolled
        ], ignore_conflicts=True, batch_size=100)
        enrollments = list(Enrollment.objects.filter(
            student_id__in=student_ids, academic_year=year, is_deleted=False
        ))
        existing = set(StudentSubjectRegistration.objects.filter(
            enrollment__in=enrollments, subject__in=subjects, is_deleted=False
        ).values_list("enrollment_id", "subject_id"))
        StudentSubjectRegistration.objects.bulk_create([
            StudentSubjectRegistration(enrollment=enrollment, subject=subject, category="core", status="active")
            for enrollment in enrollments for subject in subjects
            if (enrollment.pk, subject.pk) not in existing
        ], ignore_conflicts=True, batch_size=500)

    def _seed_assessments(self, term, stream, subjects, teacher):
        assessment_type = AssessmentType.objects.filter(is_deleted=False).order_by("pk").first()
        if not assessment_type:
            raise CommandError("No assessment type is available.")
        titles = [f"Demo learning task {index:02d}" for index in range(1, 31)]
        existing = set(Assessment.objects.filter(title__in=titles).values_list("title", flat=True))
        Assessment.objects.bulk_create([
            Assessment(
                title=title,
                assessment_type=assessment_type,
                term=term,
                subject=subjects[(index - 1) % len(subjects)],
                stream=stream,
                created_by=teacher,
                assigned_date=term.start_date + timedelta(days=index),
                due_date=term.start_date + timedelta(days=index + 10),
                instructions="Complete the applied learning task and include a short reflection.",
                max_score=100,
                weight=10,
                status="published",
                assessment_period="ongoing",
                evidence_method="triangulated",
                project_type="individual",
            )
            for index, title in enumerate(titles, 1) if title not in existing
        ], batch_size=100)
        return list(Assessment.objects.filter(title__in=titles).order_by("title"))

    def _seed_assessment_evidence(self, students, assessments, term, subject, teacher):
        pairs = list(zip(students, assessments))
        existing_results = set(AssessmentResult.objects.filter(
            assessment__in=assessments, student__in=students, is_deleted=False
        ).values_list("assessment_id", "student_id"))
        AssessmentResult.objects.bulk_create([
            AssessmentResult(
                assessment=assessment,
                student=student,
                score=Decimal(55 + index % 41),
                grade="A" if index % 4 == 0 else "B",
                feedback="Good progress; use the feedback to strengthen the next task.",
                marked_by=teacher,
            )
            for index, (student, assessment) in enumerate(pairs, 1)
            if (assessment.pk, student.pk) not in existing_results
        ], ignore_conflicts=True, batch_size=100)

        existing_portfolios = set(PortfolioItem.objects.filter(
            title__startswith="Demo portfolio"
        ).values_list("title", flat=True))
        PortfolioItem.objects.bulk_create([
            PortfolioItem(
                student=student,
                term=term,
                stream=student.stream,
                subject=assessment.subject,
                assessment=assessment,
                category="project",
                title=f"Demo portfolio {index:02d}",
                description="A practical learner product with planning and reflection evidence.",
                reflection_notes="I used feedback to improve the clarity and accuracy of my work.",
                teacher_feedback="Clear evidence of progress.",
                status="verified",
                uploaded_by=teacher,
                verified_by=teacher,
            )
            for index, (student, assessment) in enumerate(pairs, 1)
            if f"Demo portfolio {index:02d}" not in existing_portfolios
        ], batch_size=100)

        observed = set(TeacherObservation.objects.filter(
            student__in=students, term=term, note__startswith="[DEMO]"
        ).values_list("student_id", flat=True))
        TeacherObservation.objects.bulk_create([
            TeacherObservation(
                student=student,
                term=term,
                subject=assessment.subject,
                assessment=assessment,
                category="participation",
                observation_date=term.start_date + timedelta(days=20 + index % 20),
                note="[DEMO] Contributed relevant ideas and explained the evidence used.",
                observed_by=teacher,
            )
            for index, (student, assessment) in enumerate(pairs, 1) if student.pk not in observed
        ], batch_size=100)

        competency = Competency.objects.filter(is_deleted=False, is_active=True).order_by("display_order").first()
        level = CompetencyLevel.objects.filter(is_deleted=False).order_by("numeric_value").last()
        outcome = LearningOutcome.objects.filter(topic__subject=subject, is_deleted=False).first()
        skill = Skill.objects.filter(is_deleted=False, is_active=True).order_by("display_order").first()
        value = CurriculumValue.objects.filter(is_deleted=False).order_by("display_order").first()
        if competency and level:
            CompetencyAssessment.objects.bulk_create([
                CompetencyAssessment(
                    assessment=assessment, student=student, competency=competency,
                    scale_level=level, level=level.name, comment="Demonstrated consistently.", assessed_by=teacher,
                ) for student, assessment in pairs
            ], ignore_conflicts=True, batch_size=100)
        if outcome and level:
            LearningOutcomeAssessment.objects.bulk_create([
                LearningOutcomeAssessment(
                    assessment=assessment, student=student, outcome=outcome, term=term,
                    scale_level=level, level=level.code, comment="Meets the expected outcome.", assessed_by=teacher,
                ) for student, assessment in pairs if assessment.subject_id == subject.pk
            ], ignore_conflicts=True, batch_size=100)
        if skill and level:
            LearnerSkillRating.objects.bulk_create([
                LearnerSkillRating(
                    assessment=assessment, student=student, skill=skill, term=term,
                    subject=assessment.subject, level=level, comment="Applied during practical work.", assessed_by=teacher,
                ) for student, assessment in pairs
            ], ignore_conflicts=True, batch_size=100)
        if value and level:
            LearnerValueRating.objects.bulk_create([
                LearnerValueRating(
                    assessment=assessment, student=student, value=value, term=term,
                    subject=assessment.subject, level=level, comment="Observed during collaborative work.", assessed_by=teacher,
                ) for student, assessment in pairs
            ], ignore_conflicts=True, batch_size=100)

    def _seed_examinations(self, term, stream, subjects, teacher, dos):
        scale, _ = GradeScale.objects.get_or_create(
            name="Demo percentage scale",
            defaults={"curriculum_level": "general", "description": "Demonstration grading scale."},
        )
        session, _ = ExamSession.objects.get_or_create(
            term=term,
            name="Demo Term II examinations",
            defaults={
                "exam_type": "end", "start_date": term.end_date - timedelta(days=14),
                "end_date": term.end_date - timedelta(days=3), "status": "published", "grade_scale": scale,
            },
        )
        titles = [f"Demo examination {index:02d}" for index in range(1, 31)]
        existing = set(Examination.objects.filter(title__in=titles).values_list("title", flat=True))
        Examination.objects.bulk_create([
            Examination(
                title=title,
                session=session,
                term=term,
                subject=subjects[(index - 1) % len(subjects)],
                stream=stream,
                exam_date=term.end_date - timedelta(days=3 + index % 10),
                start_time=time(8 + index % 3, 0),
                duration_minutes=120,
                max_score=100,
                status="published",
                created_by=teacher,
                approved_by=dos,
                published=True,
            ) for index, title in enumerate(titles, 1) if title not in existing
        ], batch_size=100)
        examinations = list(Examination.objects.filter(title__in=titles).order_by("title"))
        students = list(Student.objects.filter(
            student_number__startswith="DEMO-STU-", is_deleted=False
        ).order_by("student_number"))
        amina = Student.objects.filter(first_name="Amina", last_name="Nabirye", is_deleted=False).first()
        students = ([amina] if amina else []) + students
        pairs = list(zip(students[:30], examinations))
        existing_results = set(ExaminationResult.objects.filter(
            examination__in=examinations, student__in=students, is_deleted=False
        ).values_list("examination_id", "student_id"))
        ExaminationResult.objects.bulk_create([
            ExaminationResult(
                examination=examination,
                student=student,
                score=Decimal(50 + index % 46),
                grade="A" if index % 5 == 0 else "B",
                points=1 if index % 5 == 0 else 2,
                descriptor="Strong progress",
                teacher_remark="Shows steady understanding of the term's work.",
                marked_by=teacher,
                approved=True,
            ) for index, (student, examination) in enumerate(pairs, 1)
            if (examination.pk, student.pk) not in existing_results
        ], ignore_conflicts=True, batch_size=100)
        return examinations

    def _seed_attendance(self, students, term, stream, subjects, teacher):
        labels = [f"Demo session {index:02d}" for index in range(1, 31)]
        existing = set(AttendanceSession.objects.filter(
            term=term, stream=stream, period_label__in=labels, is_deleted=False
        ).values_list("period_label", flat=True))
        AttendanceSession.objects.bulk_create([
            AttendanceSession(
                term=term,
                stream=stream,
                subject=subjects[(index - 1) % len(subjects)],
                session_type="subject",
                date=term.start_date + timedelta(days=index),
                period_label=label,
                taken_by=teacher,
                notes="Demonstration attendance register.",
                status="verified",
            ) for index, label in enumerate(labels, 1) if label not in existing
        ], ignore_conflicts=True, batch_size=100)
        sessions = list(AttendanceSession.objects.filter(
            term=term, stream=stream, period_label__in=labels, is_deleted=False
        ).order_by("period_label"))
        existing_pairs = set(AttendanceRecord.objects.filter(
            session__in=sessions, student__in=students, is_deleted=False
        ).values_list("session_id", "student_id"))
        AttendanceRecord.objects.bulk_create([
            AttendanceRecord(
                session=session,
                student=student,
                status="absent" if (session_index + student_index) % 23 == 0 else (
                    "late" if (session_index + student_index) % 17 == 0 else "present"
                ),
                reason="Guardian follow-up required" if (session_index + student_index) % 23 == 0 else "",
                source="import",
                device_id="demo-seed",
            )
            for session_index, session in enumerate(sessions)
            for student_index, student in enumerate(students)
            if (session.pk, student.pk) not in existing_pairs
        ], ignore_conflicts=True, batch_size=1000)

    def _seed_reports(self, students, term, stream, dos):
        existing = set(ReportCard.objects.filter(
            student__in=students, term=term, is_deleted=False
        ).values_list("student_id", flat=True))
        ReportCard.objects.bulk_create([
            ReportCard(
                student=student,
                term=term,
                stream=stream,
                total_score=Decimal(300 + index * 3),
                average_score=Decimal(55 + index % 40),
                class_position=index,
                class_size=len(students),
                attendance_present=27,
                attendance_absent=2,
                attendance_late=1,
                teacher_remark="A positive term; continue using feedback to build consistency.",
                dos_remark="Progress reviewed against the school assessment policy.",
                headteacher_comment="Keep growing in competence, character and service.",
                portfolio_summary="Practical work, reflection and teacher observation included.",
                status="published",
                generated_by=dos,
            ) for index, student in enumerate(students, 1) if student.pk not in existing
        ], ignore_conflicts=True, batch_size=100)

    def _seed_communications(self, term, class_level, stream, subjects, teacher, dos, admin):
        bulletin_titles = [f"Demo bulletin {index:02d}" for index in range(1, 31)]
        existing = set(Announcement.objects.filter(title__in=bulletin_titles).values_list("title", flat=True))
        Announcement.objects.bulk_create([
            Announcement(
                title=title,
                body=f"Academic update {index}: learners should review feedback and upcoming activities.",
                audience=["all", "students", "parents", "teachers"][index % 4],
                stream=stream if index % 4 == 0 else None,
                is_pinned=index <= 2,
                created_by=dos,
            ) for index, title in enumerate(bulletin_titles, 1) if title not in existing
        ], batch_size=100)

        resource_titles = [f"Demo resource {index:02d}" for index in range(1, 31)]
        existing_resources = set(LearningResource.objects.filter(
            title__in=resource_titles
        ).values_list("title", flat=True))
        LearningResource.objects.bulk_create([
            LearningResource(
                title=title,
                description="A demonstration revision resource with guided practice activities.",
                subject=subjects[(index - 1) % len(subjects)],
                class_level=class_level,
                stream=stream,
                resource_type="worksheet" if index % 2 else "notes",
                external_url=f"https://example.com/demo-resource-{index:02d}",
                uploaded_by=teacher,
            ) for index, title in enumerate(resource_titles, 1) if title not in existing_resources
        ], batch_size=100)

        notification_titles = [f"Demo notification {index:02d}" for index in range(1, 31)]
        existing_notifications = set(Notification.objects.filter(
            recipient=admin, title__in=notification_titles
        ).values_list("title", flat=True))
        Notification.objects.bulk_create([
            Notification(
                recipient=admin,
                title=title,
                message="A demonstration academic workflow item is ready for review.",
                channel="in_app",
                status="sent",
                link="/",
            ) for title in notification_titles if title not in existing_notifications
        ], batch_size=100)

        event_titles = [f"Demo calendar event {index:02d}" for index in range(1, 31)]
        existing_events = set(CalendarEvent.objects.filter(
            term=term, title__in=event_titles
        ).values_list("title", flat=True))
        CalendarEvent.objects.bulk_create([
            CalendarEvent(
                term=term,
                title=title,
                category=["activity", "meeting", "exam", "deadline"][index % 4],
                start_date=term.start_date + timedelta(days=index),
                description="Demonstration school calendar activity.",
            ) for index, title in enumerate(event_titles, 1) if title not in existing_events
        ], batch_size=100)

    def _seed_timetable(self, term, stream, subjects, teacher):
        slot_specs = [
            ("Demo Period 1", time(8, 0), time(8, 40)),
            ("Demo Period 2", time(8, 40), time(9, 20)),
            ("Demo Period 3", time(9, 20), time(10, 0)),
            ("Demo Period 4", time(10, 20), time(11, 0)),
            ("Demo Period 5", time(11, 0), time(11, 40)),
            ("Demo Period 6", time(11, 40), time(12, 20)),
        ]
        names = [name for name, _, _ in slot_specs]
        existing_names = set(TimeSlot.objects.filter(name__in=names).values_list("name", flat=True))
        TimeSlot.objects.bulk_create([
            TimeSlot(name=name, start_time=start, end_time=end, slot_type="lesson", display_order=index)
            for index, (name, start, end) in enumerate(slot_specs, 1) if name not in existing_names
        ], batch_size=100)
        slots = list(TimeSlot.objects.filter(name__in=names).order_by("display_order"))
        room, _ = Room.objects.get_or_create(
            name="Demo S1 Classroom", defaults={"code": "DEMO-S1", "capacity": 60}
        )
        existing = set(TimetableEntry.objects.filter(
            term=term, stream=stream, day_of_week__in=range(1, 6), time_slot__in=slots, is_deleted=False
        ).values_list("day_of_week", "time_slot_id"))
        TimetableEntry.objects.bulk_create([
            TimetableEntry(
                term=term,
                stream=stream,
                day_of_week=day,
                time_slot=slot,
                subject=subjects[(day + slot_index) % len(subjects)],
                teacher=teacher,
                room=room,
                notes="Demonstration timetable entry.",
            ) for day in range(1, 6) for slot_index, slot in enumerate(slots)
            if (day, slot.pk) not in existing
        ], ignore_conflicts=True, batch_size=100)
