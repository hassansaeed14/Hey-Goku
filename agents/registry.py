from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

from agents.agent_fabric import discover_generated_agent_blueprints
from config.master_spec import CAPABILITY_LABELS


VALID_CAPABILITY_MODES = set(CAPABILITY_LABELS)
VALID_TRUST_LEVELS = {"safe", "private", "sensitive", "critical"}
VALID_STATUSES = {"live", "experimental", "standby"}
CHAT_ROUTABLE_CAPABILITY_MODES = {"real", "hybrid"}

RUNTIME_REAL_AGENT_METADATA: Dict[str, Dict[str, Any]] = {
    "writing_runtime": {
        "name": "Writing Runtime",
        "category": "productivity",
        "description": "Direct runtime handler for general writing requests.",
        "trust_level": "safe",
        "backend": "runtime_writing_handler",
        "integration_path": "Handled directly inside brain.runtime_core with the live writing path.",
        "icon": "WRT",
        "stateful": False,
    },
    "research_runtime": {
        "name": "Research Runtime",
        "category": "productivity",
        "description": "Direct runtime handler for research requests.",
        "trust_level": "safe",
        "backend": "runtime_research_handler",
        "integration_path": "Handled directly inside brain.runtime_core with the live research path.",
        "icon": "RSH",
        "stateful": False,
    },
    "coding_runtime": {
        "name": "Coding Runtime",
        "category": "productivity",
        "description": "Direct runtime handler for coding requests.",
        "trust_level": "safe",
        "backend": "runtime_coding_handler",
        "integration_path": "Handled directly inside brain.runtime_core with the live coding path.",
        "icon": "COD",
        "stateful": False,
    },
    "summary_runtime": {
        "name": "Summary Runtime",
        "category": "productivity",
        "description": "Direct runtime handler for summarization requests.",
        "trust_level": "safe",
        "backend": "runtime_summary_handler",
        "integration_path": "Handled directly inside brain.runtime_core with the live summarization path.",
        "icon": "SUM",
        "stateful": False,
    },
    "document_generator": {
        "name": "Document Generator",
        "category": "documents",
        "description": "Direct runtime handler for notes, assignments, and exported document delivery.",
        "trust_level": "safe",
        "backend": "runtime_document_generator",
        "integration_path": "Handled directly inside brain.runtime_core and tools.document_generator.",
        "icon": "DOC",
        "stateful": False,
    },
    "document_retrieval": {
        "name": "Document Retrieval",
        "category": "documents",
        "description": "Direct runtime handler for follow-up document retrieval.",
        "trust_level": "safe",
        "backend": "runtime_document_retrieval",
        "integration_path": "Handled directly inside brain.runtime_core using generated document session memory.",
        "icon": "DOC",
        "stateful": True,
    },
    "transformation_engine": {
        "name": "Transformation Engine",
        "category": "documents",
        "description": "Direct runtime handler for content transformation into documents.",
        "trust_level": "safe",
        "backend": "runtime_transformation_handler",
        "integration_path": "Handled directly inside brain.runtime_core with tools.content_extractor and tools.document_generator.",
        "icon": "TRN",
        "stateful": False,
    },
}

UI_CLAIM_BY_MODE = {
    "real": "connected",
    "hybrid": "assisted",
    "placeholder": "planned",
}


@dataclass(frozen=True)
class AgentDescriptor:
    id: str
    name: str
    category: str
    description: str
    capability_mode: str
    trust_level: str
    backend: str
    integration_path: str
    status: str = "live"
    icon: str = "AI"
    stateful: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["ui_claim"] = UI_CLAIM_BY_MODE.get(self.capability_mode, "planned")
        payload["connected"] = self.capability_mode != "placeholder"
        payload["experimental"] = self.status == "experimental"
        payload["CAPABILITY_MODE"] = self.capability_mode
        return payload


