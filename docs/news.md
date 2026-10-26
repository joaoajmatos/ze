# Ze — News Package (`ze-news`)

The `ze-news` plugin adds RSS ingestion, personalised article ranking, and credibility
analysis to Ze. It runs as a `ZePlugin`, keeping all news-specific concerns isolated
from `ze-core` and `ze-personal`.

---

## Architecture overview

![Data flow diagram showing configured sources feeding the source registry into a fetch job that runs on a schedule or an on-demand trigger, writing articles into the news store, which asynchronously kicks off credibility scoring and fans out to three consumers: headline retrieval, semantic search, and the morning briefing.](diagrams/docs/news-pipeline.svg)

<sub>[Interactive version](diagrams/docs/news-pipeline.html)</sub>

---

## Package layout

```
plugins/ze-news/
  ze_news/
    types.py          ← Article, CredibilityFlag, CredibilityReport, NewsPreference, PersonalizationSettings, PersonalizationContext
    store.py          ← NewsStore: upsert, get_recent, get_personalized, search, by_tag, get_by_ref, update_credibility, dedup_new_articles, prune
    registry.py       ← SourceRegistry, build_registry()
    credibility.py    ← run_heuristics(), run_nli_headline_check(), run_llm_scoring(), score_article()
    plugin.py         ← NewsPlugin(ZePlugin): agents, jobs, migrations, configurable_services, UI contributions
    preferences.py    ← NewsPreferenceBuilder: builds PersonalizationContext from memory facts, profile facets, active goals, and the current request
    signals.py        ← ArticleSignalAdapter + NewsSignalSource for the correlation engine
    onboarding.py     ← news onboarding provider
    refs.py           ← article_ref_id(url), the ref id for the news_article screen kind
    screen_resolvers.py ← the news_article screen resolver
    api/              ← GET /api/v0/news/settings and its schema
    ui/settings.py    ← builds the settings section tree
    locales/          ← progress-message strings (en, pt)
    sources/
      base.py         ← NewsSource ABC
      rss.py          ← RSSSource (feedparser + httpx)
    agents/
      agent.py        ← NewsAgent(@agent)
      tools.py        ← refresh_news, get_headlines, search_news tools
    jobs/
      fetch.py        ← NewsFetchJob (job_id "news_fetch"; run(force=True) for on-demand use)
    migrations/
      versions/
        zn001_news_articles.py        ← creates news_articles table
        zn002_credibility_analysis.py ← adds credibility_analysis JSONB column
```

---

## Data model

### `Article`

```python
@dataclass
class Article:
    url: str
    source_key: str          # matches the key in config.yaml sources list
    title: str
    summary: str
    published_at: datetime
    tags: list[str]          # copied from source config at fetch time
    credibility: CredibilityReport | None  # None = not yet scored
```

### `news_articles` table

| Column | Type | Notes |
|---|---|---|
| `url` | `TEXT PK` | Deduplication key |
| `source_key` | `TEXT` | Source identifier |
| `title` | `TEXT` | Article headline |
| `summary` | `TEXT` | RSS summary / lede |
| `published_at` | `TIMESTAMPTZ` | Publication timestamp from RSS |
| `tags` | `TEXT[]` | Tags from source config |
| `embedding` | `VECTOR(768)` | Shared local embedder on `title + summary` (`zn001` creates it; `zm013` resizes older 384-dim tables) |
| `credibility_analysis` | `JSONB` | `CredibilityReport` serialised; `NULL` until scored |
| `fetched_at` | `TIMESTAMPTZ` | When Ze first ingested the article |

---

## Fetch job

`NewsFetchJob` runs on a cron (default: every 30 minutes). For each source it:

1. Calls `source.fetch(limit=50)` — fetches and parses the RSS feed.
2. Embeds each article (`title + summary`) using the shared
   `intfloat/multilingual-e5-base` singleton.
3. Upserts into `news_articles` (`ON CONFLICT (url) DO UPDATE SET fetched_at = now()`).
   Only rows that did not exist before count as new.
4. If `news.nli_dedup_enabled: true`, drops new articles that repeat an existing story.
5. If `news.credibility.enabled: true` and new articles exist, fires an
   `asyncio.create_task` to score them — scoring never blocks the fetch loop.
6. Sends new articles to memory as signals, and asks the Sources modules to refresh.
7. After all sources, deletes articles whose `fetched_at` is older than
   `news.retention_days`.

A source fetched less than `news.min_fetch_interval_minutes` ago (default 30) is
skipped, unless the run is forced (`refresh_news` forces it).

---

## Personalisation

### How it works

When the news agent or morning briefing requests personalised headlines,
`NewsPreferenceBuilder.build()` builds a `PersonalizationContext` from four sources.
Each source adds weighted `NewsPreference` entries:

