# Security Policy

## Supported Versions

| Version | Supported |
|----------|-----------|
| main     | ✅ Active |
| staging  | ✅ Pre-release |

## Reporting a Vulnerability

**Do not open a public issue.** Report security vulnerabilities to the maintainers privately.

We take security seriously. The following measures are in place:

### Secret Protection
- **Push Protection**: GitHub Secret Scanning with Push Protection is enabled. Commits containing secrets will be blocked.
- **Custom Patterns**: Detects `WECOM_SECRET`, `WECOM_ENCODING_AES_KEY`, `DATABASE_URL`, `VENDOR_CONFIRM_TOKEN`, `APP_SESSION_SECRET`, and other sensitive tokens.
- **Pre-commit guard**: `.env` and credential files are in `.gitignore`.

### Supply Chain
- **Dependency Review**: PRs are automatically scanned for dependency vulnerabilities. High-severity findings block merging.
- **Dependabot**: Automated updates for pip, npm, gomod, Docker, and GitHub Actions. Alerts for known vulnerabilities.
- **Pinned hashes**: GitHub Actions use pinned commit hashes where possible.

### Code Security
- **CodeQL Analysis**: Multi-language static analysis (Go, Python, JavaScript/TypeScript) runs on every PR. Queries: `security-extended`.
- **SQL Injection**: All SQL uses parameterized queries via psycopg2. String-concatenated SQL is blocked by CI policy check.
- **Row-Level Security**: Database policies are enforced via PostgreSQL RLS with multi-role access (public, staff, admin).

### Application Security
- **Prompt Injection**: LLM gateway includes prompt injection detection and guard rails.
- **Tone Policy**: Agent responses are validated against institutional tone contracts.
- **Privacy Gate**: Shadow proxy parity comparisons redact sensitive fields before evidence writing.
- **Rate Limiting & Circuit Breaking**: Go control plane enforces per-route rate limits and upstream circuit breakers.

### Compliance
- **Evidence Bundle**: All shadow proxy and parity comparisons produce JSONL evidence with audit trails.
- **Cutover Readiness**: Staged migration requires passing evidence gates (parity rate ≥ 0.995, no privacy violations, latency/error deltas within threshold).

### Branch Protection (recommended)
- Require pull request reviews before merging
- Require status checks before merging:
  - `release-check` (full release gate)
  - `go-control-plane` (Go tests)
  - `python-campus-modules` (campus tests)
  - `admin-console` (frontend typecheck)
  - `codeql` (security analysis)
  - `dependency-review` (supply chain)
- Require linear history
- Require conversation resolution

## Security Checks in CI

| Check | Purpose | Required? |
|-------|---------|-----------|
| `release-check` | Full test suite + freeze gates + policy | Yes |
| `go-control-plane` | Go tests, race detector, vet | Yes |
| `python-campus-modules` | Campus module + WeCom tests | Yes |
| `admin-console` | TypeScript typecheck | Yes |
| `codeql` | SAST for Go, Python, JS/TS | Yes |
| `dependency-review` | Block vulnerable dependencies | Yes |
| Secret Scanning | Block secret leakage | Yes (repo setting) |
