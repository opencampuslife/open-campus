# Parity Fixtures

These fixtures are JSON-compatible YAML files so they can be parsed without adding a new runtime dependency.

## Categories

- `deterministic_error`: stable validation failures such as malformed JSON or missing fields.
- `deterministic_policy`: stable policy/compliance outcomes that should keep the same status and required error fields.
- `nondeterministic_success`: successful chat requests where exact LLM text may drift, so parity compares status plus required response fields.

## Privacy Rules

- Every case must include `privacy.sanitized=true`, `privacy.contains_pii=false`, and `privacy.reviewed_by`.
- Use synthetic identifiers such as `synthetic-*`, `parity-*`, or `test-*`.
- Do not include `authorization`, `cookie`, or `set-cookie`.
- Do not include real phone numbers, email addresses, ID numbers, internal IDs, or raw request/trace identifiers.

## Validation

Static fixture checks:

```bash
make test-parity-fixtures
```

Unit parity:

```bash
make test-go-parity-unit
```

Optional live parity with the sanitized fixture set:

```bash
make parity-gaokao-chat \
  GO_SHADOW_BASE_URL=http://127.0.0.1:8788 \
  PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787 \
  PARITY_FIXTURE_PATH=../tests/parity/gaokao_chat_real_sanitized.yaml
```
