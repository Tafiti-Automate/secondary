# Uganda Secondary School Academic Management System

A complete, role-aware academic platform for Uganda lower-secondary CBC (S1–S4) and upper secondary (S5–S6). It is built with Django 6, Django REST Framework, JWT, PostgreSQL support, and a compiled Tailwind CSS interface.

## Academic coverage

- Role dashboards for Super Administrator, Headteacher, Director of Studies, Teacher, Parent, and Student
- Permanent learner identifiers, complete learner timelines, accommodations, interests, achievements, guardians, enrolment, movement and promotion history
- Academic years, terms, S1–S6 classes, streams, departments, subjects, combinations and teacher allocations
- The six NCDC generic skills, named configurable achievement scales and subject/class indicators
- Draft/published/retired curriculum versions with effective dates, successor links, learning areas, outcomes and evidence requirements
- HOD-approved schemes of work, weekly plans and lesson plans linked to teacher allocations
- Exercises, tests, assignments, projects, practical work, presentations, group work and coursework with per-task weights
- Individual, group, class, interdisciplinary, long-term and community projects with teams, roles, supervisors, milestones, multimedia evidence and reflections
- Separate learner outcome, practical-skill and value ratings, teacher observations and S1–S4 portfolios
- Weighted continuous assessment, assignment files/submissions and bulk mark entry
- HOD → DOS assessment moderation with immutable DOS-approved learner evidence
- Examination sessions, grade scales, mark entry, moderation, approval, publication and locking
- S5–S6 assessment plans with weighted coursework/practical/exam components, processed rankings and versioned UNEB export adapters
- Competency-based report cards plus longitudinal growth profiles with cohort-standard comparisons
- PDF report cards, Excel class-performance exports and cumulative academic transcripts
- Daily, subject and teacher attendance with retry-safe offline capture, QR/biometric provider references, alerts, interventions and analytics
- Class/teacher/student timetables with simulation and automatic conflict-free scheduling across allocations, rooms, labs and learner demand
- Multilingual announcements, private family-school conversations, consent records, emergency broadcasts, resources and delivery queues
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
python manage.py check_school_readiness --academic-year 2026
```

See [API.md](API.md), [ERD.md](ERD.md), [DEPLOYMENT.md](DEPLOYMENT.md),
[docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md), and
[docs/SCHOOL_ACCEPTANCE_CHECKLIST.md](docs/SCHOOL_ACCEPTANCE_CHECKLIST.md), and
[docs/EVOLUTION_ARCHITECTURE.md](docs/EVOLUTION_ARCHITECTURE.md).
# secondary
