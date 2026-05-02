# nom-vn Platform — Strategic Build Plan

**Status as of 2026-05-02.** Living document; update with every wave shipped.

## What's shipped right now (verifiable)

**nom-vn (OSS) — 650 tests passing.** Recent commits:

- `nom.platform` — Protocol seams: Authenticator, RBAC, PIIDetector,
  Redactor, AuditForwarder. Default OSS impls. HMAC-signed offline
  license helper. Plugin discovery via entry points. ContextVar user
  propagation. `chat.server` consumes Authenticator Protocol;
  constant-time bearer contract preserved. Commit `655d240`.
- `nom.agents` — typed multi-agent runtime, 6 Anthropic patterns
  (Single, Chain, Route, Parallel, Voting, OrchestratorWorkers,
  EvaluatorOptimizer). JSON action protocol; AuditedLLM is the trunk.
  Built-in tools: RAGTool (file Q&A), PythonEvalTool (sanitised
  arithmetic), HTTPGetTool (allow-listed), FileReadTool
  (path-traversal-blocked). 21 tests. Commit `aacb740`.
- `nom.mcp` — minimal Model Context Protocol bridge. MCPServer
  exposes any nom.agents.Tool over JSON-RPC; MCPClient +
  MCPRemoteTool let nom.agents consume external MCP servers.
  Stdio + HTTP transports; audit hook per call. End-to-end test
  proves SingleAgent uses a remote MCP tool transparently. 14 tests.
- `nom.agents_api` — FastAPI routes. POST /api/agents/{name}/run
  (sync) and GET /api/agents/{name}/stream (SSE / agent2ui).
  StreamingTrace queues events from the worker thread; UIs subscribe
  and render in real time. 6 tests. Both in commit `669de4d`.
- `nom.jobs` — durable background-job runtime. Job / JobAttempt
  frozen value types, JobQueue Protocol with InMemory + SQLite impls,
  JobWorker with exponential backoff retry and audit-chain
  integration. 25 parametrised tests. Commit `686960a`.
- `nom.nlp` — VN NER (RegexNERModel baseline + safetensors-only
  HFNERModel), sentiment (LexiconSentimentModel), language detection
  (Unicode-frequency heuristic). 23 unit tests + 7 REST API tests.
  Plus `nom worker` and `nom mcp-serve` CLI subcommands. Commit
  `9db4623`.
- `nom.agents.recipes` — production-ready agent factories:
  `vn_doc_analyser` (lang+NER+sentiment pipeline), `legal_qa`
  (RAG-grounded Q&A with citations), `deep_research`
  (orchestrator-workers), `compliance_screener` (PII-redact agent
  wrapper). Demo at `examples/recipes_demo.py`. 11 tests.

**nom-vn-enterprise (private commercial) — 46 tests passing.** At
`../nom-vn-enterprise/`, single commit `5bf8c5e`:

- `nom_ee.auth.oidc.OIDCAuthenticator` — discovery + JWKS + JWT
  verify; license-gated; injectable signing key for offline tests
- `nom_ee.rbac.multi_tenant.MultiTenantRBAC` — SQLite tenant/user/role,
  honours claims-borne roles
- `nom_ee.privacy.vn_advanced.VNAdvancedPIIDetector` — VN
  proper-name + address heuristics on top of OSS regex
- `nom_ee.privacy.tokenize.TokenizeRedactor` — round-trippable
  per-tenant token vault
- `nom_ee.audit_forward.otel_forwarder.OTelAuditForwarder` — OTLP
  log shipper
- License gate (`nom_ee.license`) — HMAC-signed JSON, offline
  verifiable, cached per-process
- All five plugins discovered through entry points; OSS imports
  nothing from `nom_ee`

**Total: 737 tests passing across both repos** (691 OSS + 46 EE).
Neither pushed to remote — awaiting deployment authorisation.

## North star

Be the **open, on-prem, audit-ready alternative to the VN cloud-AI
incumbents** (FPT.AI, Viettel Cyberbot, VinBase, VNPT AI) — for
organizations that need source access, air-gap deployment, and
Luật 134/2025 evidence trails their proprietary SaaS competitors
can't credibly provide today.

