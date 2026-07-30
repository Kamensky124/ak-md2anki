# md2anki — Markdown Knowledge → Anki Compiler (Plan)

> Status: **design / pre-build**. Founded 2026-07-30.
> Owner: andy. Project home: `~/pets/md2anki/`.
> Companion decision: see "Background" — this replaces the abandoned
> "build Anki inside the md-agent Telegram bot" path.

---

## 1. Background & decision context

Two prior repos exist:

- `~/pets/ak-anki` — a clone of the **official Anki source** (ankitects/anki):
  `pylib/anki/` (apkg import/export, v3 scheduler, notes/cards), Rust backend.
  Useful as a reference and for programmatic deck creation, **not** needed to
  *run* Anki.
- `~/pets/md-agent` — a Telegram bot (TS, OpenRouter) that already has an SM-2
  spaced-repetition vocab module (`src/vocab/srs.ts`, `repo.ts`). This is the
  **abandoned path** for the training use case.

**Decision (locked):** use **official Anki desktop** (tar.gz install on Fedora 43
Sway) for *review* — it has FSRS (better than our SM-2), native media, browser,
stats, addons. Do **not** keep building the Telegram Anki clone: the bot's only
advantages (mobile, push, multi-device) are moot for a single desktop user, and
reimplementing apkg media + FSRS is months of work to reach 80% of a free app.

**What's worth building:** a small compiler that turns the existing business
markdown knowledge base into Anki decks, with AI enrichment via free OpenRouter
models. Anki owns review+sync; this tool owns **content generation &
structuring** from `.md`.

---

## 2. Goals / Non-goals

### Goals
1. `build <file|dir>` → structured cards from existing markdown (tables, Q&A blocks).
2. AI enrichment with **free** OpenRouter models (extra example sentences, answer variants).
3. Two decks: **Business Vocab** + **Client Call Q&A** (plain Q&A, no cloze in v1).
4. Stable note identity → re-runs **update** notes, never duplicate.
5. Incremental builds (hash-based) — cheap re-runs on a large KB.
6. Sink-agnostic: AnkiConnect (primary, smooth `sync`) **and** `.apkg` (portable/headless).

### Non-goals (v1)
- Mobile / Telegram delivery.
- Reimplementing FSRS or any scheduler.
- Media (sound/image) handling — those decks import into Anki directly.
- Bidirectional Anki→md sync (md is canonical, one-way md→Anki).
- Cloze / multi-type-per-unit generation by default (opt-in later).

---

## 3. Source data (already audited)

| File | Type | Yield | Format |
|---|---|---|---|
| `org/wiki/business/marketing/inbound-negotiation-prep.md` §0 | vocab | **40 terms** + 6 marker phrases | `\| **term** / **alt** \| смысл \| "phrase" \|`, 4 categories |
| `org/wiki/business/marketing/client-call-glossary.md` | vocab | **88 terms** | `\| Term \| What it means \| Why it matters \| Say it like \|`, staged |
| `org/wiki/business/marketing/client-call-qa.md` | Q&A | **47 questions** | `### Q: "…"` → blockquote answer, grouped A–H (some have `*lead-in:*` variant cues) |
| `org/wiki/business/marketing/*.md` (~17 more) | **prose** | unstructured | positioning, strategy, playbooks… → needs LLM extraction (v2) |

Environment: `OPENROUTER_API_KEY` is **set** in both shell env and
`~/pets/md-agent/.env`. Free models configured in md-agent:
`openai/gpt-oss-20b:free`, `meta-llama/llama-3.3-70b-instruct:free`.

---

## 4. Tool landscape evaluation (build-vs-borrow)

Researched 2026-07-30. **Decisive finding: none of these parse *our* existing
structured markdown.** Every tool imposes its own input format.

| Tool | Lang / type | Input it requires | LLM | Sink | Maintained | Fit for us |
|---|---|---|---|---|---|---|
| **anki-llm** (raine) | Rust CLI/TUI | **CSV/YAML** (not md); `generate` does term→card via LLM | yes (OpenRouter-native, `--api-base-url`) | AnkiConnect upsert by key-field; batched+resume; TTS | active, mature (`cargo install`/`brew`) | **Closest engine**, but needs a md→CSV parser in front and fights its prompt/fields model for our table semantics |
| **ankiops** (visserle) | Python + Anki addon | Its **own md** (`Q:`/`A:`/`T:` labels, `\n---\n`); **writes `<!-- note_key -->` comments back into your files**; bidirectional | yes (LLM tasks on JSON batches) | bidirectional Anki↔md sync, Git | active (578 commits, PyPI) | **Wrong fit** — colonizes/rewrites our wiki; bidirectional overkill |
| **yanki** (kitschpatrol) | TS CLI/lib | Its own md (YAML frontmatter + note delimiters); supports GFM tables *inside* cards | no | genanki (.apkg) | active | Needs reformatting; tables-in-cards ≠ tables→cards |
| **md2anki** (lucagrippa) | Web app | Upload one md → AI → download `.apkg` | yes (closed) | `.apkg` | side-project | Not CLI, not scriptable, not our format |
| **Obsidian_to_Anki** | Obsidian plugin / py script | Inline syntax tags (`TARGET DECK`, `START/END`) in your md | no | AnkiConnect | maintained | Requires tagging every note by hand; ~175 manual edits |
| **ankify** (wxxedu) | Python CLI | Its own md (`#### Question`/`#### Answer` code blocks, YAML) | no | AnkiConnect | small | Requires reformatting all sources |
| **AI-AnkiSync** (Obsidian plugin) | Obsidian plugin | Obsidian vault | yes | AnkiConnect | score 52/100, 0 reviews | We're not on Obsidian |

