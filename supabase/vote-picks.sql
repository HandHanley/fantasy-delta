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

-- Added 11 Nov 2026 (PREREG-crowd-values A1): vote COUNTS per player, so the page can show under-voted players more.
-- Returns counts only — never who won a pair.
create or replace function public.item_vote_counts(p_board text)
returns table (name text, votes bigint)
language sql stable security definer set search_path = public as $$
  select n, count(*) from (
    select a as n from public.vote_picks where board = p_board and pick is not null
    union all
    select b from public.vote_picks where board = p_board and pick is not null
  ) x group by n;
$$;

revoke all on function public.item_vote_counts(text) from public;
grant execute on function public.item_vote_counts(text) to anon, authenticated;

-- Added 26 Nov 2026 (PREREG-crowd-values A2): results per pair, so the page can pair players against their neighbours
-- in the crowd's CURRENT order (a player who keeps winning gets tested against better players). Totals only: no
-- device, time or tag. Run this once in the Supabase SQL Editor.
create or replace function public.pair_results(p_board text)
returns table (x text, y text, x_wins bigint, y_wins bigint)
language sql stable security definer set search_path = public as $$
  select least(a, b), greatest(a, b),
         count(*) filter (where pick = least(a, b)), count(*) filter (where pick = greatest(a, b))
  from public.vote_picks where board = p_board and pick is not null
  group by least(a, b), greatest(a, b);
$$;

revoke all on function public.pair_results(text) from public;
grant execute on function public.pair_results(text) to anon, authenticated;

-- Added 28 Nov 2026 (docs/PLAN-your-rankings.md, step 1): a device's OWN picks, so it can build Your Rankings,
-- including votes cast before this existed. It returns only the picks of the device IDs it is given. A device ID is a
-- long random code that only that device holds (dv_session), so nobody can look up anyone else's votes without it.
-- Picks only: no times, tags or other devices. At most 10 device IDs per call. Run this once in the Supabase SQL Editor.
create or replace function public.my_picks(p_board text, p_sessions text[])
returns table (a text, b text, pick text)
language sql stable security definer set search_path = public as $$
  select v.a, v.b, v.pick from public.vote_picks v
  where v.board = p_board and v.pick is not null
    and coalesce(array_length(p_sessions, 1), 0) between 1 and 10
    and v.session = any (p_sessions)
    and char_length(v.session) >= 8
  order by v.id;
$$;

revoke all on function public.my_picks(text, text[]) from public;
grant execute on function public.my_picks(text, text[]) to anon, authenticated;
