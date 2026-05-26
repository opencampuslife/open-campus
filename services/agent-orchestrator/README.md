# Agent Orchestrator

The orchestrator replaces a generic personal-assistant loop with an admissions consultation state machine.

## State Machine

```text
NEW
  -> IDENTIFY
  -> PROFILE
  -> INTENT
  -> RETRIEVE
  -> ANSWER
  -> VERIFY
  -> ACTION
  -> FOLLOWUP
  -> CLOSED
```

## Turn Contract

1. Identify user role, auth level, campus, lead ownership, and channel.
2. Build permission scope from RBAC + ABAC + data level rules.
3. Load session summary and student or parent profile.
4. Classify intent and extract entities.
5. Detect high-risk requests before retrieval.
6. Rewrite query for retrieval.
7. Retrieve allowed evidence only.
8. Generate answer with citations.
9. Run compliance and permission-leak checks.
10. Update profile and CRM if allowed.
11. Write audit events.

## High-Risk Handoff Triggers

- asks for guaranteed admission or guaranteed score increase
- asks for internal discounts, quota, or unpublished policy
- asks for another student's private information
- expresses complaint, legal threat, or safety concern
- asks the agent to bypass school policy

