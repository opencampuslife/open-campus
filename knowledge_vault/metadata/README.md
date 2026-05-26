# Metadata Rules

Every Markdown knowledge document must include YAML frontmatter:

- `title`
- `doc_id`
- `visibility`: `public`, `protected`, `internal`, or `admin`
- `allowed_roles`
- `data_level`: `L1`, `L2`, `L3`, or `L4`
- `campus_scope`
- `business_tags`
- `effective_date`
- `expiry_date`
- `owner`
- `review_status`: only `approved` content is retrievable in production
- `source_type`

Public answers may cite document titles and human-friendly source labels. They must not expose internal file paths or internal-only metadata.