> `github.com/topics/pdf-watermark` (in the review list twice) is a paste error — unrelated to Anki.

### Build-vs-borrow verdict
**Build a small custom tool.** Borrow ideas from anki-llm (batched LLM w/ resume,
AnkiConnect upsert-by-key) but don't depend on it — at our scale (~175 cards)
those primitives are ~40 lines of HTTP each, and anki-llm's full sophistication
(concurrency, TTS, deck-style analysis) is overkill plus a Rust dependency we
don't need. ankiops is the most complete but it wants to *own* our markdown
format; rejected.

---

## 5. Architecture

```
~/pets/md2anki/                      (Python — genanki + requests; both sinks in one project)
├── PLAN.md                          this file
├── md2anki/                         package
│   ├── cli.py                       build / sync / export / list   (argparse)
│   ├── extract/
│   │   ├── structured.py            deterministic: tables → Vocab, ### Q: → Q&A   (0 LLM cost)
│   │   └── prose.py                 LLM extraction for unstructured md (v2)
│   ├── enrich.py                    free-OpenRouter: extra examples + answer variants (batched, cached)
│   ├── store.py                     cards.json read/merge/incremental-by-hash
│   ├── sink/
│   │   ├── ankiconnect.py           add-or-update by stable id   (primary)
│   │   └── apkg.py                  genanki portable file         (fallback)
│   └── config.py                    paths, model, deck ids, rate limits
├── cards.json                       canonical intermediate artifact (git-trackable)
├── enrichment.cache.json            LLM response cache (keyed by source hash)
└── out/*.apkg                       generated decks
```

Pipeline: **parse → enrich → `cards.json` → sink**. The intermediate JSON is the
canonical artifact; the sink is swappable.

---

## 6. Data model

### `cards.json` (versioned, incremental)
```json
{
  "version": 1,
  "generatedAt": "2026-07-30T11:00:00Z",
  "cards": [
    {
      "id": "vocab:glossary:retainer",
      "deck": "Business::Vocab",
      "type": "vocab",
      "fields": {
        "Term": "retainer",
        "Meaning": "ежемесячная предоплата за резерв мощности",
        "Why": "Stabilizes revenue and commits capacity.",
        "Example": "\"Maintenance runs on a monthly retainer.\"",
        "AIExamples": ["…", "…"]
      },
      "tags": ["pricing", "glossary", "stage:scoping"],
      "source": "marketing/client-call-glossary.md",
      "sourceLocator": "Stage 1 / row 12",
      "sourceHash": "sha256:…",
      "enriched": true
    },
    {
      "id": "qa:client-call:too-expensive",
      "deck": "Business::ClientQA",
      "type": "qa",
      "fields": {
        "Section": "G. Objections & closing",
        "Question": "\"That's more than we budgeted / it's too expensive.\"",
        "Answer": "<canonical blockquote answer from the md>",
        "Variants": ["<LLM paraphrase 1>", "<LLM paraphrase 2>"]
      },
      "tags": ["objections", "pricing"],
      "source": "marketing/client-call-qa.md",
      "sourceLocator": "§G Q4",
      "sourceHash": "sha256:…",
      "enriched": true
    }
  ]
}
```

