# Professional Implementation Notes

This build has been upgraded toward a full Ugandan secondary-school academic management workflow.

## CBC and upper-secondary engine expansion (2 July 2026)

- Added permanent student numbers alongside admission-year numbers, including migration of existing learners.
- Added curriculum learning areas and outcome-level assessment criteria, suggested activities and required evidence.
- Added schemes of work, weekly scheme rows and lesson plans tied to teacher subject allocations.
- Added learner outcome, practical-skill and value ratings, portfolios, observations and report-card summaries.
- Added teacher → HOD → DOS moderation. DOS-approved CBC evidence is read-only until explicitly reopened.
- Added S5–S6 subject assessment plans with 100%-validated weighted components, automatic processing, missing-component checks, grading and ranking.
- Added cumulative academic transcripts and restored the previously missing PDF report renderer.
- Added REST resources and role-aware querysets for the new records.
- Added migrations and regression tests for both assessment engines.

## Implemented in this revision

1. **Student report printing**
   - Improved the PDF report format for Ugandan secondary schools.
   - Added school address, EMIS number, UNEB centre number, attendance, class position, promotion decision, teacher remark, headteacher comment, and footer.
   - Added bulk class report-card download as a ZIP file of individual PDFs.

2. **Student movement / progression**
   - Added a bulk progression workflow for moving learners from one stream/class placement to another after term review.
   - The workflow records promotion/repeat/completion/deferred decisions.
   - It updates the learner's current stream where applicable.
   - It creates or updates the learner's enrolment in the destination academic year.
   - It includes a safeguard to exclude learners whose report cards still have missing marks.

3. **Dashboard improvements**
   - Added male/female learner count.
   - Added published reports count.
   - Added reports with missing marks count.
   - Added pending exam entries count.
   - Added class population breakdown.
   - Retained performance trends and attendance risk watchlist.

## New URLs

- `/students/promotions/bulk/` — Bulk learner progression / rollover
- `/reports/export/report-cards.zip?term=<term_id>&stream=<stream_id>` — Bulk class report-card PDF download

## Files changed

- `students/forms.py`
- `students/views.py`
- `students/urls.py`
- `templates/students/bulk_promotion.html`
- `templates/students/promotion_list.html`
- `reports/views.py`
- `reports/urls.py`
- `templates/reports/report_list.html`
- `config/views.py`
- `templates/dashboard.html`

## Validation

Python syntax was validated successfully using `py_compile` for the edited Python files. A full Django runtime check could not be executed in this environment because Django is not installed in the active container environment.
