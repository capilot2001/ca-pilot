# Engineering Principles

Durable rules for LedgerFlow v2. These apply across **every** phase and change rarely. A change
to a principle is significant enough that it must be recorded as an ADR in [decisions/](decisions/).

Each principle states the rule, then *why*, so it can be applied with judgment rather than
followed blindly.

---

## P1 — The codebase is deployment-platform-independent
**Rule.** Application code must not know which platform it runs on. No `if cloud_run:`,
no hardcoded hosts, ports, paths, or credentials. The **container is the portability boundary**;
**config (env) is the only thing that knows a platform.**

**Why.** We will move between platforms (dev: Vercel + Railway + Cloud Run; prod: possibly
all-Railway or AWS). Moving platforms must be a change to `deploy/` configs and environment
variables — never a code change. This is the central constraint of the whole architecture.

## P2 — 12-factor configuration
**Rule.** Everything that varies between environments — secrets, URLs, DB location, provider
selection, ports, CORS origins — comes from environment variables, loaded through one typed
settings module per service. Logs go to stdout. Services are stateless.

**Why.** It is what makes P1 real and testable, and it keeps secrets out of the codebase.

## P3 — Ports & adapters only at real seams
**Rule.** Put an interface (port) + swappable implementations (adapters) **only** where there is
a genuine boundary: the database, the LLM provider, the OCR provider, the extraction service, and
future external systems (Tally, GST portal). **Never** wrap pure functions
(`classify`, `validate`, `masters`) in a port.

**Why.** Interfaces at real seams make the expensive things swappable (change a dependency, not a
rewrite). Interfaces around pure logic are pure overhead — indirection with no second
implementation. This is how we stay extensible *without* over-engineering.

## P4 — Reader reads, code decides
**Rule.** The AI/OCR layer only **reads** what is printed on a document. All accounting
judgement — nature of transaction, tax, ledger selection, the balanced journal — is done by
deterministic code (`classify`). This holds **even across a service boundary**: the OCR service
returns a *reading*; the core server decides.

**Why.** Accounting must be explainable, auditable, and reproducible. Models are probabilistic;
ledgers cannot be. Keeping the decision in code is what a CA can trust and sign off.

## P5 — Migrate logic unchanged (in a migration phase)
**Rule.** When the goal is migration (Phase-0), the *behaviour* of the domain logic
(`ocr`, `llm_extract`, `classify`, `validate`, exporters) does not change. Structure,
orchestration, and deployment may change; what the functions compute does not.

**Why.** It lets us verify the move by comparing outputs, and separates "we restructured" from
"we changed behaviour" — two things that must never be debugged together.

## P6 — Don't over-engineer for the current scale
**Rule.** Build the **boundary** now; defer the **mechanism** until load demands it. Example:
structure OCR as its own service with its own contract from day one, but you may run it
in-process until throughput/timeouts require the network split — flipped by config.

**Why.** The boundary is cheap and keeps options open; premature mechanism (clusters, sharding,
microservice sprawl) is expensive and often wrong. Let real numbers trigger the next step.

## P7 — State lives in a datastore, not in a service
**Rule.** Services are disposable. Durable state lives in the database/volume/queue, never on a
service's local disk or memory. Any service instance can be killed and replaced.

**Why.** It is what lets us autoscale OCR workers, redeploy freely, and survive the ephemeral
filesystems of Cloud Run / Railway.

## P8 — Backpressure and fairness are first-class
**Rule.** Heavy work (OCR/extraction) goes through a queue that (a) rate-limits to stay within
external quotas and (b) enforces **per-tenant fairness** so one CA's large batch cannot starve
others.

**Why.** At target scale (100 CAs, ~20k invoices/day) a shared worker pool and a shared Google
quota are contended resources. Without fairness, the loudest tenant degrades everyone.

## P9 — Cost is a design input, not an afterthought
**Rule.** Per-invoice external cost (Vision + Gemini) is tracked and optimized as part of the
design. Prefer the cheapest correct path (e.g. PDF text layer before OCR; Batch API for
non-urgent work; dedup).

**Why.** At scale the Google bill is a real COGS line (~$13–26 per CA/month, estimated) that
directly shapes SaaS pricing. Small routing choices move it materially.

## P10 — Decisions, principles, and bets are written down
**Rule.** Significant choices become ADRs; assumptions become hypotheses with a validation plan;
rules become principles. Code is not the only artifact; the *reasoning* is maintained too.

**Why.** This project will outlive any one contributor's memory. The docs are how the next person
inherits the context instead of re-deriving it (or breaking it).