def _agent(
    agent_id: str,
    name: str,
    category: str,
    description: str,
    capability_mode: str,
    trust_level: str,
    backend: str,
    integration_path: str,
    *,
    status: str = "live",
    icon: str = "AI",
    stateful: bool = False,
) -> AgentDescriptor:
    return AgentDescriptor(
        id=agent_id,
        name=name,
        category=category,
        description=description,
        capability_mode=capability_mode,
        trust_level=trust_level,
        backend=backend,
        integration_path=integration_path,
        status=status,
        icon=icon,
        stateful=stateful,
    )


MANUAL_AGENT_REGISTRY: tuple[AgentDescriptor, ...] = (
    _agent("general", "General AURA", "core", "Primary assistant.", "hybrid", "safe", "llm_orchestrated_runtime", "Intent routing plus LLM response generation.", icon="GEN"),
    _agent("reasoning", "Reasoning Agent", "core", "Logic and analysis support.", "placeholder", "safe", "rule_plus_llm_reasoning", "Connect this reasoning agent to verified multi-step analysis before enabling live routing.", icon="RSN"),
    _agent("compare", "Compare Agent", "core", "Tradeoff comparisons.", "placeholder", "safe", "structured_prompting", "Connect this comparison agent to validated comparison workflows before enabling live routing.", icon="CMP"),
    _agent("identity", "Identity Agent", "core", "AURA persona responses.", "placeholder", "safe", "prompted_persona", "Connect this identity agent to a distinct runtime behavior before enabling live routing.", icon="ID"),
    _agent("insights", "Insights Agent", "memory", "User insight summaries.", "hybrid", "private", "memory_analysis", "Stored interactions plus learned pattern summaries.", icon="MEM", stateful=True),
    _agent("permission", "Permission Guard", "security", "Deterministic policy checks.", "real", "safe", "policy_engine", "Connected to security.trust_engine.", icon="SEC"),
    _agent("study", "Study Agent", "productivity", "Teaching and explanation.", "placeholder", "safe", "llm_teaching", "Connect this study agent to a distinct teaching workflow before enabling live routing.", icon="STU"),
    _agent("research", "Research Agent", "productivity", "Research-style reports.", "placeholder", "safe", "llm_research", "Connect this research agent to a verified research runtime before enabling live routing.", icon="RSH"),
    _agent("code", "Coding Agent", "productivity", "Programming guidance.", "placeholder", "safe", "llm_coding_assistant", "Connect this coding agent to a dedicated coding runtime before enabling live routing.", icon="COD"),
    _agent("content", "Content Writer", "productivity", "Article and blog writing.", "placeholder", "safe", "llm_content_generation", "Connect this content agent to a dedicated writing runtime before enabling live routing.", icon="WRT"),
    _agent("email", "Email Writer", "productivity", "Professional email drafting.", "placeholder", "safe", "llm_email_generation", "Connect this email agent to a distinct drafting workflow before enabling live routing.", icon="EML"),
    _agent("summarize", "Summarizer", "productivity", "Condenses long input.", "placeholder", "safe", "llm_summarization", "Connect this summarizer to the verified summary runtime before enabling live routing.", icon="SUM"),
    _agent("grammar", "Grammar Agent", "productivity", "Proofreading and cleanup.", "placeholder", "safe", "llm_editing", "Connect this grammar agent to a verified editing workflow before enabling live routing.", icon="GRM"),
    _agent("quiz", "Quiz Agent", "productivity", "Quiz and flashcard generation.", "placeholder", "safe", "llm_quiz_generation", "Connect this quiz agent to a dedicated education workflow before enabling live routing.", icon="QIZ"),
    _agent("fitness", "Fitness Agent", "productivity", "Workout planning.", "placeholder", "safe", "llm_planning", "Connect this fitness agent to a verified planning workflow before enabling live routing.", icon="FIT"),
    _agent("task", "Task Agent", "productivity", "Task planning and tracking.", "hybrid", "safe", "json_store_plus_llm_planning", "memory/tasks.json persistence plus planning support.", icon="TSK", stateful=True),
    _agent("resume", "Resume Agent", "productivity", "Resume generation.", "placeholder", "safe", "llm_document_generation", "Connect this resume agent to the verified document runtime before enabling live routing.", icon="CV"),
    _agent("cover_letter", "Cover Letter Agent", "productivity", "Cover letter drafting.", "placeholder", "safe", "llm_document_generation", "Connect this cover-letter agent to the verified document runtime before enabling live routing.", icon="CL"),
    _agent("weather", "Weather Agent", "integration", "Live weather and forecast.", "real", "safe", "open_meteo_api", "Connected to Open-Meteo APIs.", icon="WTH"),
    _agent("news", "News Agent", "integration", "Live news headlines.", "real", "safe", "gnews_api", "Connected to the configured GNews API.", icon="NWS"),
    _agent("math", "Math Agent", "integration", "Calculation and equation solving.", "hybrid", "safe", "direct_eval_plus_llm", "Direct safe evaluation first, then LLM help.", icon="MTH"),
    _agent("translation", "Translation Agent", "integration", "Language translation.", "hybrid", "safe", "validation_plus_llm", "Validated inputs plus structured translation prompts.", icon="TRN"),
    _agent("web_search", "Web Search Agent", "integration", "Search and website summaries.", "hybrid", "safe", "live_search_plus_summary", "Live search and extraction with deterministic or LLM summaries.", icon="WEB"),
    _agent("currency", "Currency Agent", "integration", "Currency and crypto conversion.", "hybrid", "safe", "exchange_api_plus_llm_fallback", "Exchange APIs first with approximate fallback only when needed.", icon="FX"),
    _agent("dictionary", "Dictionary Agent", "integration", "Definitions and synonyms.", "hybrid", "safe", "dictionary_api_plus_llm_fallback", "Dictionary lookups first with LLM fallback.", icon="DCT"),
    _agent("youtube", "YouTube Agent", "integration", "YouTube topic and video help.", "hybrid", "safe", "oembed_plus_llm", "YouTube metadata plus bounded LLM analysis.", icon="YTB"),
    _agent("joke", "Joke Agent", "integration", "Light humor.", "placeholder", "safe", "llm_text_generation", "Connect this joke agent to a curated humor source before enabling live routing.", icon="JOK"),
    _agent("quote", "Quote Agent", "integration", "Quotes and sayings.", "placeholder", "safe", "llm_text_generation", "Connect this quote agent to a curated quote source before enabling live routing.", icon="QTE"),
    _agent("reminder", "Reminder Agent", "integration", "Persistent reminder storage.", "real", "safe", "json_store", "Connected to memory/reminders.json.", icon="RMD", stateful=True),
    _agent("password", "Password Agent", "integration", "Local password generation and checking.", "real", "safe", "local_security_policy", "Local password policy and entropy analysis.", icon="PWD"),
    _agent("file", "File Agent", "system", "File reading and analysis.", "hybrid", "private", "filesystem_read_plus_llm_summary", "Real file reads plus optional LLM summarization.", icon="FIL"),
    _agent("list_files", "File Listing Agent", "system", "Directory listing.", "real", "private", "filesystem_listing", "Local filesystem enumeration.", icon="LST"),
    _agent("screenshot", "Screenshot Agent", "system", "Desktop capture.", "real", "sensitive", "desktop_capture", "pyautogui-backed screenshot capture.", icon="SS"),
    _agent("learning", "Learning Agent", "memory", "Personalization patterns.", "hybrid", "private", "memory_learning", "Interaction learning over time.", icon="LRN", stateful=True),
    _agent("planner_agent", "Planner Agent", "autonomous", "Step-by-step planning.", "placeholder", "safe", "rule_plus_llm_planning", "Connect this planner to a verified execution graph before enabling live routing.", icon="PLN"),
    _agent("executor", "Executor", "autonomous", "Bounded step execution.", "hybrid", "sensitive", "step_dispatcher", "Dispatches bounded execution steps to helper agents.", icon="EXE"),
    _agent("tool_selector", "Tool Selector", "autonomous", "Tool choice for autonomous flows.", "placeholder", "safe", "rule_plus_llm_selection", "Connect this tool selector to verified autonomous execution before enabling live routing.", icon="TLS"),
    _agent("debug_agent", "Debug Agent", "autonomous", "Failure debugging in autonomous flows.", "placeholder", "safe", "llm_debugging", "Connect this debug agent to observable execution traces before enabling live routing.", icon="DBG"),
    _agent("cognitive", "Cognitive Core", "cognitive", "Reflective thinking pipeline.", "placeholder", "safe", "experimental_pipeline", "Connect reflective memory and audited self-review before enabling.", status="experimental", icon="COG"),
    _agent("planner_core", "Planner Core", "cognitive", "Experimental planning core.", "placeholder", "safe", "experimental_pipeline", "Connect to real task graphs and execution telemetry before enabling.", status="experimental", icon="CPL"),
    _agent("reasoning_core", "Reasoning Core", "cognitive", "Experimental reasoning core.", "placeholder", "safe", "experimental_pipeline", "Connect to verification checks before production claims.", status="experimental", icon="CRS"),
    _agent("memory_core", "Memory Core", "cognitive", "Experimental memory core.", "placeholder", "private", "experimental_pipeline", "Connect to durable memory stores and privacy controls before enabling.", status="experimental", icon="CME", stateful=True),
    _agent("evaluator_core", "Evaluator Core", "cognitive", "Experimental evaluator.", "placeholder", "safe", "experimental_pipeline", "Connect to execution traces and quality signals before enabling.", status="experimental", icon="CEV"),
    _agent("evolution_core", "Evolution Core", "cognitive", "Experimental self-improvement core.", "placeholder", "sensitive", "experimental_pipeline", "Connect to approved change management before activation.", status="experimental", icon="CEO"),
)


