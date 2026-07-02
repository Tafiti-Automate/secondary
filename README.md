# Uganda Secondary School Academic Management System

A complete, role-aware academic platform for Uganda lower-secondary CBC (S1–S4) and upper secondary (S5–S6). It is built with Django 6, Django REST Framework, JWT, PostgreSQL support, and a compiled Tailwind CSS interface.

## Academic coverage

- Role dashboards for Super Administrator, Headteacher, Director of Studies, Teacher, Parent, and Student
- Student admission numbers, learner profiles, guardians, enrolment and promotion history
- Academic years, terms, S1–S6 classes, streams, departments, subjects, combinations and teacher allocations
- The eight CBC competencies, configurable proficiency scales and subject/class indicators
- Curriculum learning areas, outcome criteria, suggested activities and required evidence
- HOD-approved schemes of work, weekly plans and lesson plans linked to teacher allocations
- Exercises, tests, assignments, projects, practical work, presentations, group work and coursework
- Separate learner outcome, practical-skill and value ratings, teacher observations and S1–S4 portfolios
- Weighted continuous assessment, assignment files/submissions and bulk mark entry
- HOD → DOS assessment moderation with immutable DOS-approved learner evidence
- Examination sessions, grade scales, mark entry, moderation, approval, publication and locking
- S5–S6 assessment plans with weighted coursework/practical/exam components and processed rankings
- Competency-based report cards with attendance, position, comments and promotion decisions
- PDF report cards, Excel class-performance exports and cumulative academic transcripts
- Daily, subject and teacher attendance with parent absence alerts and analytics
- Class/teacher/student timetables, rooms and teacher/room/stream conflict detection
- Announcements, learning resources and in-system/email-ready notifications
- REST API, JWT claims, browsable OpenAPI documentation, pagination and throttling
- Soft deletion, activity tracking and an academic audit trail
- Responsive mobile navigation, dark mode, accessible forms and print layouts

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build:css
export DEBUG=True
export DB_ENGINE=sqlite
python manage.py migrate
python seed_data.py
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. API documentation is at `/api/docs/` and the Django administration is at `/admin/`.

### Demonstration accounts

| Workspace | Username | Password |
|---|---|---|
| Super Administrator | `admin` | `Admin@2026` |
| Director of Studies | `dos` | `School@2026` |
| Teacher | `teacher` | `Teacher@2026` |
| Parent | `parent` | `Parent@2026` |
| Student | `student` | `Student@2026` |

Change all demonstration passwords before using the database outside local development.

## Verification

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py collectstatic --noinput
```

See [API.md](API.md), [ERD.md](ERD.md), and [DEPLOYMENT.md](DEPLOYMENT.md) for interface, data-model, and production instructions.
# secondary
