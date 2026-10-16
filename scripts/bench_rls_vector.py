"""Measure RLS overhead on the pgvector retrieval query (EXPLAIN ANALYZE). Local benchmarking only.

    BENCH_ADMIN_URL=postgresql+psycopg://aqrem:aqrem@localhost:5432/postgres \
    python scripts/bench_rls_vector.py --orgs 10 --rows-per-org 5000 --dim 1536

Creates a throwaway database ``aqrem_rls_bench``, runs migrations (incl. RLS), seeds random
vectors, compares: superuser (RLS bypassed) vs non-superuser app role (RLS enforced), and drops
the database afterwards.
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

DB = "aqrem_rls_bench"
ROLE = "aqrem_rls_bench_app"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orgs", type=int, default=10)
    ap.add_argument("--rows-per-org", type=int, default=5000)
    ap.add_argument("--dim", type=int, default=1536)
    ap.add_argument("--runs", type=int, default=7)
    a = ap.parse_args()
    admin_url = make_url(os.environ.get("BENCH_ADMIN_URL", "postgresql+psycopg://aqrem:aqrem@localhost:5432/postgres"))
    os.environ["EMBEDDING_DIMENSIONS"] = str(a.dim)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    pw = uuid.uuid4().hex
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
        c.execute(text(f"CREATE DATABASE {DB}"))
        c.execute(text(f"DROP ROLE IF EXISTS {ROLE}"))
        c.execute(text(f"CREATE ROLE {ROLE} LOGIN NOBYPASSRLS PASSWORD '{pw}'"))
    su = create_engine(admin_url.set(database=DB))
    try:
        from app.db.migrate import run_migrations

        run_migrations(su)
        with su.begin() as c:
            c.execute(text(f"GRANT USAGE ON SCHEMA public TO {ROLE}"))
            c.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ROLE}"))
            c.execute(text(f"GRANT aqrem_rls_control TO {ROLE}"))
            orgs = [uuid.uuid4() for _ in range(a.orgs)]
            for o in orgs:
                s = uuid.uuid4()
                c.execute(text("INSERT INTO sources (id, organization_id, name, source_type, scope, status, config, "
                               "visibility_mode) VALUES (:s, :o, 'b', 'upload', 'organization', 'ready', '{}', "
                               "'all_members')"), {"s": s, "o": o})
                c.execute(text(
                    "INSERT INTO evidence_items (id, organization_id, source_id, source_type, scope, file_name, "
                    "file_path, content, content_type, chunk_index, content_hash, metadata, visibility_mode, embedding) "
                    "SELECT gen_random_uuid(), :o, :s, 'upload', 'organization', 'f', 'f', 'x', 'text/plain', g, 'h', "
                    "'{}', 'all_members', (SELECT array_agg(random())::real[]::vector FROM generate_series(1, :d) "
                    "WHERE g > 0) FROM generate_series(1, :n) g"), {"o": o, "s": s, "d": a.dim, "n": a.rows_per_org})
            c.execute(text("ANALYZE evidence_items"))
        q = "[" + ",".join("0.5" for _ in range(a.dim)) + "]"
        target = orgs[0]
        sql_app = ("EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM evidence_items WHERE organization_id = CAST(:o AS uuid) "
                   "ORDER BY embedding <=> CAST(:q AS vector) LIMIT 20")
        sql_rls_only = ("EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM evidence_items "
                        "ORDER BY embedding <=> CAST(:q AS vector) LIMIT 20")
        app = create_engine(admin_url.set(database=DB, username=ROLE, password=pw))

        def run(engine, sql, label):
            times, plan = [], None
            for _ in range(a.runs):
                with engine.begin() as c:
                    c.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(target)})
                    lines = [r[0] for r in c.execute(text(sql), {"o": str(target), "q": q})]
                    times.append(float(re.search(r"Execution Time: ([\d.]+)", "\n".join(lines)).group(1)))
                    plan = [re.sub(r"'\[[^']*\]'", "'[query vector]'", ln) for ln in lines]
            med = statistics.median(times[1:])  # drop first (cold)
            print(f"\n== {label}: median {med:.2f} ms (runs: {', '.join(f'{t:.1f}' for t in times)})")
            print("\n".join(plan))
            return med

        print(f"dataset: {a.orgs} orgs x {a.rows_per_org} rows, dim {a.dim}; query top-20 for one org")
        base = run(su, sql_app, "NO RLS (superuser bypass) + app WHERE organization_id")
        rls = run(app, sql_app, "RLS enforced (app role) + app WHERE organization_id")
        rls_only = run(app, sql_rls_only, "RLS enforced (app role), no app filter")
        print(f"\nSUMMARY no_rls={base:.2f}ms rls+filter={rls:.2f}ms ({(rls / base - 1) * 100:+.1f}%) "
              f"rls_only={rls_only:.2f}ms ({(rls_only / base - 1) * 100:+.1f}%)")
        app.dispose()
    finally:
        su.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
            c.execute(text(f"DROP ROLE IF EXISTS {ROLE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