def _build_generated_descriptors() -> tuple[AgentDescriptor, ...]:
    existing_ids = {agent.id for agent in MANUAL_AGENT_REGISTRY}
    seen_ids = set(existing_ids)
    generated: List[AgentDescriptor] = []
    for blueprint in discover_generated_agent_blueprints():
        if blueprint.id in seen_ids:
            continue
        generated.append(
            _agent(
                blueprint.id,
                blueprint.name,
                blueprint.category,
                blueprint.description,
                blueprint.capability_mode,
                blueprint.trust_level,
                blueprint.backend,
                blueprint.integration_path,
                status=blueprint.status,
                icon=blueprint.icon,
                stateful=blueprint.stateful,
            )
        )
        seen_ids.add(blueprint.id)
    return tuple(generated)


AGENT_REGISTRY: tuple[AgentDescriptor, ...] = MANUAL_AGENT_REGISTRY + _build_generated_descriptors()


def list_agents(
    *,
    include_experimental: bool = True,
    include_placeholders: bool = True,
) -> List[Dict[str, Any]]:
    agents = []
    for agent in AGENT_REGISTRY:
        if not include_experimental and agent.status == "experimental":
            continue
        if not include_placeholders and agent.capability_mode == "placeholder":
            continue
        agents.append(agent.to_dict())
    return agents


