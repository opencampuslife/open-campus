# Permission Service

Permission is independent from memory organization.

## Inputs

- user role
- auth level
- campus
- department
- lead ownership
- requested action
- channel

## Output

```json
{
  "role": "parent",
  "campus": "zhengzhou",
  "auth_level": "phone_verified",
  "allowed_visibility": ["public", "protected"],
  "allowed_data_levels": ["L1", "L2"],
  "forbidden_tags": ["internal_pricing", "sales_script", "crm_rule"]
}
```

## Required Checks

- pre-retrieval SQL or metadata filter
- post-retrieval chunk validation
- output permission-leak check
- audit log for every denied or redacted item