This is **not** "first VN NLP stack" — that claim is wrong, the
incumbents already ship broader product catalogues (see Competitive
Landscape below). It IS "first **Apache-2.0, source-open,
air-gappable, compliance-bundled** VN stack." The differentiation is
specific and defensible:

1. **Open core** — Apache 2.0 source + verifiable build. Audit teams
   read the code; lawyers read the licence. No incumbent allows this.
2. **Air-gappable from day one.** Viettel offers private cloud
   (proprietary). FPT AI Factory rents GPUs to host FPT services.
   Neither ships a fully customer-controllable, source-open NLP
   stack you install behind your firewall.
3. **Compliance-by-construction.** Luật 134/2025 (effective
   2026-03-01) requires risk classification, audit trails, dossiers
   for high-risk systems. As of 2026-05, no VN AI vendor publicly
   advertises 134 readiness. We design for it.
4. **VN-first quality with reproducible benchmarks.** Vendors quote
   "95% accuracy" without protocol. We commit measurement scripts +
   real corpora + best-of-N. Auditable per CLAUDE.md §12.

## Competitive landscape (verified 2026-05-02)

| Vendor | Stack breadth | Deployment | License | Compliance posture |
|---|---|---|---|---|
| **FPT.AI / FPT Smart Cloud** | Broadest: ASR + TTS + OCR/IDP + eKYC + NLU + agents [^fpt1] | SaaS-only product surface; FPT AI Factory is GPU rental [^fpt2] | Proprietary closed | SOC 2 / ISO 27001 / PCI on infra; **no Luật 134 statement** [^fpt3] |
| **VNPT AI** | 12 products: speech, vision, OCR, NER, agents [^vnpt1] | Cloud + likely on-prem (state telco) | Proprietary closed | NIST FRVT top-10 for vnFace; **no 134 statement** |
| **VinBase / VinBigdata** | NLU + voice + vision + ViGPT LLM [^vin1] | Hybrid (unverified for air-gap) | Proprietary closed | Not published |
| **Viettel AI / Cyberbot** | ASR + TTS + chatbot + callbot [^viettel1] | **On-prem available** (Viettel Private Cloud) [^viettel2] | Proprietary closed | ISO 27001 + Decree 53/2022 alignment; no 134 statement |
| **Zalo AI Lab** | Consumer-app-bound (Kiki, Kiki Info) [^zalo1] | Internal to Zalo platform | Proprietary closed | N/A — no enterprise SLA product |
| **Cốc Cốc** | Single slice: search-grounding API [^coc1] | SaaS only | Proprietary closed | "National digital platform" recognised; certs unverified |
| **MISA AMIS OneAI** (2026 launch) | Productized for SMB cross-sell with accounting/CRM [^misa1] | Hosted on local NVIDIA GPUs | Proprietary closed | Not detailed |
| **Underthesea** | OSS toolkit (NER, POS, word seg) | Library, not platform | **GPL-3.0** | N/A |
| **VinAI/MovianAI** | Open weights (PhoBERT, PhoWhisper) — research artifacts | HF-hosted weights | MIT/Apache | N/A; **acquired by Qualcomm 2025-04-01** [^vinai1] |

**Where nom-vn fits.** None of the above ship the four-way intersection
of (a) Apache 2.0, (b) air-gappable, (c) bundled compliance plugins
for Luật 134 + Nghị định 13, (d) reproducible VN benchmarks. That's
the wedge. Underthesea is the closest open-source reference but is
GPL-3 (incompatible with most enterprise procurement) and a library,
not a platform.

[^fpt1]: https://fpt.ai/ — product wall, plus voice/eKYC/IDP product pages.
[^fpt2]: https://docs.fpt.ai/docs/en/speech/documentation/stt-pricing/ — only metered cloud tiers; https://factory.fpt.ai/ — GPU rental layer.
[^fpt3]: https://fptcloud.com/en/fpt-ai-factory-in-review-2025-taking-the-lead-in-ai-innovation/
[^vnpt1]: https://vnptai.io/vi
[^vin1]: https://vinbigdata.com/en/vinbase
[^viettel1]: https://viettelai.vn/en
[^viettel2]: https://viettelai.vn/en/privacy/policy
[^zalo1]: https://kiki.zalo.ai/
[^coc1]: https://coccoc.com/en/coc-coc-search-api
[^misa1]: https://www.misa.vn/en/154177/misa-launches-misa-amis-oneai-...
[^vinai1]: https://techcrunch.com/2025/04/01/qualcomm-acquires-generative-ai-division-of-vietnamese-startup-vinai/

