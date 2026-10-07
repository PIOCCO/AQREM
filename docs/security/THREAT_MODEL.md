# Threat Model (STRIDE summary)

| Threat | Example | Mitigations in AQREM |
|--------|---------|----------------------|
| **Spoofing** | Stolen JWT | HTTPS, short-ish token TTL, org header + membership check |
| **Tampering** | Mass-assignment | Pydantic schemas; explicit fields on create/update |
| **Repudiation** | Deny approval | Audit log for answer/project/source actions |
| **Information disclosure** | Cross-tenant IDOR | Org filters on queries; 404 cross-org; citation allowlist |
| **Information disclosure** | Prompt/secret leak via LLM | System prompt rules; no secrets in evidence pipeline |
| **Denial of service** | LLM cost abuse | Auth required for generate; rate limits; token caps |
| **Elevation of privilege** | VIEWER approves answer | `require_role(REVIEWER)` on approve/edit |
| **Prompt injection** | Malicious PDF text | Sanitize + untrusted markers; not sole control |
| **RAG poisoning** | Bad indexed doc | Same as injection; re-index/staleness workflows |
| **Supply chain** | Vulnerable deps | Run `./scripts/run-security-checks.sh`; add CI scans |

### Account takeover

- Weak passwords — mitigate with policy/MFA (future); rate-limited login.

### Cross-tenant leakage

- Primary control: `organization_id` on all tenant tables + dependency injection.
- Tests: `test_security_authorization.py`, existing tenant isolation tests.

### AI cost abuse

- Unauthenticated generate blocked (401).
- Rate limits on generate and retrieval preview.

### Secret theft

- No secrets in frontend bundle; `.env` gitignored; Terraform outputs non-secret only.
