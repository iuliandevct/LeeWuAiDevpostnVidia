#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastembed import TextEmbedding

from ingest import MODEL, env_file


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: search.py QUERY [LIMIT]", file=sys.stderr)
        return 2
    query = sys.argv[1]
    limit = max(1, min(int(sys.argv[2]) if len(sys.argv) > 2 else 8, 50))
    vector = next(iter(TextEmbedding(model_name=MODEL).query_embed(query)))
    literal = "{" + ",".join(f"{float(value):.8g}" for value in vector) + "}"
    root = Path(__file__).resolve().parents[1]
    settings = env_file(root / ".env")
    sql = f"""
select round(similarity::numeric, 4) as score,
       filename,
       concat_ws('-', page_from::text, nullif(page_to, page_from)::text) as pages,
       left(regexp_replace(content, E'[\\n\\r]+', ' ', 'g'), 260) as excerpt
from public.match_knowledge_chunks('{literal}'::double precision[], {limit});
"""
    process_env = os.environ.copy()
    process_env["PGPASSWORD"] = settings["SUPABASE_DB_PASSWORD"]
    result = subprocess.run([
        "/usr/local/opt/postgresql@15/bin/psql", "-X", "-P", "pager=off",
        "-h", "127.0.0.1", "-p", settings.get("SUPABASE_DB_PORT", "54322"),
        "-U", settings["SUPABASE_DB_USER"], "-d", settings["SUPABASE_DB_NAME"],
        "-c", sql,
    ], env=process_env)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