## Defensible vs. fluff

| Claim | Status | Why |
|---|---|---|
| "First Apache-2.0 + air-gappable + 134-ready VN stack" | **Defensible** | Verified — none of incumbents fit all 4 criteria (2026-05) |
| "Designed for Luật 134/2025 high-risk obligations" | **Defensible** if phrased "designed for" not "certified for" | No vendor publicly certified yet; we're early but not lying |
| "Reproducible benchmarks vs Underthesea / bkai / mE5" | **Defensible** | `benchmarks/` is committed |
| "First full-stack VN NLP" | ❌ **Retract** | Wrong — FPT/VNPT/VinBase have broader catalogs |
| "Best-in-class VN ASR/TTS" | ❌ **Don't claim** | No head-to-head benches vs PhoWhisper/FPT STT yet |
| "Production-grade" | ⚠️ Soft until named reference deploys | Use "designed for production" |

## Architecture: open core split

```
nom-vn (Apache 2.0, public)            nom-vn-enterprise (commercial, private)
├── nom.text, chunking, embeddings    ├── nom_ee.auth (OIDC, SAML, LDAP)
├── nom.rag, llm, retrieve, doc       ├── nom_ee.rbac (multi-tenant SQL/PG)
├── nom.compliance (full)             ├── nom_ee.privacy (NER + tokenize)
├── nom.platform (Protocol seams)     ├── nom_ee.audit_forward (SIEM shippers)
├── nom.agents (full)                 ├── nom_ee.connectors (Office, Teams, …)
├── nom.mcp.{server,client} (full)    ├── nom_ee.admin (console + API)
├── nom.jobs (full)                   ├── nom_ee.compliance_pro (cross-WS)
├── nom.nlp (NER, sentiment, …)       ├── nom_ee.training (customer fine-tune)
├── nom.translate (VN ↔ EN/ZH/JP)
├── nom.asr / nom.tts
└── ui (chat + agent viewer)          └── ui_admin (admin + compliance pro)
```

**Invariant (one-way):** EE imports OSS; OSS never imports EE.
Plugins register via `importlib.metadata` entry-point groups
(`nom.platform.*`). Activation = `pip install nom-vn-enterprise` +
licence file. License is HMAC-signed JSON, offline-verifiable for
air-gapped deployments.

## Waves — sequenced delivery

### Wave 0 — Foundation ✅ shipped (2026-05-02)

- `nom.compliance` (audit chain, risk classifier, dossier, transparency, incident).
- `nom.platform` Protocol seams (Authenticator, RBAC, PIIDetector, Redactor, AuditForwarder).
- Default OSS impls (BearerTokenAuth, AllowAllRBAC, RoleSetRBAC, RegexPIIDetector, MaskRedactor, NoOpAuditForwarder).
- License helper (`sign_license`, `verify_license`).
- Plugin discovery via entry points.
- `current_user` ContextVar for per-request identity propagation.
- `nom.chat.server` refactored to consume Authenticator.
- 95+ tests green; backward-compat preserved.

### Wave 1 — EE plugins for P0 enterprise gating (in progress, ~2 weeks)

- [x] `nom-vn-enterprise` repo skeleton, commercial LICENSE, pyproject with entry points.
- [x] `nom_ee.auth.oidc.OIDCAuthenticator` — discovery + JWKS + JWT verify, license-gated.
- [x] `nom_ee.rbac.multi_tenant.MultiTenantRBAC` — SQLite tenant/user/role store.
- [x] `nom_ee.privacy.vn_advanced.VNAdvancedPIIDetector` — composes OSS regex + VN proper-name + address heuristics.
- [x] `nom_ee.privacy.tokenize.TokenizeRedactor` — round-trippable tokens.
- [ ] `nom_ee.auth.saml` (optional extra).
- [ ] `nom_ee.auth.ldap` (optional extra).
- [ ] `nom_ee.audit_forward.{splunk,otel}` shippers.
- [ ] EE test suite (license, OIDC w/ fake provider, RBAC, redactor roundtrip).
- [ ] End-to-end integration: install both packages in venv, prove plugin discovery wires the OIDC flow against a fake provider.