def get_agent_map(
    *,
    include_experimental: bool = True,
    include_placeholders: bool = True,
) -> Dict[str, Dict[str, Any]]:
    return {
        agent.id: agent.to_dict()
        for agent in AGENT_REGISTRY
        if (include_experimental or agent.status != "experimental")
        and (include_placeholders or agent.capability_mode != "placeholder")
    }


def get_agent_descriptor(agent_id: str) -> Optional[AgentDescriptor]:
    normalized = str(agent_id or "").strip().lower()
    for agent in AGENT_REGISTRY:
        if agent.id == normalized:
            return agent
    return None


def get_agent_capability_mode(agent_id: str, *, default: str = "hybrid") -> str:
    normalized = str(agent_id or "").strip().lower()
    if normalized in RUNTIME_REAL_AGENT_METADATA:
        return "real"
    descriptor = get_agent_descriptor(agent_id)
    if descriptor is None:
        return default
    return descriptor.capability_mode


def is_chat_routable_agent(agent_id: str) -> bool:
    return get_agent_capability_mode(agent_id) in CHAT_ROUTABLE_CAPABILITY_MODES


def filter_chat_routable_agents(agent_ids: Iterable[str]) -> tuple[List[str], List[str]]:
    allowed: List[str] = []
    blocked: List[str] = []
    seen = set()
    for agent_id in agent_ids:
        normalized = str(agent_id or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if get_agent_capability_mode(normalized) == "placeholder":
            blocked.append(normalized)
            continue
        allowed.append(normalized)
    return allowed, blocked


def build_runtime_agent_cards(agent_ids: Iterable[str]) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    seen = set()
    for agent_id in agent_ids:
        normalized = str(agent_id or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        descriptor = get_agent_descriptor(normalized)
        if descriptor is None:
            runtime_override = RUNTIME_REAL_AGENT_METADATA.get(normalized)
            if runtime_override is not None:
                cards.append(
                    {
                        "id": normalized,
                        "name": runtime_override["name"],
                        "category": runtime_override["category"],
                        "description": runtime_override["description"],
                        "capability_mode": "real",
                        "trust_level": runtime_override["trust_level"],
                        "backend": runtime_override["backend"],
                        "integration_path": runtime_override["integration_path"],
                        "status": "live",
                        "icon": runtime_override["icon"],
                        "stateful": runtime_override["stateful"],
                        "ui_claim": UI_CLAIM_BY_MODE.get("real", "connected"),
                        "connected": True,
                        "experimental": False,
                        "CAPABILITY_MODE": "real",
                    }
                )
                seen.add(normalized)
                continue
            fallback_mode = "real" if normalized in {"time", "date"} else "hybrid"
            fallback_trust = "private" if normalized == "memory" else "safe"
            cards.append(
                {
                    "id": normalized,
                    "name": normalized.replace("_", " ").title(),
                    "category": "runtime",
                    "description": "Runtime-handled capability.",
                    "capability_mode": fallback_mode,
                    "trust_level": fallback_trust,
                    "backend": "runtime",
                    "integration_path": "Handled directly inside the shared runtime.",
                    "status": "live",
                    "icon": "RUN",
                    "stateful": normalized == "memory",
                    "ui_claim": UI_CLAIM_BY_MODE.get(fallback_mode, "planned"),
                    "connected": True,
                    "experimental": False,
                    "CAPABILITY_MODE": fallback_mode,
                }
            )
            seen.add(normalized)
            continue
        cards.append(descriptor.to_dict())
        seen.add(normalized)
    return cards


def get_agent_summary(
    *,
    include_experimental: bool = True,
    include_placeholders: bool = True,
) -> Dict[str, Any]:
    agents = list_agents(
        include_experimental=include_experimental,
        include_placeholders=include_placeholders,
    )
    summary = {
        "total": len(agents),
        "live": 0,
        "experimental": 0,
        "standby": 0,
        "connected": 0,
        "capability_modes": {mode: 0 for mode in CAPABILITY_LABELS},
        "trust_levels": {level: 0 for level in sorted(VALID_TRUST_LEVELS)},
        "categories": {},
    }

    for agent in agents:
        status = agent["status"]
        summary[status] = summary.get(status, 0) + 1
        summary["capability_modes"][agent["capability_mode"]] += 1
        summary["trust_levels"][agent["trust_level"]] += 1
        category = agent["category"]
        summary["categories"][category] = summary["categories"].get(category, 0) + 1
        if agent["capability_mode"] != "placeholder":
            summary["connected"] += 1

    summary["placeholders"] = summary["capability_modes"]["placeholder"]
    return summary


def validate_registry() -> List[str]:
    errors: List[str] = []
    seen_ids = set()
    for agent in AGENT_REGISTRY:
        if agent.id in seen_ids:
            errors.append(f"Duplicate agent id: {agent.id}")
        seen_ids.add(agent.id)
        if agent.capability_mode not in VALID_CAPABILITY_MODES:
            errors.append(f"{agent.id}: invalid capability mode")
        if agent.trust_level not in VALID_TRUST_LEVELS:
            errors.append(f"{agent.id}: invalid trust level")
        if agent.status not in VALID_STATUSES:
            errors.append(f"{agent.id}: invalid status")
        if not agent.integration_path.strip():
            errors.append(f"{agent.id}: missing integration path")
        if agent.capability_mode == "placeholder" and "connect" not in agent.integration_path.lower():
            errors.append(f"{agent.id}: placeholder agents need a future integration path")
    return errors
