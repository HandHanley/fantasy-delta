# Plan: Your Rankings (And Using Them In The Trade Calc)

Drafted 28 Nov 2026. Steve's decisions on the open questions are in **Decided (28 Nov)** at the end. Nothing is built yet.

## Why

Right now voting gives you one thing back: a line saying what share of voters agreed with you. That's gone in a
second, so there's little reason to keep voting once the push to 5,000 ends. This gives every voter something that's
theirs and gets better the more carefully they vote:

1. **Your Rankings:** your own board, built from your picks, showing where you disagree with the crowd.
2. **Your Rankings in the Trade Calc:** an optional column that judges a trade by your board.

Both are for anyone. No login needed. A login keeps them safe and puts them on every device (step 3).

## What Stays The Same

- **The crowd board.** How it's fitted, weighted and priced (`docs/PREREG-crowd-values.md`) doesn't change. Your
  Rankings only read the votes; they never feed back into the crowd's board.
- **The Trade Calc's default.** Market and DELTA Value columns and the verdict work exactly as now. Your Rankings is
  an extra you switch on. The pre-registration says the Trade Calc doesn't change on crowd votes, and it doesn't:
  this is your opinion beside the existing numbers, not a replacement for them.
- **DELTA's model.** No value, score or engine number changes. Engine Audit should still read 32/32 after each step.

## How Your Rankings Are Built (Plain Version)

Start with the crowd's current order. Then let your picks push players up or down from there. If you've taken Olave
over Jefferson, Olave moves up your board and Jefferson moves down. Players you've never voted on stay where the crowd
has them.

That means 25 votes gives a sensible board right away rather than a random one, and every extra vote makes it more
yours. It's the same method the vote page already uses to pair players (`crowdOrder` in `delta-vote.js`), with the
crowd's order as the starting point instead of the page's.

**Prices:** the same frozen value curve the crowd board uses. Your 1st player is 10,000, your 10th about 7,900, your
50th 3,420. So "your value" means "what that spot in line is worth," the same way the crowd board works. No market
numbers.

**Coverage:** only the 159 players and picks on the vote list. Anyone else shows "Not On The Vote List."

## Step 1: Your Rankings View

**Where:** its own tab in My Team, beside Roster, Trade Calc, Mock Draft and Watchlist, because it's yours rather than
the crowd's. The vote page and the Market tab's vote card get a "See Your Rankings" button that opens it. Before your
25th vote, the button reads as a counter ("Your Rankings unlock in 7 votes"). My Team then has five tabs, the same
count as the NFL row, so the phone tab strip gets checked at 390px wide.

**What you see:**
- **Where You Disagree With The Crowd** first: the 5 players you're highest on and the 5 you're lowest on compared
  with the crowd, in plain words ("You have Olave as your WR6. The crowd has him at WR11").
- Then your board by position, **showing only players you've voted on**, with the Early Crowd Rankings position rank
  beside each. Ranks are still worked out against the whole board, so "your WR6" means sixth among all receivers,
  not sixth among the ones you've seen.
- A line underneath: "You've ranked 38 of 159 players. Keep voting to fill in your board."

The share picture is step 1b, unlocked at 50 votes.

**Your past votes count.** Votes already cast on a device are stored in the database under that device's ID, so a new
database function returns this device's own picks, and everyone who's already voted gets their board on day one. Picks
are also kept on the device from now on, so the board still loads if the database is slow.

**Files:**
- `supabase/vote-picks.sql`: new `my_picks(p_sessions)` function. Returns only the picks for the device IDs it's
  given. A device ID is a long random code that only that device knows, so nobody can look up anyone else's votes.
  Steve runs it in Supabase before the upload.
- `delta-vote.js`: keep this device's picks, fetch past ones, build the personal board.
- `vote/index.html` and `index.html`: the button, the view and the share picture.

## Step 1b: The Share Picture (50 Votes)