### Wave 2 — Agent runtime (~2 weeks)

- [ ] **Research:** read Anthropic's Building Effective Agents in full,
  Claude Code subagent docs, ADK workflow primitives, Pydantic AI typed
  shape. Output: `docs/research/2026-05-agent-design.md`.
- [ ] `nom.agents.protocol` — `Agent`, `Tool`, `State`, `StateGraph` Protocols (≤200 LOC).
- [ ] `nom.agents.checkpoint` — HMAC-chained checkpoints, reuses `nom.compliance.audit` infra.
- [ ] `nom.agents.runner` — graph executor, audit-first, resume-after-crash.
- [ ] **6 patterns** (each ≤200 LOC, per Anthropic taxonomy):
  - `ChainAgent` — sequential prompt chaining.
  - `RouteAgent` — classify → dispatch.
  - `ParallelAgent` — fan-out, sectioning + voting variants.
  - `OrchestratorWorkers` — supervisor + dynamic worker delegation.
  - `EvaluatorOptimizer` — generator-critic loop with bounded iterations.
  - `AutonomousAgent` — open-ended loop with environment feedback + safety budget.
- [ ] Built-in tools wrapping `nom.rag`, `nom.doc`, `nom.text`, `nom.nlp`.
- [ ] Smoke against real Ollama; published bench against pure-LLM baseline.

### Wave 3 — MCP + background jobs (~2 weeks)

- [ ] `nom.mcp.server` — expose `nom.rag`, `nom.doc`, `nom.text`, `nom.nlp` as MCP tools.
  Verify with Claude Desktop config + Cursor.
- [ ] `nom.mcp.client` — `nom.agents` consumes external MCP servers as tools.
  Each call audited via `AuditedLLM` companion.
- [ ] `nom.jobs` — arq-based async queue (Apache 2.0, Redis or in-memory backend).
  Workers: indexing, agent runs, dossier export, PII vault rebuild.
- [ ] Job state mirrored into audit chain (Đ14.1.c "ai làm gì lúc nào").
- [ ] CLI: `nom worker` to spawn worker pool.

### Wave 4 — UI + streaming (~2 weeks)

- [ ] `nom.streaming` — `agent2ui` SSE protocol. Typed events (node-enter, tool-call,
  output-chunk, checkpoint-saved, error). Correlation-ID tied to gateway audit.
- [ ] React hook `useAgentRun(runId)` — reuses existing ui/ design tokens.
- [ ] Agent run viewer page (OSS): graph of state transitions, tool calls expanded,
  per-node prompt+response, audit links.
- [ ] Compliance console (OSS basic): dossier preview/export, incident form, risk wizard.

### Wave 5 — Scale (~2 weeks)

- [ ] Postgres backend for `nom.chat.store` + `nom.compliance.audit` (dual-driver via Protocol).
- [ ] pgvector adapter for `nom.embeddings`.
- [ ] vLLM cluster adapter (OpenAI-compat endpoint, token throughput config).
- [ ] Multi-tenant schema isolation in EE: `shared` / `schema-per-tenant` / `db-per-tenant`.
- [ ] Helm chart Tier-S/M/L with HPA, Postgres HA template, vLLM stateful set.
- [ ] Terraform modules: AWS, Azure, GCP, Viettel IDC, FPT Cloud.
- [ ] Backup/restore CLI.

### Wave 6 — VN NLP-as-a-service (AWS-equivalents for VN) — strategic differentiator (~3 weeks)

The "VN AWS" play. Each module ships as: pure-Python `nom.<module>`,
HTTP endpoint via `nom serve`, MCP tool, agent-runtime Tool. One
codebase, four delivery shapes.

- [ ] **`nom.nlp.ner`** — VN named-entity recognition (PER/ORG/LOC/MISC/DATE/MONEY).
  Candidates: PhoBERT fine-tunes on HF, `xlm-roberta-large-finetuned-vi-ner`
  (open weights, mostly Apache/MIT — verify each at adoption time).
  **Note:** PhoBERT is open-weight, not a productized service. Underthesea
  ships `ner()` but is GPL-3 — incompatible with our Apache redistribution.
  Build path: adopt the strongest Apache-2.0 + safetensors HF model,
  benchmark on VLSP NER task, publish numbers. If no model meets
  bar, fine-tune our own from XLM-R-base.
  Equivalent to **AWS Comprehend DetectEntities** + competes with
  FPT NLU's entity-extraction surface.
