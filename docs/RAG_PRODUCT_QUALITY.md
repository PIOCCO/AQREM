# RAG product quality evaluation (26 questions)

Controlled policy documents live in `tests/fixtures/rag_eval/` (Documents A–C, conflict pair, injection probe).

## Run (requires Docker Postgres + pgvector)

```bash
docker compose up -d postgres redis
docker compose exec postgres psql -U aqrem -c "CREATE DATABASE aqrem_test;"
export TEST_DATABASE_URL=postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test
pip install -e backend[dev]

# Mock LLM (CI default)
python3 -m pytest tests/backend/test_rag_product_quality.py -v -s

# Live Azure (optional — incurs cost)
export LLM_PROVIDER=azure
# set AZURE_OPENAI_* ...
python3 -m pytest tests/backend/test_rag_product_quality.py -v -s
python3 scripts/azure_openai_smoke.py
```

The pytest module prints a pass/fail table to stdout and fails on any **Fail** row.

## UI upload path

The evaluation indexes fixtures through the same `index_files` pipeline used after source upload/sync. To validate UI upload end-to-end, upload the same `.md` files via **Projects → source → files** and re-run questions in Chat.

## Azure vs mock

| Mode | When | What it proves |
|------|------|----------------|
| `LLM_PROVIDER=mock` | Default CI | Retrieval + citation wiring; mock refuses weak grounding |
| `LLM_PROVIDER=azure` | Your deployment | Full generation quality against real deployments |

Never mark Azure as verified unless `azure_openai_smoke.py` succeeds.
