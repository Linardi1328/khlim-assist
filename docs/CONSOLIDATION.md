# KHLIM Assist consolidation into KHLIM Digital Ecosystem

KHLIM Assist is being transitioned from a standalone product repository into the AI customer-intelligence capability of `Linardi1328/khlim-digital-ecosystem`.

## Direction

The existing KHLIM Assist implementation remains valuable reference code for multilingual interpretation, knowledge retrieval, deterministic GREEN/YELLOW/RED decisions, provider portability, WhatsApp boundaries, and draft-only response handling. Those capabilities should be migrated incrementally rather than copied wholesale into the main platform.

The parent platform now owns the long-term product roadmap:

- AI assistant and knowledge retrieval;
- AI receptionist / enquiry handling;
- lead qualification and trial-booking proposals;
- permission-aware operational assistance;
- future sports intelligence;
- shared KHLIM identity, programme, membership, billing, scheduling, and audit data.

## Migration rules

1. KHLIM Digital Ecosystem remains the authoritative database and API platform.
2. KHLIM Assist must not create a second authoritative event, family, membership, payment, or scheduling database.
3. AI capabilities are disabled by default during migration.
4. Read tools may be enabled before write tools.
5. Mutating actions require explicit platform authorization and approval policy.
6. Restricted actions must remain unavailable to autonomous AI.
7. Existing tests and safety behavior in this repository should be preserved as migration references until equivalent coverage exists in the parent platform.

## Repository lifecycle

Do not delete or archive this repository yet. Keep it as a migration/reference repository until the parent platform has equivalent tested capabilities and migration acceptance has been recorded.