| Source | Weight | What it reads |
|---|---|---|
| Stored facts | 0.9 include, 1.0 exclude | Facts with a predicate that starts with `news_interest`, `interest_news`, or `topic_interest`, and facts that state a dislike ("not interested", "don't show", "avoid", …). Contradicted facts and facts below `min_confidence` are skipped |
| Profile facets | 0.6 include, 0.9 exclude | `topics`, `preferences`, `news_preferences`, `news_interests` (include) and `news_exclusions` (exclude). The onboarding step writes these |
| Active goals | 0.5 | One include entry per active goal title |
| The current request | 1.0 | The user's query text, unless it is a diagnostic question such as "why do you keep showing me this?" |

```python
@dataclass
class PersonalizationContext:
    interest_text: str       # " | "-joined "source:topic" for every include entry
    exclusions: list[str]    # excluded topics, de-duplicated
    explore_ratio: float     # fraction of results reserved for discovery (default: 0.2)
    fact_count: int          # number of include entries (checked against min_preferences)
    query_text: str
    preferences: list[NewsPreference]
    max_per_topic: int
    candidate_multiplier: int
```

`NewsStore.get_personalized()` then:

1. If there are fewer include entries than `min_preferences` and none comes from the
   current request, falls back to recency order with exclusions applied and returns
   `(articles, [])`. The caller treats this as "not enough signal yet."
2. Otherwise, fetches `limit × candidate_multiplier` recent articles as candidates.
3. Applies word-boundary exclusions (regex `\bterm\b`) — articles whose title or
   summary match any exclusion term are dropped.
4. Scores each candidate: `1.5 × request similarity + stored-preference similarity +
   0.1 × freshness`. Similarity is the weighted cosine between the article embedding
   and the embedding of each preference topic; the best match wins.
5. Keeps at most `max_per_topic` articles for each topic (the first tag, or the first
   word of the title).
6. Splits into two buckets:
   - **Relevant** — top `ceil((1 − explore_ratio) × limit)` articles by score.
   - **Discovery** — the next candidates, re-sorted by recency (`published_at DESC`),
     up to `limit − len(relevant)`.

If no structured preferences exist, the older path runs: it embeds `interest_text` and
ranks candidates by cosine similarity against it.

### Preference signals

No new UI is needed. When the user says *"Ze, I don't care about football"*, the memory
extractor stores a fact that states the dislike. On the next context build, "football"
appears in `exclusions`, and word-boundary regex filters it from both buckets — so
"sport" won't falsely exclude "transport" articles.

### Briefing rendering

```
📰 For you (based on your interests):
  • Article title (source_key)  🔍 question headline
  • Another article (source_key)

  (1 of 5 articles flagged for potentially misleading patterns)

🔭 Outside your usual:
  • Off-profile article (source_key)
```

- The "For you" header appears when `fact_count ≥ min_preferences`. Below the threshold it
  falls back to `📰 Headlines:`.
- Discovery articles never show inline credibility labels (to avoid double-negative
  framing). Their flags are available via the news agent.
- The summary line appears only when flagged articles are fewer than 50% of the
  relevant bucket — at higher density the count conveys no useful signal.

---

## Credibility analysis

Ze flags articles for manipulative or misleading journalistic patterns. Flagged
articles are never filtered out — the system informs, it does not censor.

### Two-pass architecture

**Pass 1 — Heuristic pre-pass** (inline, zero cost)

Runs first inside `score_article()`, which the fetch job starts in the background for
each batch of new articles (only when `news.credibility.enabled` is true). Pure phrase
and regex matching against the title and summary. Produces `CredibilityFlag` objects
with `source="heuristic"`. Only six types have heuristics: `betteridge`, `clickbait`,
`vague_attribution`, `weasel_words`, `emotional_manipulation`, and `sensationalism`.
The LLM pass alone covers `passive_agency`, `false_balance`, `missing_context`, and
`headline_mismatch`.

**Pass 1b — NLI headline check** (optional, local cross-encoder)

When `news.nli_credibility_enabled: true`, runs before the LLM pass. Premise =
summary, hypothesis = headline. Flags `headline_mismatch` when
`contradiction ≥ nli_headline_contradiction_threshold` (default 0.50) or
`entailment < nli_headline_entailment_threshold` (default 0.30). Produces flags
with `source="nli"`.

**Pass 2 — LLM scoring pass** (async, one API call per article)

Fires as a background task via `asyncio.create_task` after upsert. A cheap model
(GPT-4o-mini by default) receives the headline and summary and returns a structured
JSON report with verdicts for all 10 pattern types. The LLM:

