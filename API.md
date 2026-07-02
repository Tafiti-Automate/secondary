# Academic REST API

Interactive Swagger documentation is served at `/api/docs/`, ReDoc at `/api/redoc/`, and the OpenAPI document at `/api/schema/`.

## Authentication

1. `POST /api/accounts/auth/token/` with `username` and `password`.
2. Send `Authorization: Bearer <access-token>`.
3. `POST /api/accounts/auth/token/refresh/` rotates a refresh token and blacklists the old token.

Access tokens include `role` and `name` claims. Unsafe operations are restricted to the relevant academic staff or management roles, while parent and student querysets are limited to linked learners.

## Resources

| Prefix | Resources |
|---|---|
| `/api/accounts/` | current user and manager-only user administration |
| `/api/academics/` | school profile, years, terms, departments, classes, streams, subjects, combinations, allocations, calendar |
| `/api/students/` | students, guardians, guardian links, enrolments, promotions |
| `/api/assessments/` | curriculum learning areas/topics/outcomes, named achievement scales, schemes, weekly plans, lessons, weighted assessments, project milestones, moderation, outcome/competency/skill/value ratings, portfolios and observations |
| `/api/exams/` | grade scales, sessions, examinations, S5–S6 weighted assessment plans/components, processed results, UNEB records and workflow transitions |
| `/api/attendance/` | attendance sessions, student records and teacher attendance |
| `/api/timetables/` | rooms, time slots and scoped timetable entries |
| `/api/communications/` | announcements, resources and personal notifications |
| `/api/reports/` | nested progress-report evidence and cumulative academic transcripts |

DRF routers provide `list`, `retrieve`, `create`, `update`, `partial_update`, and soft `destroy` where the caller's role permits them. Collections use page-number pagination (`page`, 25 records by default).

### Examination workflow

`POST /api/exams/examinations/{id}/transition/`

```json
{"operation": "submit"}
```

Valid operations are `submit`, `moderate`, `approve`, `publish`, `lock`, and `reopen`. State-order and management approval rules are enforced.

### Lower-secondary moderation workflow

`POST /api/assessments/assessments/{id}/workflow/`

Valid operations are `submit`, `hod_approve`, `hod_request_changes`, `dos_approve`, `dos_request_changes`, `lock`, and `reopen`. DOS approval makes marks, competency ratings, rubric ratings, learning-outcome ratings, skill/value ratings, and evidence read-only.

### Upper-secondary processing

Create an assessment plan and components whose active weights total 100%, approve the plan, then call:

`POST /api/exams/upper-assessment-plans/{id}/process/`

```json
{"term": 1, "stream": 1}
```

The response contains component breakdowns, weighted totals, grades, points, pass/fail state, missing-component warnings, subject positions, and class positions.

Processed upper-secondary results then use `POST /api/exams/upper-subject-results/{id}/transition/` with `moderate`, `approve`, `lock`, or `reopen`. Subject HOD moderation, DOS approval, and headteacher locking are role-checked separately.

Generate a cumulative transcript with `POST /api/reports/transcripts/generate/` and a `student` identifier.