- [ ] **`nom.nlp.sentiment`** — sentence-level VN sentiment (negative/neutral/positive).
  Models: `vinai/sentiment-uit-vsfc`, `wonrax/phobert-sentiment`, etc.
  Equivalent to **AWS Comprehend DetectSentiment**.
- [ ] **`nom.nlp.keyphrases`** — keyphrase extraction (KeyBERT-style + VN tokenizer).
  Equivalent to **AWS Comprehend DetectKeyPhrases**.
- [ ] **`nom.nlp.lang_detect`** — language detection (already trivial, ship a clean API).
  Equivalent to **AWS Comprehend DetectDominantLanguage**.
- [ ] **`nom.nlp.topics`** — unsupervised topic modelling (BERTopic + VN embedder).
  Equivalent to **AWS Comprehend Topic Modeling**.
- [ ] **`nom.translate`** — VN ↔ EN/ZH/JP/KR. Research: NLLB-200 (CC-BY-NC — license risk),
  `Helsinki-NLP/opus-mt-vi-en` (Apache 2.0), `vinai/vinai-translate`.
  Equivalent to **AWS Translate**.
- [ ] **`nom.asr`** — VN speech-to-text. Research: `openai/whisper-large-v3` (MIT,
  strong VN coverage), `vinai/PhoWhisper`, `viettel-ai/vai-asr-large`.
  Equivalent to **AWS Transcribe**.
- [ ] **`nom.tts`** — VN text-to-speech. Research: `coqui/XTTS-v2` (CPML — license
  needs review), `vinai/vinatts`, `facebook/mms-tts-vie` (CC-BY-NC).
  Equivalent to **AWS Polly**.
- [ ] **`nom.doc.forms`** — form-field extraction (key-value pairs, signatures).
  Equivalent to **AWS Textract AnalyzeDocument**.
- [ ] **`nom.doc.tables`** — structured table extraction (already partial in `nom.doc`,
  productize).
- [ ] **`nom.address`** — VN address parser/normalizer (đường/phường/quận/TP standardization).
  No clean AWS equivalent — pure VN play.

**Trust ladder for adopting external models:**
1. Apache/MIT/BSD + safetensors → adopt freely.
2. CC-BY (commercial OK) + safetensors → adopt with attribution.
3. CC-BY-NC / CPML → research-only; ship our own permissively-licensed
   replacement before commercial release.
4. `.pkl` / `.pickle` → auto-reject (CLAUDE.md §11).

**Benchmark requirement (CLAUDE.md §12):** every NLP module ships
with a measurement script, real VN corpus (≥2 registers), best-of-N
methodology, baseline JSON committed.

### Wave 7 — Domain-specific NLP (EE moats) (~3-4 weeks each)

These need both ML expertise and VN domain partnerships. Each is a
separate go-to-market.

- [ ] **`nom_ee.legal`** — VN legal NER (statute citations, party
  resolution, court names), legal-corpus RAG presets, contract-clause
  classification. Aligned with Đ27 impact-assessment dossier.
- [ ] **`nom_ee.medical`** — VN medical NER (diagnosis ICD-10-VN,
  drug names, dosages), de-identification per Bộ Y Tế guidelines,
  hospital-corpus presets. Hospital pilot required before GA.
- [ ] **`nom_ee.banking_kyc`** — KYC document extraction (CCCD, DKKD,
  hộ khẩu), liveness-check integration points, AML watchlist matching.
- [ ] **`nom_ee.insurance`** — claim form extraction, fraud-signal
  scoring, policy-clause Q&A presets.

### Wave 8 — Integrations + ecosystem (rolling)

- [ ] OSS MCP catalog: Slack, GitHub, Linear, web-fetch, postgres, Notion.
- [ ] EE connectors: SharePoint, Outlook, OneDrive, Teams, Confluence, JIRA.
- [ ] Adapter docs (already in `docs/integrations/`): expand for
  agent runtime — show how to use `nom.agents` from inside LangChain,
  ADK, Pydantic AI flows.
- [ ] Customer fine-tuning workflow (`nom_ee.training`): upload corpus
  → eval → fine-tune → publish private HF repo. Operator workflow on
  the EE admin console.

