# Evolution architecture

This layer is designed so the school can adopt new NCDC policies, UNEB formats and teaching practices without replacing the application. Stable learner identities and historical records remain intact while policy-heavy configuration is versioned.

## Module boundaries

| Module | Durable record | What can evolve safely |
|---|---|---|
| Students | Permanent learner ID and chronological timeline | Accommodations, interests, achievements, enrolments, movement and support events |
| Academics | Academic years, classes, subjects and allocations | Draft, published, retired and superseding curriculum frameworks |
| Assessments | Evidence tied to learner, outcome and term | Scales, rubrics, observations, project teams and image/audio/video/document evidence |
| Examinations | Moderated and locked school results | Internal examination policies and dated UNEB export adapter versions |
| Reports | Published report cards and transcript entries | Longitudinal outcome, skill, competency, attendance and cohort-comparison views |
| Attendance | Idempotent capture event | Web, offline, QR and external biometric-provider sources; alert and intervention workflows |
| Timetables | Preserved approved entries | Scheduling constraints and auditable generation/simulation runs |
| Communications | Auditable message, consent and broadcast | Languages, translations, channels, audiences and delivery providers |

## Important invariants

- Historical records point to the curriculum, policy, adapter and academic period that applied at the time; a reform creates a successor version instead of rewriting history.
- Published or approved academic evidence is not silently overwritten.
- Offline attendance retries use the same capture UUID, making repeated synchronisation idempotent.
- Biometric templates are not stored in this application. Only a provider reference is retained, and biometric use should have an appropriate consent record.
- Timetable generation preserves manual entries. Any lesson that cannot satisfy the current constraints is reported as an unresolved gap.
- A conversation is visible only to its participants. Parent and learner participant/learner choices are restricted to their communication scope.
- External email, SMS and WhatsApp notifications enter a pending delivery queue; a production provider worker must deliver them and write back delivery status.

## Operational workflows

### Curriculum reform

1. Create a draft framework with a source reference, effective date and optional predecessor.
2. Import authorised topic/outcome data into the draft.
3. Validate coverage with `check_school_readiness` and school curriculum owners.
4. Publish the successor. The predecessor is retired but remains attached to historical records.

### Offline attendance

1. Open a register while connected.
2. If connectivity drops, select **Save on this device**. The browser keeps one UUID per learner capture.
3. When connected, select **Sync saved records**. Successful UUIDs leave the local queue; failed items remain for review.
4. Repeated absences create an alert that staff can assign and connect to interventions.

### Timetable generation

1. Configure lesson slots, rooms and subject allocations.
2. Add scheduling requirements for laboratories, preferred rooms, allowed days and daily subject limits.
3. Simulate first and resolve reported capacity gaps.
4. Generate. Existing entries stay untouched and every run retains its result summary.

### Emergency communication

1. Prepare the original message and optional translations keyed by language.
2. Choose severity, audience and channels.
3. Review and send. In-app messages are immediate; external channels are queued.
4. Review the delivery summary and provider delivery states.

## Still required for production

The models and workflows are an extensible foundation, not a substitute for governance or infrastructure. Before school use, complete authorised NCDC data, configure and approve current UNEB adapters, connect and monitor external delivery/identity providers, validate retention and consent policies, complete the production-readiness gate, test backups/restoration, and run school acceptance testing.
