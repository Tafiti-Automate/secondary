# Ugandan curriculum alignment

Last reviewed: 1 July 2026.

This document records the curriculum assumptions enforced by the software. It is an implementation guide, not a replacement for NCDC syllabi, UNEB circulars, or school assessment policy.

## NCDC design rules implemented

1. **Generic skills are integrated.** Learning outcomes can be linked to one or more generic skills, and teachers capture evidence through the assessment/activity and its rubric. The six seeded generic skills are critical thinking and problem solving; creativity and innovation; communication; cooperation and self-directed learning; mathematical computation; and ICT proficiency.
2. **Values are cross-cutting by default.** The curriculum-value catalogue is separate from marks and seeds values as `is_assessed=False`. A school can document values without turning them into a free-standing percentage.
3. **Assessment starts from learning outcomes.** Framework → topic → learning outcome → Activity of Integration/project → assessment/evidence is explicit in the model.
4. **Evidence can be triangulated.** An assessment evidence record identifies observation, conversation, or product evidence and can attach an evidence file/reference.
5. **Rubrics are first-class records.** Rubrics contain criteria and achievement levels; each learner can receive criterion-level scores and feedback.
6. **Two assessment engines are explicit.** S1–S4 evidence is organised around learning outcomes, competencies, practical skills, values, observations and portfolios. S5–S6 can use an approved subject assessment plan whose coursework, practical and examination components total 100%. The earlier annual aligned-advanced policy remains available for schools using that route; examinations attached to a traditional upper-secondary component use the weighted plan instead.
7. **Missing is not zero.** A report result with absent required evidence has a null final score plus a reason. It receives no grade and blocks report publication until complete.
8. **Moderation is auditable.** Lower-secondary assessments move through teacher submission, HOD review and DOS approval. Approval records the reviewer and time and makes learner evidence read-only until an academic manager explicitly reopens it.
9. **Portfolios continue across classes.** Portfolio items belong to the learner and term, retain their class/subject context, and are not replaced during promotion.
10. **Achievement scales are school-configurable.** A named scale owns its ordered levels and can be selected by an assessment policy. Learning outcomes, generic skills, practical skills and observed values use those records; no national `1/2/3` or `Basic/Satisfactory/Excellent` algorithm is hardcoded.
11. **Every learning task can carry its own weight.** The assessment type supplies only a default. A teacher can override the weight on an AoI, practical, presentation or project, and continuous-assessment processing normalises the actual task weights instead of averaging every task in a category equally.
12. **Projects retain their learning process.** Project records distinguish individual, group, class, interdisciplinary, long-term and community work; assign a supervisor; define ordered milestones; and link milestone evidence to the learner portfolio and reflection workflow.

Authoritative curriculum references:

- [NCDC Lower Secondary Curriculum Framework](https://ncdc.go.ug/wp-content/uploads/2024/03/Curriculum_Framework.pdf)
- [NCDC curriculum and syllabus portal](https://ncdc.go.ug/)
- [NCDC statement on the aligned Advanced Secondary Curriculum](https://ncdc.go.ug/2025/10/08/ncdc-launches-2nd-international-conference-on-curriculum-development-2/)
- [Example NCDC Advanced Secondary syllabus showing learning outcomes, generic skills, assessment triangulation, rubrics, and Activities of Integration](https://www.ncdc.go.ug/wp-content/uploads/2025/03/IRE.pdf)

## UNEB records implemented

The system stores UCE/UACE candidate identity, centre/index number, candidate subjects, subject achievement, Activity of Integration, project/coursework records, evidence references, and draft → verified → approved → exported status. Approved records can be downloaded in an auditable workbook whose contents are hashed and retained as an export batch.

NCDC states that Lower Secondary final certification comprises `20%` school-based assessment from S3–S4 and `80%` end-of-cycle assessment. The software records that as a versioned UNEB-preparation policy; it does not incorrectly reuse the certification split as every school's term-report formula. Current UNEB guidance also confirms that subject CA and S3 project scores are required for UCE registration/certification, while the current circular, instrument and upload template remain the authority for exactly what a school submits in a given cycle.

This does **not** claim direct UNEB submission compatibility. UNEB may revise deadlines, subject codes, upload templates, and e-registration requirements. Before each examination cycle, an authorised school officer must compare the export with the current UNEB circular/template and use UNEB's authorised submission channel.

Authoritative examination references:

- [UNEB 2026 registration guidance and CA/project record reminder](https://uneb.ac.ug/2026/06/01/uneb-normal-registration-extended-to-30th-june-2026/)
- [NCDC teacher-support summary of the 20% school-based / 80% end-of-cycle certification split](https://ncdc.go.ug/wp-content/uploads/2025/04/Understanding-the-curriculum-materials-1.pdf)
- [UNEB circular on handling S3/S4 Continuous Assessment in 2026](https://uneb.ac.ug/2026/02/27/circular-on-handling-of-continuous-assessment-for-s-3-s-4-2026/)
- [UNEB S3 project theme for 2026](https://uneb.ac.ug/2026/02/18/project-theme-for-s-3-2026/)
- [UNEB official website and current circulars](https://uneb.ac.ug/)

## School go-live validation

Before first use, the Director of Studies should:

1. Import and verify every current topic and learning outcome for the subjects actually offered.
2. Configure class-specific assessment policies, grade scales, and promotion rules approved by the school.
3. Verify S5–S6 subject combinations and every candidate's individual subject registration.
4. Test missing-evidence, moderation, approval, report publication, locking, and UNEB export with a non-production cohort.
5. Sign off the wording and layout of report cards and the current UNEB pre-submission export.