- **`id`** is deterministic (`<type>:<file-stem>:<slug>`). Drives AnkiConnect
  upsert (stored in note's first field / a `SourceId` field) and genanki `guid`.
- **`sourceHash`** per card enables incremental rebuilds + cache validity.

### Anki note types (models)
| Model | Fields | Card |
|---|---|---|
| `Business Vocab` | Term, Meaning, Why, Example, AIExamples, SourceId | Front: Term · Back: Meaning + Why + Example + AIExamples |
| `Client Q&A` | Section, Question, Answer, Variants, SourceId | Front: Question · Back: Answer + Variants |

---

## 7. Extraction rules

### Structured (deterministic, 0 LLM cost) — v1
- **Tables** (`\| Term \| … \| Say it like \|` and the 4-col glossary variant):
  strip markdown bold/italics → `Term`; map remaining columns by header name;
  HTML-convert cell content (Anki renders HTML). One Vocab card per row.
- **`### Q: "…"` + following blockquote**: Question = the quoted text; Answer =
  the blockquote body (join continuation `>` lines). Preserve `*lead-in:*`
  italic cues as a sub-label. Section = nearest `## ` header. One Q&A card each.
- **Marker-phrase bullets** (`- "Before I quote, …"`): optional Vocab card with
  Term = first 5 words, Meaning = "(trust marker)", Example = the phrase.

### Prose (LLM, grounded) — v2
For md without recognized structure: send the section (chunked) to the LLM with
a prompt that returns JSON cards. **Here "AI picks card type" is justified**
(no structure to map). Respect `<!-- anki:cloze|qa|skip -->` hints when present.

---

## 8. Enrichment design

- **Provider:** OpenRouter, free models. Primary `openai/gpt-oss-20b:free`,
  fallback `meta-llama/llama-3.3-70b-instruct:free`. Read `OPENROUTER_API_KEY`
  from env (or `~/pets/md-agent/.env`).
- **Batching:** ~10 terms per call (one call ⇒ N example sentences). ~18 calls
  total for the whole v1 corpus — a **one-time** cost.
- **Rate limit:** ≤5 calls/min (house rule + free-model caps). Sleep between
  batches.
- **Caching:** `enrichment.cache.json` keyed by `sha1(term|question)`. Re-runs
  cost **zero** API calls for unchanged content. Invalidate via `sourceHash`.
- **Grounding guardrail:** for the Q&A deck, the LLM only **paraphrases** the
  canonical answer into variants — it never invents the answer. For Vocab, the
  LLM generates *additional* example sentences using the term; the source's own
  "Say it like" example is always preserved verbatim.

---

## 9. Sinks

### Primary: AnkiConnect (addon `2055492157`, `localhost:8765`)
- Smoothest loop: edit md → `md2anki build` → `md2anki sync` → done (no import dialog).
- Upsert: `findNotes` by `SourceId` field → `addNote` (new) or `updateNoteFields`
  (existing). Stable `id` guarantees no duplicates across re-runs.
- Requires Anki desktop running + addon installed. Tags propagated via `addNote`.

### Fallback: `.apkg` (genanki)
- `md2anki export --apkg out/business.apkg` — portable, headless, shareable.
- genanki `guid` derived from the stable `id` → re-import updates existing notes.
- No Anki running required.

---

## 10. CLI surface
```
md2anki build  <path>            # file or dir (recursive); structured extract; enrich; write cards.json
              [--deck NAME]
              [--no-enrich]
              [--prose]          # enable LLM prose extractor (v2)
md2anki sync   [--deck NAME] [--dry-run]    # AnkiConnect upsert
md2anki export [--apkg FILE] [--deck NAME]  # genanki portable file
md2anki list   [--deck NAME] [--due]        # inspect cards.json
```

---

## 11. Guardrails
1. **No hallucinated business advice.** Every card grounded in source text; LLM
   only enriches/paraphrases. The Q&A answer is always *yours*.
2. **Review before sync.** `cards.json` is human-inspectable; `sync --dry-run`
   previews the diff.
3. **Restraint over coverage.** Default = **one card per knowledge unit**.
   Multi-type (Basic+Cloze+Reverse) is opt-in (`--variants` or per-section hints)
   to protect daily review volume — over-generation is the #1 reason people quit Anki.
4. **Predictable decks.** Deterministic type from structure; AI auto-typing only
   on unstructured prose. Surprising card types on each review is fatiguing.

---

## 12. Sequencing

- **v1 (this week):** structured extractor on the 3 audited files → Vocab +
  Q&A decks → AnkiConnect `sync`. **Goal: training in days, not weeks.**
- **v2:** prose LLM extractor + `build <dir>` across the whole marketing folder;
  `<!-- anki:* -->` hints; incremental rebuilds.
- **v3:** extend to other KB areas (Shopify, postgres, AI-SDK, Georgian IP,
  insurance, EN business vocab) — the "knowledge compiler" vision, earned.

---

## 13. Open decisions (blocking build)
1. **Language/sink** — Python + (AnkiConnect **and** genanki `--apkg`) [my rec:
   both sinks in one project] **vs** TS reusing md-agent's provider abstraction,
   AnkiConnect-only, apkg deferred.
2. **Project name** — `md2anki` (current) **vs** `anki-ai` (broader vision).
3. **v1 scope** — structured-only on the 3 files [my rec] **vs** include the
   prose extractor in v1.
