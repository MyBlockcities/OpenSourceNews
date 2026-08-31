# YouTube Source Audit & Proposed Additions

**Date:** 2026-08-31
**Method:** Every handle resolved live against YouTube; every claim about "currently ingesting" cross-checked against the actual `author` field in the last 14 daily reports (`outputs/daily/2026-08-*.json`).
**Companion doc:** [`PIPELINE_AUDIT_2026-08-31.md`](PIPELINE_AUDIT_2026-08-31.md)

> **Read §2 first.** Before adding anything, there is a channel-mislabeling bug that means several of the channels you think you're collecting are not the ones being collected.

---

## 1. Your list — verified status

35 YouTube channels are currently ingesting, all at the 5-items/day cap. Here is where your list actually stands:

### AI

| Channel | Status | Detail |
|---|---|---|
| [@indydevdan](https://www.youtube.com/@indydevdan) | ✅ **Ingesting** | …**twice**. Both `yt_indydevdan` and `yt_arseny_shatokhin` point at IndyDevDan |
| [@intheworldofai](https://www.youtube.com/@intheworldofai) | ✅ Ingesting | Collected under the misnamed id `yt_matt_wolfe` |
| [@allin](https://www.youtube.com/@allin) | ✅ Ingesting | `yt_all_in_podcast` |
| [@mreflow](https://www.youtube.com/@mreflow) (Matt Wolfe) | ✅ **Ingesting** | …**twice**. Both `yt_wes_roth` and `yt_bitboy_legacy` resolve to Matt Wolfe |
| [@vrsen](https://www.youtube.com/@vrsen) | ✅ Ingesting | Collected under the misnamed id `yt_matthew_berman`. VRSEN's channel title is his real name, Arseny Shatokhin |
| [@WesRoth](https://www.youtube.com/@WesRoth) | 🔴 **NOT ingesting** | The `yt_wes_roth` slot points at `@mreflow` — Matt Wolfe. **You have never collected Wes Roth.** Real ID: `UCqcbQf6yw5KzRoDDcZ_wBSw` |
| [@AILABS-393](https://www.youtube.com/@AILABS-393) | 🔴 Not present | Active today. `UCelfWQr9sXVMTvBzviPGlFw` |
| [@echohive](https://www.youtube.com/@echohive) | 🔴 Not present | ⚠️ Last upload **46 days ago** — semi-dormant. `UCL7przoMtZTmiQMhc9ifIww` |
| [@rileybrownai](https://www.youtube.com/@rileybrownai) | 🔴 Not present | Active (4d). `UCMcoud_ZW7cfxeIugBflSBw` |

**Also already ingesting in this bucket (not on your list):** Matthew Berman, AI Explained*, Two Minute Papers, Nate Herk, Fireship, ThePrimeagen, Theo (t3.gg).

### Strategy

| Channel | Status | Detail |
|---|---|---|
| [@AlexHormozi](https://www.youtube.com/@AlexHormozi) | 🔴 Not present | Active today. `UCrvchO1h6lWZAuGaa1LqX9Q` |
| [@peterdiamandis](https://www.youtube.com/@peterdiamandis) | 🔴 Not present | Active today. `UCCpNQKYvrnWQNjZprabMJlw` |

**Adjacent already ingesting:** The Diary Of A CEO, Lex Fridman, All-In, Bloomberg TV*, Visual Capitalist.

### Truth / independent journalism

**None of the six are currently ingesting.** All resolved and all active:

| Channel | Channel ID | Last upload |
|---|---|---|
| [@ShawnRyanShow](https://www.youtube.com/@ShawnRyanShow) | `UC1vUksRWfEfd6V4pPDIQ0jw` | 1d |
| [@Iancarrollshow](https://www.youtube.com/@Iancarrollshow) | `UCCgpGpylCfrJIV-RwA_L7tg` | 1d |
| [@LondonRealTV](https://www.youtube.com/@LondonRealTV) | `UCCZVmatSqIMTTB8uExk8xEg` | 0d |
| [@Robert_Edward_Grant](https://www.youtube.com/@Robert_Edward_Grant) | `UC2MN4AlpbY9NYxuYH-ecoCQ` | 1d |
| [@OnlyTheSAVVY](https://www.youtube.com/@OnlyTheSAVVY) | `UCtKPFtUPf6ol9Lw4XvX4iQQ` | 1d |
| [@newupdates4real](https://www.youtube.com/@newupdates4real) | `UCWL91oqW3z6-A045ZjJMYHA` | 9d — ⚠️ mostly Shorts, low signal density |

**Already ingesting in this bucket:** Coffeezilla, Breaking Points, Nick Shirley, Johnny Harris (×2, duplicated), The Independent, TLDR Podcasts.

⚠️ **Policy conflict — see §4.** Note also that `investigative_documents.yaml` already contains **disabled** Ian Carroll entries (`ian_carroll_site`, `x_ian_carroll`, `twitch_ian_carroll`), so he was staged and never switched on.

### Crypto / blockchain

| Channel | Status | Detail |
|---|---|---|
| [@CoinBureau](https://www.youtube.com/@CoinBureau) | ✅ **Ingesting** | …**twice**. `yt_coinbureau` + `yt_bankless_id` both resolve to Coin Bureau |
| [@AltcoinDaily](https://www.youtube.com/@AltcoinDaily) | 🔴 Not present | Active today. `UCbLhGKVY-bJPcawebgtNfbw` |
| [@solana](https://www.youtube.com/@solana) | 🔴 Not present | Active today. `UC9AdQPUe4BdVJ8M9X7wxHUA` |

**Already ingesting:** Bankless (×2, duplicated), Ivan on Tech, BitBoy X.

---

## 2. 🔴 Critical: the channel labels are shifted

`config/sources/current_collection.yaml` has **15 YouTube entries whose configured name does not match the channel actually being fetched.** The pattern looks like a list of names and a list of channel IDs that got misaligned by one row when the config was generated.

Proof — the `yt_wes_roth` record is internally contradictory:

```yaml
id: yt_wes_roth
name: Wes Roth
publisher: Wes Roth
homepage: https://www.youtube.com/@mreflow   # ← Matt Wolfe's handle
endpoints:
  - '@mreflow'                                # ← Matt Wolfe's handle
```

Confirmed mismatches:

| source_id | Config says | **Actually fetches** |
|---|---|---|
| `yt_wes_roth` | Wes Roth | **Matt Wolfe** |
| `yt_bitboy_legacy` | BitBoy X legacy id | **Matt Wolfe** (dupe) |
| `yt_matt_wolfe` | Matt Wolfe | **WorldofAI** |
| `yt_worldofai` | WorldofAI | **Matthew Berman** |
| `yt_matthew_berman` | Matthew Berman | **Arseny Shatokhin (VRSEN)** |
| `yt_arseny_shatokhin` | Arseny Shatokhin | **IndyDevDan** (dupe) |
| `yt_ai_channel_extra` | Additional AI channel | **Bankless** (dupe) |
| `yt_bankless_id` | Bankless channel id | **Coin Bureau** (dupe) |
| `yt_coinbureau_id` | Coin Bureau channel id | **BitBoy X** |
| `yt_ai_explained` | AI Explained | **"AI Ki Duniya"** — `@AIExplained` is a different channel; the real one is `@aiexplained-official` |
| `yt_bloomberg_tv` | Bloomberg Television | a Korean personal vlog — `@BloombergTelevision` is not Bloomberg's handle |

### Why this matters more than it looks

`publisher` is written from the config label, not from the fetched feed. That label rides along into `outputs/daily/`, into the atoms, into Qdrant `news_signals`, and into anything Hermes generates. **Right now, content attributed to "Wes Roth" is actually Matt Wolfe's video.** Any generated content that cites a creator is currently citing the wrong person — which is a credibility problem in published output, not just a tidiness problem.

The good news: `author` (from the feed) is correct throughout, so **the data is recoverable** — it can be re-derived rather than re-collected.

### Five duplicate pairs are burning collection budget

| Channel | Collected via | Waste |
|---|---|---|
| Matt Wolfe | `yt_wes_roth` + `yt_bitboy_legacy` | 5 items/day |
| Johnny Harris | `yt_johnny_harris_sm` + `yt_johnny_harris_alt` | 5 items/day |
| Bankless | `yt_ai_channel_extra` + `yt_bankless` | 5 items/day |
| IndyDevDan | `yt_indydevdan` + `yt_arseny_shatokhin` | 5 items/day |
| Coin Bureau | `yt_coinbureau` + `yt_bankless_id` | 5 items/day |

That's **~25 duplicate items/day (~5% of total daily volume)** and five wasted source slots. Because of the hard 5-item-per-source cap (see the pipeline audit §11), reclaiming these five slots costs nothing and immediately makes room for five real channels.

**Recommendation: fix the labels and drop the five duplicates before adding anything new.** That alone gets you Wes Roth plus four additions at zero net cost.

---

## 3. Five recommended AI additions

You already collect Matthew Berman, Matt Wolfe, WorldofAI, VRSEN, IndyDevDan, Nate Herk, AI Explained and Two Minute Papers — so those are off the table.

> **Note on the draft already in `news_sources_to_add.md`:** its top two picks don't hold up. It recommends **Matt Wolfe** as #1 — but Matt Wolfe *is* `@mreflow`, which is already on your own list and already ingesting twice. And **Matthew Berman** is already ingesting under the misnamed `yt_worldofai`. Its picks 3–5 (Cole Medin, David Ondrej, AI Jason) are reasonable; Cole Medin I agree with strongly enough to rank first below.

Your taste reads as: early on releases, real workflows over theory, agent-capability tracking, and tools tied to business leverage. All five below were verified live — each resolved to a real channel ID and each has uploaded within the last 6 days.

| # | Channel | Channel ID | Last upload | Why it fits |
|---|---|---|---|---|
| **1** | **Cole Medin** [@ColeMedin](https://www.youtube.com/@ColeMedin) | `UCMwVTLZIRRUyyVrkjDpn4pA` | 1d | The closest thing to "IndyDevDan but on architecture." Production agent builds, RAG, MCP, local models. Highest-value single addition for your Hermes work. Latest: *"The Hidden Flaw of EVERY Coding Agent"* |
| **2** | **AI Engineer** [@aiDotEngineer](https://www.youtube.com/@aiDotEngineer) | `UCLKPca3kwwd-B59HNr-_lvA` | 1d | Conference talks from people shipping agents at scale. Highest signal-to-noise on the list and unusually good knowledge-base material — dense, technical, citable, minimal hype. Nothing in your current mix covers this |
| **3** | **Sam Witteveen** [@samwitteveenai](https://www.youtube.com/@samwitteveenai) | `UC55ODQSvARtgSyc8ThfiepQ` | 0d | Code-first, and consistently early on new model/agent releases with a working notebook rather than a reaction video. Good corroborating source when a release breaks |
| **4** | **Greg Isenberg** [@GregIsenberg](https://www.youtube.com/@GregIsenberg) | `UCPjNBjflYl0-HQtUvOx0Ibw` | 4d | Bridges your AI and strategy buckets — AI business models and productized services. Natural companion to Hormozi/Diamandis. Latest: *"WebMCP: Let AI Agents pay you money"* |
| **5** | **bycloud** [@bycloudAI](https://www.youtube.com/@bycloudAI) | `UCgfe2ooZD3VJPB6aJAnuQng` | 6d | Research-to-practice explainers. Catches capability shifts weeks before the news channels. Complements AI Explained without duplicating it |

### Alternates

| Channel | Channel ID | Last upload | Note |
|---|---|---|---|
| David Ondrej [@DavidOndrej](https://www.youtube.com/@DavidOndrej) | `UCPGrgwfbkjTIgPoOh2q1BAg` | 4d | Solid, but overlaps Nate Herk on n8n/automation |
| AI Jason [@AIJasonZ](https://www.youtube.com/@AIJasonZ) | `UCrXSVX9a1mj8l0CMLwKgMVw` | 6d | Good agent-architecture long-form |
| ~~Yannic Kilcher~~ | ~~`UCHmD-oSpV0sNfAUnpYpj8KA`~~ | **1,114d** | ❌ **Dead — do not add.** Worth noting as an example of why upload recency belongs in the review checklist |

---

## 4. ⚠️ Policy conflict on the Truth / independent bucket

This is a public repo, and `HERMES_INTEGRATION.md` states the current collection policy explicitly:

> *"high-controversy personality channels are excluded from `config/feeds.yaml` (Alternative bucket kept for independent/investigative sources only)."*

Four of your six — London Real, Robert Edward Grant, Only The SAVVY, newsupdates4real — are exactly what that sentence carves out. Adding them to the public registry reverses a documented policy decision on a repo anyone can read. That's your call to make, not mine, but make it deliberately rather than by merging a config diff.

Three ways forward:

1. **Tier them T5 (`quarantined`)** — `config/source_policy.yaml` already defines this tier: `permitted_use: quarantined_discovery`, `automatic_content_eligible: false`, `automatic_evidence_promotion: false`, `corroboration_required: true`. They get collected for discovery but can never auto-promote into published content. **This is what T5 exists for, and it's my recommendation.**
2. **Collect them Hermes-side only** — keeps the public sensor's stated policy intact while you still get the signal privately.
3. **Amend the policy** in `HERMES_INTEGRATION.md` so doc and behavior agree. Whatever you choose, don't leave them disagreeing.

Shawn Ryan Show and Ian Carroll sit more comfortably in the existing "independent/investigative" carve-out and are defensible at **T4** — the same tier as Coffeezilla and Breaking Points, which you already collect. Note `newupdates4real` is mostly Shorts; expect low signal density regardless of tier.

---

## 5. Paste-ready config

Append to `config/sources/current_collection.yaml` under `sources:`. Channel IDs are more durable than handles — every mismatch in §2 came from a handle that moved or was mistyped, so **prefer IDs**.

### 5a. Fixes first (do these before adding)

```yaml
# 1. yt_wes_roth currently fetches Matt Wolfe. Point it at the real Wes Roth:
#    endpoints: ['UCqcbQf6yw5KzRoDDcZ_wBSw']   homepage: https://www.youtube.com/@WesRoth
#
# 2. Rename to match what they actually fetch:
#    yt_matt_wolfe        -> WorldofAI            (UC2WmuBuFq6gL08QYG-JjXKw)
#    yt_worldofai         -> Matthew Berman       (UCawZsQWqfGSbCI5yjkdVkTA)
#    yt_matthew_berman    -> VRSEN / Arseny Shatokhin (UCSv4qL8vmoSH7GaPjuqRiCQ)
#    yt_coinbureau_id     -> BitBoy X             (UCuV9EB4I9L-xmRoaXd8tmuA)
#
# 3. DELETE these five duplicates (frees 25 items/day):
#    yt_bitboy_legacy     (dupe Matt Wolfe)
#    yt_arseny_shatokhin  (dupe IndyDevDan)
#    yt_ai_channel_extra  (dupe Bankless)
#    yt_bankless_id       (dupe Coin Bureau)
#    yt_johnny_harris_alt (dupe Johnny Harris)
#
# 4. Fix two wrong handles:
#    yt_ai_explained  '@AIExplained'         -> '@aiexplained-official'
#    yt_bloomberg_tv  '@BloombergTelevision' -> '@markets'
```

### 5b. Recommended AI additions (T4, `discovery_only`)

```yaml
- schema: source_definition.v1
  id: yt_cole_medin
  name: Cole Medin
  publisher: Cole Medin
  homepage: https://www.youtube.com/@ColeMedin
  adapter: youtube
  endpoints: ['UCMwVTLZIRRUyyVrkjDpn4pA']
  topics: [ai, ai_agents]
  regions: [global]
  languages: [en]
  tier: T4
  source_kind: commentary
  permitted_use: discovery_only
  corroboration_required: true
  automatic_content_eligible: false
  automatic_evidence_promotion: false
  extract_outbound_evidence_links: true
  robots_policy: obey
  rate_limit: {requests_per_second: 0.2}
  retention: {raw_days: 90, normalized_days: 0}
  collection_mode: scheduled
  project_hints: []
  enabled: true
  owner: intelligence
  reviewed_at: '2026-08-31'
  feeds_topic: AI / AI Tools / AI Agents
  feeds_key: youtube_sources

- schema: source_definition.v1
  id: yt_ai_engineer
  name: AI Engineer
  publisher: AI Engineer
  homepage: https://www.youtube.com/@aiDotEngineer
  adapter: youtube
  endpoints: ['UCLKPca3kwwd-B59HNr-_lvA']
  topics: [ai, ai_agents]
  regions: [global]
  languages: [en]
  tier: T3
  source_kind: expert_interpretation
  permitted_use: discovery_and_interpretation
  corroboration_required: true
  automatic_content_eligible: false
  automatic_evidence_promotion: false
  extract_outbound_evidence_links: true
  robots_policy: obey
  rate_limit: {requests_per_second: 0.2}
  retention: {raw_days: 90, normalized_days: 0}
  collection_mode: scheduled
  project_hints: []
  enabled: true
  owner: intelligence
  reviewed_at: '2026-08-31'
  feeds_topic: AI / AI Tools / AI Agents
  feeds_key: youtube_sources
```

…and the same block shape for:

| id | name | endpoint |
|---|---|---|
| `yt_sam_witteveen` | Sam Witteveen | `UC55ODQSvARtgSyc8ThfiepQ` |
| `yt_greg_isenberg` | Greg Isenberg | `UCPjNBjflYl0-HQtUvOx0Ibw` |
| `yt_bycloud` | bycloud | `UCgfe2ooZD3VJPB6aJAnuQng` |
| `yt_ai_labs` | AI LABS | `UCelfWQr9sXVMTvBzviPGlFw` |
| `yt_riley_brown` | Riley Brown | `UCMcoud_ZW7cfxeIugBflSBw` |
| `yt_echohive` | echohive | `UCL7przoMtZTmiQMhc9ifIww` |
| `yt_alex_hormozi` | Alex Hormozi | `UCrvchO1h6lWZAuGaa1LqX9Q` |
| `yt_peter_diamandis` | Peter Diamandis | `UCCpNQKYvrnWQNjZprabMJlw` |
| `yt_altcoin_daily` | Altcoin Daily | `UCbLhGKVY-bJPcawebgtNfbw` |
| `yt_solana_official` | Solana | `UC9AdQPUe4BdVJ8M9X7wxHUA` |
| `yt_shawn_ryan_show` | Shawn Ryan Show | `UC1vUksRWfEfd6V4pPDIQ0jw` |
| `yt_ian_carroll` | Ian Carroll | `UCCgpGpylCfrJIV-RwA_L7tg` |

Tier guidance: **T3** for AI Engineer (conference talks with citable sources) and Solana (official channel — arguably T1 as `official_lab`); **T4** for the rest; **T5** for the four high-controversy channels if you add them (§4).

After editing, validate before pushing — this is what the daily workflow runs:

```bash
python scripts/validate_sources.py
python scripts/compile_feeds_compat.py --check
```

---

## 6. Suggested order of work

1. **Fix the 15 mislabeled entries + delete the 5 duplicates.** Free, reclaims 25 items/day, and stops mis-attributing content to the wrong creators.
2. **Backfill the `publisher` field** in historical `outputs/daily/*.json` from the correct `author` value, then re-run the Hermes ingest so Qdrant carries correct attribution. The data is recoverable — don't leave the wrong names in the vector store.
3. **Fix envelope health reporting first** (pipeline audit §4.2 / P0). Until `failed_sources` is computed rather than hardcoded to `0`, a newly added channel that silently fails is indistinguishable from one that works. **You will be adding sources blind until this is fixed.**
4. **Add the 5 AI recommendations** into the freed duplicate slots — net zero change in collection volume.
5. **Add strategy + crypto** (Hormozi, Diamandis, Altcoin Daily, Solana).
6. **Decide the §4 policy question**, then add the Truth bucket at the tier you chose.
7. **Re-check yield after 3 nights.** Any new source still at zero items is broken, not quiet.

### One structural decision worth making now

Every collector is hard-capped at **5 items per source per run** (`fetch_rss`, `fetch_youtube`, PubMed, ClinicalTrials, HN, GitHub all use `limit=5` or `[:5]`). Adding ~19 channels takes you from 123 to ~142 sources and from ~510 to roughly ~600 items/night.

But it also means a channel posting 3 videos/day and a channel posting 1/week contribute identically. If you'd rather have depth on your best sources than breadth across many, raise the cap for T0–T2 sources specifically instead of only adding channels. Right now the architecture offers you breadth only — worth choosing deliberately rather than by default.
