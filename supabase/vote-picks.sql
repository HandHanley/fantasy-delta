-- fantasydelta.com/vote/ — "Who Would You Rather Have?" (10 Nov 2026)
-- Run once in Supabase: SQL Editor -> New query -> paste all of this -> Run.
-- Safe to run again: it only creates what is missing.
--
-- What it allows, through the site's publishable key:
--   * anyone can ADD a vote (one row per tap or skip);
--   * nobody can READ, CHANGE or DELETE votes;
--   * one function, vote_share(a, b), returns how many people picked each side of a pair.
-- The raw table is read only from the Supabase dashboard (or the secret key, which never goes in the repo).

create table if not exists public.vote_picks (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  board       text not null check (char_length(board) between 1 and 20),     -- which player list, e.g. 2026-11-10
  session     text not null check (char_length(session) between 8 and 64),   -- random id kept on the voter's device
  tag         text not null default 'organic' check (tag in ('organic', 'owner')),
  a           text not null check (char_length(a) between 1 and 60),         -- left/top card
  b           text not null check (char_length(b) between 1 and 60),         -- right/bottom card
  pick        text check (pick is null or pick = a or pick = b),              -- null = skipped
  pair_type   text check (pair_type in ('close', 'random', 'gimme')),
  ms          integer check (ms is null or ms between 0 and 3600000),         -- time from showing the pair to the tap
  check (a <> b)
);

create index if not exists vote_picks_pair on public.vote_picks (least(a, b), greatest(a, b));
create index if not exists vote_picks_session on public.vote_picks (session, created_at);

alter table public.vote_picks enable row level security;

drop policy if exists "anyone can add a vote" on public.vote_picks;
create policy "anyone can add a vote" on public.vote_picks
  for insert to anon, authenticated with check (true);
-- No select, update or delete policies: through the site, votes can be added and never read back.

create or replace function public.vote_share(p_a text, p_b text)
returns table (a_votes bigint, b_votes bigint)
language sql stable security definer set search_path = public as $$
  select count(*) filter (where pick = p_a), count(*) filter (where pick = p_b)
  from public.vote_picks
  where least(a, b) = least(p_a, p_b) and greatest(a, b) = greatest(p_a, p_b) and pick is not null;
$$;

revoke all on function public.vote_share(text, text) from public;
grant execute on function public.vote_share(text, text) to anon, authenticated;