- Requires a verbatim quote from the provided text in `detail` for every `"present"`
  verdict — making every flag self-auditable.
- Defaults to `"uncertain"` when evidence is ambiguous — the system prefers false
  negatives over false positives.
- Reviews heuristic flags and can `"clear"` them if it assesses them as false
  positives on the full article context.

If scoring has not finished by the 8 AM briefing, those articles render without
flags (graceful degradation) and show no placeholder.

### Flag taxonomy

Flags belong to one of two confidence tiers, which control where they appear.

**High-confidence** (clear linguistic signatures, low false-positive risk):

| Flag | Label shown | Detection |
|---|---|---|
| `betteridge` | Question headline | Headline ends in `?` (language-agnostic) |
| `clickbait` | Engagement hook language | EN + PT phrase lists, then LLM |
| `vague_attribution` | Sources unnamed | EN + PT phrase lists, then LLM |
| `headline_mismatch` | Headline stronger than summary | NLI (optional) + LLM |

**Low-confidence** (require contextual judgment, higher false-positive risk):

| Flag | Label shown | Why low-confidence |
|---|---|---|
| `weasel_words` | Hedged claim language | "Could" is sometimes appropriate epistemic caution |
| `emotional_manipulation` | Heightened emotional language | "Devastating earthquake" is accurate, not manipulation |
| `passive_agency` | Actor not named | Passive voice is grammatically valid; actor may be named elsewhere |
| `false_balance` | Unequal positions presented equally | Requires knowing expert consensus state; unreliable for niche topics |
| `missing_context` | Context may be incomplete | Requires external knowledge of what context is relevant |
| `sensationalism` | Disproportionate framing | "Unprecedented flooding" may be accurate |

### Rendering rules

| Tier | Briefing inline | Briefing count | `get_headlines` | Agent response |
|---|---|---|---|---|
| High-confidence | ✅ when `is_briefing_worthy` | ✅ | ✅ with `confidence` field | Direct: "Ze noted: sources unnamed" |
| Low-confidence | ❌ | ❌ | ✅ with `confidence: "low"` | Caveated: "Ze noticed this may be worth noting…" |

`is_briefing_worthy` is true when an article has ≥ 2 high-confidence flags **or** a
single flag of type `betteridge`, `clickbait`, or `headline_mismatch`. A lone
`vague_attribution` flag does not show inline — it requires corroborating signal.

Ze uses the 🔍 icon throughout (not ⚠️). It signals observation, not condemnation.
Labels are descriptive, not evaluative: "Sources unnamed" rather than "Phantom sources."

### Prompt versioning

Ze stores the LLM scoring prompt's SHA-256 (first 12 characters) on every
`CredibilityReport` as `prompt_version`. When the prompt changes, only articles whose
stored version differs from the current one need re-scoring. Treat prompt changes as
schema changes: they alter the semantics of stored flag types. You can re-score
articles by running the scoring pipeline directly against the database — no REST
endpoint exists for this yet.

### Semantic dedup (optional)

URL is the primary dedup key. When `news.nli_dedup_enabled: true`, Ze compares newly
inserted articles against recent neighbours (cosine on title+summary embeddings, then
mutual NLI entailment on summaries) and deletes duplicates of an existing story from
`news_articles`, so the briefing does not surface the same event twice under
different URLs.

---

## Configuration

```yaml
news:
  enabled: true
  fetch_schedule: "*/30 * * * *"   # cron for fetch job
  min_fetch_interval_minutes: 30    # skip a source fetched more recently than this
  retention_days: 7                 # hard-delete articles fetched more than N days ago
  model: "openai/gpt-4o-mini"      # news agent model
  briefing_limit: 8                 # fallback if personalization.briefing_limit not set

  personalization:
    enabled: true
    explore_ratio: 0.2             # fraction of briefing reserved for discovery
    candidate_multiplier: 4        # over-fetch multiplier before scoring
    briefing_limit: 8              # total articles in morning briefing (≥ 8 recommended)
    min_preferences: 2             # min include preferences before scoring; below → recency fallback
                                   # (min_facts is read when min_preferences is absent)
    max_per_topic: 2               # cap per topic in the ranked list
    fact_days: 365                 # how far back to read stored facts
    fact_limit: 100                # max facts read
    min_confidence: 0.65           # facts and facets below this are ignored

  credibility:
    enabled: true
    llm_scoring: true              # false → heuristic-only (zero LLM cost)
    model: "openai/gpt-4o-mini"   # model for LLM scoring pass
    flag_in_briefing: true         # show 🔍 labels inline in morning briefing
    briefing_summary: true         # show "N of M articles flagged" summary line

  nli_credibility_enabled: false   # local NLI headline–summary mismatch pass
  nli_headline_contradiction_threshold: 0.50
  nli_headline_entailment_threshold: 0.30
  nli_dedup_enabled: false         # delete semantically duplicate new articles
  nli_dedup_cosine_threshold: 0.75
  nli_dedup_entailment_threshold: 0.70

  sources:
    - key: bbc_world
      type: rss
      url: "https://feeds.bbci.co.uk/news/world/rss.xml"
      tags: [global, general]
```

