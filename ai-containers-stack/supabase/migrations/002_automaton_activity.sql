begin;

create table if not exists public.automaton_activity (
  id bigint generated always as identity primary key,
  automaton_name text not null default 'conway-automaton',
  source text not null,
  event_type text not null,
  status text not null
    check (status in ('setup', 'online', 'sleeping', 'degraded', 'offline', 'error')),
  summary text not null,
  details jsonb not null default '{}'::jsonb,
  recorded_at timestamptz not null default now()
);

create index if not exists automaton_activity_recorded_at_idx
  on public.automaton_activity(recorded_at desc);

create index if not exists automaton_activity_event_type_idx
  on public.automaton_activity(event_type, recorded_at desc);

comment on table public.automaton_activity is
  'Append-only operational activity for the isolated Conway Automaton container.';

commit;
