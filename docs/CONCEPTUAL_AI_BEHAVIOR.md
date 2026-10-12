# Conceptual AI behavior (missing evidence & outcomes)

## Structured outcomes

Chat `/api/v1/chat/ask` responses include `outcome` (see `AnswerOutcome` in `backend/app/models/enums.py`):

| Outcome | Meaning |
|---------|---------|
| `answered` | Evidence supports the response |
| `partially_answered` | Some aspects answered; others missing in retrieved evidence |
| `insufficient_evidence` | No adequate match in authorized indexed sources (not proof of global absence) |
| `conflicting_evidence` | Material contradiction across sources; review recommended |
| `clarification_required` | Question too vague to interpret |
| `access_denied` | Policy/security refusal (credentials, other tenants, jailbreak-style asks) |
| `source_unavailable` | Retrieval/search failed (distinct from empty results) |
| `action_not_supported` | User asked for an operation chat cannot perform |

Additional fields: `missing_information`, `next_steps`, `needs_review`, `conflicts`.

## Tests

```bash
# Unit only (no database)
python3 -m pytest tests/backend/test_conceptual_ai_behavior.py::TestBehaviorPure -q

# Full conceptual suite (PostgreSQL + pgvector)
export TEST_DATABASE_URL=postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test
python3 -m pytest tests/backend/test_conceptual_ai_behavior.py -q
```

Mock LLM is used unless `LLM_PROVIDER=azure` with valid credentials.