- At your 50th vote: "Share Your Hot Takes" draws a picture of your 5 biggest disagreements with the crowd (same kit
  as the Trade Calc's share image).
- If you're signed out, a small second prompt sits beside it: "Sign in so your board follows you."

**Files:** `index.html`, `vote/index.html`.

## Step 2: The Trade Calc Toggle

- A "Use Your Rankings" switch in the Trade Calc, shown once you have a board. Off by default; the choice stays on
  this device like other display settings.
- When it's on, each player shows a third number, "Yours," and a short line under the verdict, for example: "By Your
  Rankings: Team A wins by 1,200." The main verdict doesn't change.
- A player you haven't voted on uses the crowd's value, labelled "Crowd," so trades still add up.
- If any player in the trade isn't on the vote list, that line says so instead of giving a partial total.

**Files:** `index.html` only.

## Step 3: Sign In To Keep Them

- **The prompt:** right after the 25th vote, when Your Rankings first unlocks: "Your Rankings are ready. Sign in to
  keep them on every device." Shown once per device, never blocking the vote.
- **What signing in does:** the account remembers each device ID you've signed in from, so your board combines your
  votes from your phone and your laptop and survives a cleared browser or a new phone. This uses the existing sync
  (`delta-sync.js`) as a backup, the same way watchlists work. Your Rankings are your data, like a watchlist, so they
  travel with your account. Display settings, including the Trade Calc switch, still stay per device.
- **Tagging signed-in votes:** a new `signed_in` yes/no column on `vote_picks`, so we can later check whether
  signed-in voters vote differently (more carefully, closer to where the market ends up). It's counted only. The crowd
  board ignores it, and any change to how those votes are weighted would go through a written amendment first.
- **Not changed:** the crowd board still treats each device as one voter. Linking devices to an account doesn't merge
  them on the crowd board.

**Files:** `supabase/vote-picks.sql` (column, plus an account-to-device table with row-level security),
`delta-sync.js`, `delta-vote.js`, `index.html`, `vote/index.html`.

## Order And Checks

Each step ships and gets eye-tested on its own, phone first.

1. **Step 1.** Run the SQL, upload, check your own board (yours will be built from about 500 votes) and the
   unlock counter on a fresh browser.
2. **Step 2.** Check a trade with the switch off (identical to now) and on. Then `?dev=1`: Engine Audit 32/32.
3. **Step 3.** Sign in on your phone and your laptop and confirm both show the same board. Then check a new vote in
   the next export has `signed_in` filled in.

Before each upload, I'll run the view against stub data and check what it actually prints, not just that the file
loads.

## Open Questions For Steve

1. **Show the crowd's ranks before 5,000 votes?** "Where You Disagree With The Crowd" shows the crowd's position
   ranks, which aren't on the site yet. The risk is anchoring: people seeing the crowd's order and voting along with
   it. Some of that already happens with the "% agreed" line after each vote. Options:
   - **(a)** Show them, labelled "Early Crowd Rankings (3,755 votes)." This is my lean, because the payoff is the point.
   - **(b)** Show only your own board until 5,000, then add the crowd comparison.
2. **Unlock at 25 votes?** That's about a minute of voting. Fewer votes makes boards that barely differ from the crowd's.
3. **Share picture now or later?** It's the part that spreads the vote, but it's the largest piece of step 1. It
   could slip to a step 1b.

## Decided (28 Nov, Steve)

1. **Early Crowd Rankings are shown** before 5,000 votes, labelled that way.
2. **Unlock at 25 votes**, with the sign-in prompt at the same moment.
3. **Only players you've voted on are shown**, so filling in your board is a reason to keep voting.
4. **Home:** a Your Rankings tab in My Team, opened from the vote card and vote page.
5. **Share picture at 50 votes** (step 1b), with a second, smaller sign-in prompt for anyone still signed out.
6. **Pairing doesn't change.** The vote still picks pairs for the crowd's board, not to fill in your own. Steering pairs
   per person would change the pre-registered pairing, so it isn't part of this plan.

## Shipped (28 Nov)

- **Step 1** (e572c41, 33dbdf9): Your Rankings tab, colours on Where You Disagree.
- **25-vote pop-up** (3cc874d), with **Sign In To Keep Them** once step 3 made it true.
- **Step 3** (57b9ca1): `vote_devices`, `signed_in`, linked devices.
- **Step 1b**: the share picture is Steve's pick "A2" from the mock canvas (My N Hottest Takes, three numbers, up to 5 takes
  each way with a gap bar, the vote link). The 50-vote pop-up comes at least 25 votes after the 25-vote one. Your
  Rankings' headings and text sizes now follow BRAND.md (no small capitals; 12/13/16/20/28).
