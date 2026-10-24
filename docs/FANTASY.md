# Lämäri: how the fantasy game works

Lämäri is a season-long Liiga fantasy game inside the reader app. Readers turn on **Fantasy mode** in Profile and open **Lämäri fantasy** from the profile list. It is free to play. Brands put up prizes.

Language: Finnish for readers whose profile language is Finnish, English for everyone else.

Code: `backend/apps/fantasy/` (rules in `rules.py`) and `frontend/src/pages/Fantasy.jsx` with `frontend/src/components/fantasy/`.

---

## 1. Your team

| Rule | Value |
|---|---|
| Squad | 15 players: 2 goalies, 5 defenders, 8 forwards |
| Budget | 100.0 |
| Players from one Liiga team | at most 3 |
| Lineup each gameweek | 11 starters (1 goalie, 4 defenders, 6 forwards) and 4 on the bench |
| Captain | scores double. If the captain doesn't play, the vice-captain scores double instead. |

**Player prices** run from 4.0 to 13.0. Each player is priced by his rank in points per game within his position. A price is set when he is first priced and doesn't change after someone owns him.

**Gameweeks** follow Liiga's own gameweek numbers. A gameweek locks at the first face-off of its first game. Changes made after that count from the next gameweek.

**Auto-substitution:** when a starter's team has finished all its games for the week and he didn't play, the first bench player in the same position who did play takes his place.

## 2. Points: how a game becomes points

After every game, each player's box score from the Liiga API is turned into points (`rules.game_points`).

| Everyone | Points |
|---|---|
| Played | +1 |
| Goal | forward +4, defender +6, goalie +8 |
| Assist | +3 |
| Game-winning goal | +1 |
| Penalty minutes | -1 per 2 minutes, at most -4 |

| Skaters (forwards and defenders) | Points |
|---|---|
| 15+ minutes of ice time | +1 |
| Plus/minus | +1 per plus, -1 per minus |
| Shots | +1 per 3 shots |
| Blocked shots | +1 per 3 blocks |
| Defender, team conceded no goals | +3 |

| Goalies | Points |
|---|---|
| Saves | +1 per 5 saves |
| Goals against | -1 per 2 goals |
| Win (the goalie who played most of the game) | +3 |
| Shutout (all three periods) | +5 |

**Your gameweek score** is your starters' points after auto-subs, with the captain doubled, minus the points you spent on changes that week. Scoring runs every 10 minutes while games are on (`tasks.sync_live`). A gameweek becomes **final** when its last game is finished. Final gameweeks award vouchers (see 5).

## 3. Changing your team

Tap **Change team** under your lineup.

- **Swap a player:** tap one of your players, pick a Liiga team (or all teams), pick a player. You see his price, his points and what the change costs. Then confirm.
- **Shake up:** choose how many points you are willing to spend. Lämäri replaces up to 3 of your weakest-form starters with better-form players in the same position. It picks at random from the strongest options and stays within your money and that points limit.

**Cost of a change** (`rules.transfer_cost`): every incoming player costs points in that gameweek, by his season rank within his position. The lowest-ranked costs 1 point and the top-ranked costs 8. The cost is shown on every option.

**Free changes:** before your first deadline, building and changing your team costs nothing.

**Money:** you sell a player for what you paid and buy at his current price. The difference goes to or from your bank.

## 4. Leaderboards, tiers and leagues

- Leaderboards: **season**, **gameweek** and **today**. Each can be shown for Finland, Oulu (members of the Oulu community) or one of your private leagues. Ties share a place.
- **Tiers** come from your season rank among all managers:

| Tier | Who |
|---|---|
| 💎 Diamond | the leader, plus the top 1% |
| Gold | top 10% |
| Silver | top 35% |
| Bronze | everyone else |

- **Private leagues:** create one and share its 6-character code, or invite friends by @username.

## 5. Prizes and vouchers

Each brand decides its own prize (`Reward`). There are four kinds:

| Kind | You win when | Example |
|---|---|---|
| `rank` | you finish in the top 3 (or 1st) of a leaderboard | Prisma: win the gameweek in Finland |
| `player` | the brand's chosen player counts for your team and reaches a points target | Hesburger: Roni Hirvonen scores 5+ in the gameweek |
| `points` | your gameweek total reaches a target | DNA: 115 points in a gameweek |
| `tier` | you finish the season in a tier or better | Marimekko: Gold or Diamond |

- **Weekly prizes** are issued automatically as **vouchers with a code** when a gameweek is final (`services/rewards.award_gameweek`).
- **Season prizes** are awarded after the final.
- Vouchers appear under **Prizes > Your vouchers**.

Brands get placements:
- the prize banner on the Team tab
- logos next to the leaderboard places that win a prize
- one card marked "Sponsored" in the match list.

`manage.py seed_sponsors` sets up the demo partners. Bootstrap runs it.

## 6. Coach, analysis and chat

All facts come from Liiga data: results, standings computed the Liiga way (3 / 2 / 1 points), form, head-to-head and fantasy points.

- An AI model may only reword text. Its version is dropped if it contains any number that isn't in the data.
- AI-worded text is labelled.
- Readers never wait for a model. They get the data version at once, and an AI-worded one is stored in the background for the next visit.

- **Coach tab:** your last gameweek reviewed, and picks for the next one: captain, start or bench, one transfer, each with the reason in numbers.
- **Matches tab:** one gameweek per page. Tap a game for the context beyond the score, or a preview. Choose **Fan** or **New to hockey** (which explains the rules that game depends on), and **Short** or **Full**.
- **Coach chat:**
  - Answers only questions about winning with Liiga data.
  - Anything else gets "Sorry, I can only help with sports data". Asking again straight away gets a firm stop.
  - Limits: 8 messages a minute and 120 a day per reader.

## 7. Sports desk agent

A Celery job every 30 minutes (`services/sports_desk.py`):

1. Reads Kaleva's hockey and sports RSS feeds **once** (2 requests).
2. Gives each followed player (one in someone's team) his own task, **only when there is something new**:
   - he has never been checked
   - his team finished a game since his last check
   - a day has passed (to catch a suspension).

   Between gameweeks this is usually nobody.
3. Each player task:
   - reads the player's Liiga game log and writes a form note
   - checks his suspension status
   - links Kaleva stories that mention him.

   Those stories are also handed to the newsroom, so readers open our own version once an editor publishes it.

**Rate limits:**
- player tasks: 20 a minute, with 1.5 s between Liiga requests
- model calls: `SPORTS_AI_PER_MINUTE` (default 4) across all workers
- an unreachable model is detected in 2 seconds and skipped for 5 minutes.

## 8. Data and refreshes

| What | When |
|---|---|
| Schedule and rosters | daily at 06:00 (`tasks.sync_schedule`) |
| Box scores and scoring | every 10 minutes for games started in the last 6 hours (`tasks.sync_live`) |
| Player photos | made once as 96 px WebP when players are synced |
| In the app | sports data is kept on the device with a time limit (players 6 h, season 30 min, team 2 min), so a refresh doesn't fetch everything again |

Commands:

```bash
python manage.py sync_liiga          # import or refresh the season from the Liiga API
python manage.py seed_fantasy_demo   # demo managers and leagues
python manage.py seed_sponsors       # demo brand partners and prizes
```

To use a separate model for Lämäri wording, set `LLM_MODEL_SPORTS` in `.env` (for example `gemini:gemini-3.1-flash-lite`).
