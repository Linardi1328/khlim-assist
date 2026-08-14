# Security And Privacy

KHLIM Assist must minimize participant data exposure from the start.

## Data Minimization

Collect only information needed for the support task. Do not ask for extra child, team, payment, address, or identity details when a general FAQ answer is enough.

## Sensitive Information

Do not put participant-sensitive data into AI knowledge files, tests, fixtures, logs, or documentation. This includes:

- IC numbers
- passport numbers
- bank details
- payment-card information
- precise home addresses
- unnecessary child information
- participant identities
- phone numbers
- raw historical WhatsApp conversations

## Separation

Maintain conceptual separation between:

```text
KHLIM KNOWLEDGE
```

and

```text
PARTICIPANT DATA
```

KHLIM knowledge includes event rules, dates, fees, public registration links, check-in rules, and response style. Participant data includes registration records, payment status, order status, messages, and handoff context.

## Logging

Never log:

- API keys
- access tokens
- Meta secrets
- OpenAI secrets
- raw sensitive participant content unless there is a justified operational reason

Audit logs should capture event type, entity reference, actor type, and safe metadata only. Secret values must not be included in audit metadata.

## Human Authority

AI must not approve:

- refunds
- exceptions
- disciplinary decisions
- schedule changes
- special eligibility
- reserved slots
- withdrawals

A future verified workflow may support structured approvals, but Phase 0 does not grant that authority.

## Phase 0 External Services

The app can start without Meta or OpenAI credentials. External-service clients fail gracefully when credential-requiring functionality is called. Automated tests must not call external APIs.
