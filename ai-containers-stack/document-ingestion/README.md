# Maritime document ingestion

Local-only ingestion pipeline for the project-cargo knowledge base in Supabase PostgreSQL.

## Data model

- `public.knowledge_documents`: source identity, checksum, aliases and Codex-curated metadata.
- `public.knowledge_chunks`: page-aware text chunks plus normalized 384-dimensional embeddings.
- `public.match_knowledge_chunks(...)`: cosine-similarity retrieval function intended for an MCP tool.

The embedding model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, executed locally through FastEmbed. It supports cross-language searches between Romanian and English. No document text is sent to a cloud embedding service.

## Commands

Run from the repository root with the Python 3.11 virtual environment:

```sh
.venv-document-ingest311/bin/python document-ingestion/ingest.py FILE...
.venv-document-ingest311/bin/python document-ingestion/search.py "Romanian or English query" 8
```

The importer is checksum-idempotent: re-importing the same source replaces its document and chunks. Identical files are stored once, with duplicate paths recorded as aliases.

Apply these migrations before a first import:

```text
supabase/migrations/003_maritime_knowledge.sql
supabase/migrations/004_maritime_document_metadata.sql
```

PDF extraction uses Poppler `pdftotext`; DOCX uses macOS `textutil`; XLSX extraction reads OpenXML directly.
