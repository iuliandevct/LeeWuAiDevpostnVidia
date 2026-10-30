create table if not exists public.knowledge_documents (
  id uuid primary key,
  filename text not null,
  source_path text not null,
  media_type text not null,
  sha256 text not null unique,
  title text,
  page_count integer,
  byte_size bigint not null,
  language text,
  domain text not null default 'maritime_cargo_securing',
  metadata jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.knowledge_chunks (
  id uuid primary key,
  document_id uuid not null references public.knowledge_documents(id) on delete cascade,
  chunk_index integer not null,
  page_from integer,
  page_to integer,
  heading text,
  content text not null,
  token_estimate integer not null,
  embedding double precision[] not null,
  embedding_model text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create index if not exists knowledge_chunks_document_idx
  on public.knowledge_chunks(document_id, chunk_index);

create index if not exists knowledge_chunks_content_fts_idx
  on public.knowledge_chunks using gin (to_tsvector('english', content));

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'knowledge_chunks_embedding_384_dims'
  ) then
    alter table public.knowledge_chunks
      add constraint knowledge_chunks_embedding_384_dims
      check (cardinality(embedding) = 384);
  end if;
end $$;

create or replace function public.array_cosine_similarity(a double precision[], b double precision[])
returns double precision
language sql
immutable
strict
as $$
  select case
    when sqrt(sum(x * x)) = 0 or sqrt(sum(y * y)) = 0 then 0
    else sum(x * y) / (sqrt(sum(x * x)) * sqrt(sum(y * y)))
  end
  from unnest(a, b) as t(x, y);
$$;

create or replace function public.match_knowledge_chunks(
  query_embedding double precision[],
  match_count integer default 10,
  document_filter uuid default null
)
returns table (
  chunk_id uuid,
  document_id uuid,
  filename text,
  page_from integer,
  page_to integer,
  content text,
  similarity double precision
)
language sql
stable
as $$
  select c.id, c.document_id, d.filename, c.page_from, c.page_to, c.content,
         public.array_cosine_similarity(c.embedding, query_embedding) as similarity
  from public.knowledge_chunks c
  join public.knowledge_documents d on d.id = c.document_id
  where document_filter is null or c.document_id = document_filter
  order by public.array_cosine_similarity(c.embedding, query_embedding) desc
  limit greatest(match_count, 1);
$$;

comment on table public.knowledge_documents is
  'Source documents for the local maritime/project-cargo knowledge base.';
comment on table public.knowledge_chunks is
  'Page-aware chunks and normalized local embeddings for semantic retrieval.';
