#!/usr/bin/env bash
# Resize pgvector columns to EMBEDDING_DIMENSIONS (local-prod / Raspberry Pi stack).
# Existing vectors are cleared (they were built for the old size); click
# "Re-index all documents" afterwards (Admin > Documents).
#
# Usage: scripts/migrate-embedding-dimensions.sh 1536
set -euo pipefail
DIM="${1:-}"
if ! [[ "$DIM" =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 <dimensions>   e.g. $0 1536" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f ${COMPOSE_FILE:-docker-compose.local-prod.yml}"
DB_NAME="${DB_NAME:-aqrem}"
echo "Resizing vector columns in database '$DB_NAME' to vector($DIM)..."
$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U aqrem -d "$DB_NAME" <<SQL
ALTER TABLE evidence_items ALTER COLUMN embedding TYPE vector($DIM) USING NULL;
UPDATE evidence_items SET metadata = metadata - 'embedding_model' - 'embedding_dimensions' WHERE metadata IS NOT NULL;
ALTER TABLE answer_library_entries ALTER COLUMN question_embedding TYPE vector($DIM) USING NULL;
UPDATE client_documents SET embedding_model = NULL, embedding_dimensions = NULL;
SQL
echo "Done. Now set EMBEDDING_DIMENSIONS=$DIM in .env, restart api/worker, then Admin > Documents > Re-index all documents."