## Decisions chốt (durable)

| Decision | Rationale |
|---|---|
| Open core, EE imports OSS (one-way) | Mitigates fork risk, preserves moat |
| Plugin discovery via entry points | Standard, no DI framework needed |
| HMAC-signed offline licence | Air-gapped customers must work; phone-home is a non-starter for VN gov |
| Compliance, agents, MCP **stay OSS** | These are the moat; closing them kills adoption |
| Auth/RBAC/SIEM/admin console **EE-only** | "Vấn đề công ty 200 người" — clear value-add |
| Build `nom.agents` natively, not LangChain | Per research turn — pickle policy, audit traceability, VN gotchas |
| One codebase across S/M/L/X tiers | Config-driven, not fork-driven |
| Every module ships with VN benchmark | CLAUDE.md §12 — no fake numbers |
| Cite Viet-Anh Nguyen + Neural Research Lab on every artifact | CLAUDE.md §13 |
| `safetensors` only for ML deps | CLAUDE.md §11 |

## Quyết định cần chốt sớm (block Wave 2-3)

1. **Postgres timing.** Default backend for Tier-M+: SQLite WAL or Postgres?
   *Lean: SQLite through Wave 5; Postgres adapter then.*
2. **Background queue tech.** `arq` (asyncio, Redis) vs in-process `asyncio.Queue`
   for Tier-S?
   *Lean: in-memory default, arq when Redis is available.*
3. **MCP server transport.** stdio for desktop clients only, or also HTTP/SSE for
   server-side use?
   *Lean: ship both — stdio for Claude Desktop / Cursor, HTTP/SSE for `nom.agents` to consume.*
4. **VN NER baseline model.** PhoBERT-large fine-tune we curate, or off-the-shelf
   Apache 2.0 release?
   *Action: research turn before Wave 6 start.*
5. **Tier-X air-gapped story.** Periodic refresh via signed `.tar.gz` bundle
   delivered to customer? Or full self-mirror of HF?
   *Lean: signed bundle; self-mirror is over-engineering for v1.*

## Doanh thu — recommend ordering ROI

Wave 1 closes the 5 P0 vendor-security-review fails — needed for first
deal. Wave 2-3 (agents + MCP) is what makes "AI platform" not "RAG
tool" — closes the gap with how customers think about modern AI in
2026. Wave 6 (VN NLP-as-a-service) is the *category-defining* play:
no one offers this for VN today. Each module is a separately
sellable API surface ("NER as a service for VN", "VN translation API
on-prem", "VN ASR for hospitals") that doesn't even require the full
RAG/chat stack.

## What this plan is NOT

- Not a sprint plan. Wave durations are Claude-Code-augmented engineering
  estimates; bottleneck is decision quality + customer conversation.
- Not a feature catalog for marketing — most of these are technical
  moves; their customer-facing names are TBD.
- Not committed externally. Doanh-nghiep page must NOT reference any
  Wave-2+ feature until it ships (CLAUDE.md verified-benchmarks rule).

## Success metrics per wave

| Wave | Ship gate |
|---|---|
| 1 | EE OIDC + RBAC pass an external pen-test contract; one banking pilot signs MSA |
| 2 | `nom.agents` benches ≥ pure-LLM baseline on VN-deep-research task; demo internally |
| 3 | Claude Desktop ships nom-vn as a featured MCP server; one customer routes 100% via MCP |
| 4 | Three reference deployments running agent run viewer; SLO p95 < 2s for SSE first-byte |
| 5 | Tier-L deploy survives 1k QPS for 24h with chain integrity; one healthcare deal |
| 6 | Each NLP module: VN bench ≥ best public number; published model card on `nrl-ai/*` |
| 7 | One regulated-domain customer per module live in production |
| 8 | ≥5 OSS MCP integrations, ≥3 EE connectors live |

## Anti-goals

- Do NOT pull LangChain/LangGraph as a hard dep (per research turn).
- Do NOT ship telemetry-by-default in OSS (CrewAI failure mode).
- Do NOT crippleware the OSS to push EE — solo VN dev must get a complete product.
- Do NOT promise compliance posture we haven't measured (CLAUDE.md §12).
- Do NOT support Hán-Nôm corpora (project scope: modern VN in chữ Quốc Ngữ).
