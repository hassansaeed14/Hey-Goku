# AURA MASTER SPEC
## Autonomous Universal Responsive Assistant

**Document type:** Reality-based master doctrine  
**Status:** Active  
**Version label:** v1.0-dev  
**Last updated:** 2026-04-11

---

## 1. Project Identity

**AURA** stands for **Autonomous Universal Responsive Assistant**.

AURA is a private, JARVIS-style AI operating system designed to understand, route, execute, remember, and improve through real system behavior.

AURA is:
- a local/private-first AI runtime
- a multi-view assistant interface
- a routed system with memory, security, and execution layers
- a hybrid architecture that combines deterministic logic and provider-backed intelligence

AURA is not:
- a generic chatbot
- a fake “AI OS” shell
- a prompt wrapper pretending to be an assistant
- a release-ready public v1.0 product

---

## 2. Core Goal

The goal of AURA is to become a dependable human-quality personal assistant that can:

- understand natural language and messy input
- respond naturally in text and voice
- route tasks to the right system path
- remember useful context
- operate under a real trust model
- improve over time without overclaiming capability

Core pipeline:

**Perceive -> Understand -> Decide -> Act -> Reflect -> Improve**

---

## 3. Current Product Truth

AURA is currently a **real development-stage private AI OS prototype**.

It already has:
- a working local private web runtime
- a real backend request path
- structured local memory layers
- local chat history persistence
- a security model with auth, approvals, and PIN support
- a broad agent catalog
- voice-related infrastructure
- tests across major runtime layers

It does **not** yet qualify as a fully dependable release product because:
- provider readiness and routing still require hardening
- some capabilities remain partial
- some UI surfaces still overstate confidence
- vector memory needs repair
- parts of the agent ecosystem are wrapper-based rather than deep bespoke integrations
- some legacy runtime drift still exists

---

## 4. Product Standard

AURA must feel like:
- a capable human personal assistant
- private and trustworthy
- intelligent and calm
- fast and direct
- premium in tone and behavior
- honest under failure

AURA must not feel like:
- a toy chatbot
- a robotic template engine
- a fake JARVIS theme over weak internals
- a UI that claims more than the backend can do

---

## 5. Reality Rules

These rules are mandatory across the whole project:

- Reality over hype
- Working over advertised
- Verified over assumed
- Configured does not mean healthy
- Partial systems must be labeled partial
- Placeholder systems must be labeled placeholder
- Broken systems must be surfaced honestly
- UI must never outrun backend truth
- Security must never be cosmetic
- Memory must never be faked
- Execution must never be implied without a real path

---

## 6. Architecture Truth

Primary runtime path:

`AURA.bat -> run_aura.py -> Waitress -> FastAPI -> brain -> agents/memory/security/voice -> web UI`

Current architectural facts:
- the private web runtime is the main live path
- older runtime layers still exist and create maintenance drift
- backend execution relies on a brain/runtime path plus multiple supporting subsystems
- the agent catalog is broad, but many agents are generated wrappers over shared fabric
- structured memory is real
- vector memory exists but is currently not yet dependable enough to overclaim

---

## 7. System Layers

### Brain
Responsible for understanding, routing, decision-making, provider usage, response generation, and runtime orchestration.

### Agents
Responsible for capability-specific task handling.
AURA may expose many agents, but only real, wired behavior may be advertised as dependable.

### Memory
Responsible for chat history, working memory, semantic memory, episodic memory, and future retrieval quality.

### Security
Responsible for identity, session trust, approvals, confirmation flows, PIN protection, and guarded execution.

### Voice
Responsible for speech input, speech output, wake-word-related flow, and spoken response quality.

### Interface
Responsible for presenting truthful status, conversation flow, settings, history, voice controls, and a premium user experience.

### Forge
Responsible for auditing, repairing, building, and evolving AURA itself.

---

## 8. Trust Model

Trust categories:

- **safe** -> auto allow
- **private** -> ask confirmation
- **sensitive** -> session approval
- **critical** -> confirmation code + PIN

This trust model must be enforced through real execution paths.
No feature is considered secure until trust enforcement is actually wired to the action path.

---

## 9. Assistant Quality Standard

AURA’s user-facing voice must be:

- natural
- precise
- warm
- calm
- intelligent
- premium
- human-sounding

AURA should:
- answer the actual question first
- avoid robotic filler
- avoid repeated apologies
- avoid canned template behavior
- produce text that also sounds natural when spoken aloud

---

## 10. Provider Standard

Provider rules:

- configured != healthy
- provider health must come from real verification or recent successful runtime evidence
- provider routing must be explicit and testable
- degraded mode must be honest
- provider status shown in UI/API must be truthful

Target runtime routing direction:
- Gemini as primary
- OpenAI as backup
- Groq as fallback
- honest degraded mode when no provider is healthy

---

## 11. Agent Truth Standard

AURA may expose a large catalog of agents, but:

- wrapper agents must not be marketed as deep bespoke systems
- placeholder families must be labeled clearly
- capability claims must match real behavior
- execution agents must go through real guards and permissions where required

The goal is not maximum agent count.
The goal is trustworthy capability.

---

## 12. Memory Standard

AURA memory should be:

- local/private-first
- structured
- useful
- non-fake
- explicit about health and limits

Current direction:
- SQLite-backed history remains valid
- structured local memory remains valid
- vector retrieval must be repaired and validated before stronger claims

---

## 13. Voice Standard

Voice is part of AURA’s identity.
However, voice quality is not judged by whether it can listen alone.
It is judged by end-to-end usefulness:

- hears correctly
- routes correctly
- answers correctly
- sounds natural aloud

AURA fails the voice standard if it listens but answers weakly.

---

## 14. UI Standard

The interface must earn trust.

That means:
- clear status
- no fake readiness
- no decorative confidence masking broken behavior
- premium feel through clarity, flow, and responsiveness
- strong listening, thinking, and answer states
- visible degraded modes when real issues exist

---

## 15. AURA Forge

**AURA Forge** is AURA’s internal upgrade and evolution system.

Forge is responsible for:
- audit
- repair
- build
- evolution
- patch reporting
- safe internal improvement

Forge must:
- be real
- follow the trust model
- never modify recklessly
- produce reports
- align implementation with this master spec

---

## 16. Current Priorities

### Priority 1
Verify and harden the live provider execution path.

### Priority 2
Replace fake provider readiness with real health checks and shared status truth.

### Priority 3
Improve assistant response quality so AURA feels human, relevant, and premium.

### Priority 4
Improve voice-input-to-answer quality.

### Priority 5
Repair vector memory and retrieval dependability.

### Priority 6
Resolve auth/session drift and clean security test failures.

### Priority 7
Reduce runtime drift and remove misleading legacy paths.

### Priority 8
Begin AURA Forge as a real internal subsystem.

---

## 17. Release Doctrine

AURA may keep the version label `v1.0-dev`, but public-facing language must remain honest.

Until provider truth, vector memory, response quality, UI trust, and runtime drift are materially improved, AURA should be described as:

**“a private AI OS prototype in active development.”**

Not as:
- complete
- fully dependable
- production-ready
- finished JARVIS

---

## 18. Final Rule

The purpose of AURA is not to imitate a powerful assistant.

The purpose of AURA is to become one.