**`explore_ratio`** — `0.0` = fully interest-ranked (filter bubble). `1.0` = all
discovery. Default `0.2` means one in five briefing headlines is deliberately off-profile.

**`briefing_limit`** must be ≥ 8 for the 80/20 split to produce at least 2 discovery
articles. At `limit=5`, `ceil(0.2 × 5) = 1` — a single discovery article is not
meaningful serendipity.

**`credibility.llm_scoring: false`** gives a useful intermediate state: heuristics
are free and catch Betteridge violations, clickbait phrases, and common weasel words.
Useful if OpenRouter costs become a concern (`~$1/day` at current source volume).

**Source tags** are arbitrary strings. Useful conventions: `global`, `local`, `tech`,
`pt`, `leiria`, `hacker-news`. Both `get_headlines` and the briefing accept a `tags`
filter.

---

## Adding a source

Add an entry under `news.sources` in `config/config.yaml`:

```yaml
- key: my_source         # unique identifier used as source_key on articles
  type: rss
  url: "https://example.com/feed.xml"
  tags: [global, tech]   # arbitrary; used for filtering
```

Sources are registered at startup. A full restart is required when adding or removing
sources (`enabled` flag changes also require restart; hot-reload via SIGHUP does not
apply to the news plugin).

---

## Tools

The news agent exposes three tools:

**`refresh_news`** — triggers an immediate RSS fetch across all configured sources,
bypassing the normal 30-minute minimum fetch interval. The agent calls this
automatically when the user asks for today's news or says headlines are stale.
Returns `{"status": "ok", "message": "..."}` when all sources have been fetched;
the agent then calls `get_headlines` to present the fresh articles.

**`get_headlines`** — returns ranked headlines. The LLM schema accepts `limit`,
`tags`, and `personalized`. When `personalized=true` (default), the tool injects
the current session's `PersonalizationContext` automatically and returns:

```json
{
  "relevant": [
    {
      "title": "Is this the worst PM ever?",
      "url": "https://...",
      "source": "bbc_world",
      "published_at": "2026-06-07T08:00:00+00:00",
      "tags": ["global", "general"],
      "credibility": {
        "flags": [
          {
            "type": "betteridge",
            "label": "Question headline",
            "detail": "Headline ends with '?' — implies a claim the author won't assert as fact.",
            "confidence": "high"
          }
        ],
        "status": "complete"
      }
    }
  ],
  "discovery": [...]
}
```

`credibility` is `null` when the article has not yet been scored.

**`search_news`** — semantic search via pgvector cosine similarity. Accepts `query`,
`limit`, and optional `tags` filter.

---

## Multilingual support

The embedding model (`intfloat/multilingual-e5-base`) handles all source
languages without changes. Portuguese sources (DN, Observador, Jornal de Leiria) are
embedded and ranked correctly alongside English sources.

Heuristic credibility detection has partial Portuguese coverage:

| Pattern | EN | PT |
|---|---|---|
| `betteridge` | ✅ (language-agnostic — `?` suffix) | ✅ |
| `clickbait` | ✅ | ✅ (common PT formulas) |
| `vague_attribution` | ✅ | ✅ |
| `weasel_words` | ✅ | ✅ |
| `headline_mismatch` | ✅ (LLM) | ✅ (LLM handles PT) |
| Other low-confidence | ✅ (EN only) | ❌ (LLM handles PT) |

Full heuristic parity across all languages is a v2 concern. Heuristic flags carry a
`lang` field (`"en"`, `"pt"`, `"any"`) so coverage gaps are auditable.

---

## Inspecting news data

Use the news agent in conversation to query current news:
- *"What's in the news today?"* — agent calls `refresh_news` then `get_headlines`
- *"Any tech news?"* — `get_headlines(tags=["tech"])`
- *"Search for articles about the budget"* — `search_news(query="budget")`
- *"Were any of today's headlines flagged?"* — agent surfaces credibility flags with context

The agent calls `refresh_news` automatically when the user asks for today's or recent
news so the local store is always up-to-date before presenting headlines. The scheduled
`NewsFetchJob` (every 30 minutes) continues to run in the background for the morning
briefing and proactive delivery; `refresh_news` bypasses the interval guard for
on-demand requests.
