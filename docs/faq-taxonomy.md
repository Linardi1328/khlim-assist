# FAQ Taxonomy

The FAQ master separates generalized question families from event-specific facts. Changing details such as fees, dates, links, deadlines, and category rules must come from event configuration or trusted systems.

## Categories

- `REGISTRATION`
- `FEES`
- `TEAM_COMPOSITION`
- `ELIGIBILITY`
- `PLAYER_RESTRICTIONS`
- `SCHEDULE`
- `RULES`
- `CHECK_IN`
- `PAYMENT`
- `WITHDRAWAL`
- `MERCHANDISE`
- `TECHNICAL`
- `COMMERCIAL`
- `GENERAL`

## Handling Modes

- `AUTO`: may be answered when the referenced event knowledge is confirmed and no human authority is required.
- `CLARIFY`: the participant request is understandable but missing needed fields, such as birth year or category.
- `LOOKUP`: a trusted system must be checked, such as payment status, registration status, or merchandise order status.
- `HUMAN`: a PIC must decide or respond.

## General Category Guidance

- `REGISTRATION`: links, deadline, and open/closed status are usually `AUTO`; registration status is `LOOKUP`; late registration is `HUMAN`.
- `FEES`: published event fees are usually `AUTO`; refunds and overpayment are `HUMAN`.
- `TEAM_COMPOSITION`: published player count rules are usually `AUTO`.
- `ELIGIBILITY`: normal rule checks can be `AUTO` when category and birth year are present; incomplete questions are `CLARIFY`; exceptions and disputes are `HUMAN`.
- `PLAYER_RESTRICTIONS`: published foreign-player or national-player policies are usually `AUTO`.
- `SCHEDULE`: published dates are usually `AUTO`; schedule change requests are `HUMAN`.
- `RULES` and `CHECK_IN`: published links or check-in rules are usually `AUTO`.
- `PAYMENT`: confirmation requires `LOOKUP`; refunds, overpayment, and wrong-amount handling require `HUMAN`.
- `WITHDRAWAL`: withdrawal and walkover consequences require `HUMAN`.
- `MERCHANDISE`: published item details are `AUTO`; order-specific status or delivery changes are `LOOKUP`.
- `TECHNICAL`: form issues usually need `CLARIFY` first and may route to registration.
- `COMMERCIAL`: booth/vendor enquiries require `HUMAN`.
