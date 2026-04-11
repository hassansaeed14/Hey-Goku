import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from brain.command_splitter import split_commands
from brain.confidence_engine import evaluate_confidence
from brain.context_manager import update_context_from_command
from brain.decision_engine import (
    build_decision_summary,
    format_multi_response,
    should_add_low_confidence_note,
    should_fallback_to_general,
    should_plan,
    should_treat_as_multi_command,
    should_use_agent,
)
from brain.entity_parser import parse_entities
from brain.planner import summarize_execution_plan
from brain.reflection_engine import record_reflection
from brain.orchestrator import orchestrator as master_orchestrator
from brain.response_engine import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    build_messages,
    build_system_prompt,
    build_degraded_reply,
    clean_response,
    generate_response_payload,
    is_meaningful_text,
)
from brain.telemetry_engine import ProcessingTelemetry, set_last_telemetry
from brain.intent_engine import detect_intent_with_confidence
from brain.understanding_engine import clean_user_input

from config.settings import DEFAULT_REASONING_PROVIDER
from memory.knowledge_base import get_user_name, store_user_name
from memory.memory_controller import process_interaction_memory

from agents.autonomous.planner_agent import create_plan, parse_plan_to_steps
from agents.core.language_agent import detect_language, respond_in_language
from agents.core.reasoning_agent import compare, reason
from agents.core.self_improvement_agent import log_failure, log_agent_error, log_low_confidence
from agents.integration.currency_agent import convert_currency, get_crypto_price
from agents.integration.dictionary_agent import define_word, get_synonyms
from agents.integration.joke_agent import get_joke
from agents.integration.math_agent import solve_math
from agents.integration.news_agent import get_news
from agents.integration.quote_agent import get_quote
from agents.integration.reminder_agent import (
    add_reminder,
    complete_reminder,
    delete_reminder,
    get_reminders,
)
from agents.integration.translation_agent import translate
from agents.integration.weather_agent import get_weather
from agents.integration.web_search_agent import web_search
from agents.integration.youtube_agent import search_youtube_topic
from agents.memory.learning_agent import (
    build_context,
    get_personalized_greeting,
    get_user_insights,
    learn_from_interaction,
)
from agents.productivity.coding_agent import code_help
from agents.productivity.content_writer_agent import write_content
from agents.productivity.email_writer_agent import write_email
from agents.productivity.fitness_agent import get_workout_plan
from agents.productivity.grammar_agent import check_grammar
from agents.productivity.quiz_agent import generate_flashcards, generate_quiz
from agents.productivity.research_agent import research
from agents.productivity.study_agent import study
from agents.productivity.summarizer_agent import summarize_text, summarize_topic
from agents.productivity.task_agent import add_task, complete_task, delete_task, get_tasks, plan_tasks
from agents.system.file_agent import analyze_file, list_files
from agents.system.screenshot_agent import take_screenshot
from security.trust_engine import build_permission_response, get_trust_level
from agents.agent_fabric import match_generated_agent_request, run_generated_agent
from agents.registry import build_runtime_agent_cards


GREETING_INPUTS = {"hi", "hello", "hey", "hey aura", "hi aura", "hello aura"}

try:
    from memory.vector_memory import store_memory
except Exception:
    def store_memory(*args, **kwargs) -> None:
        return None


def _telemetry_excerpt(value: Any, limit: int = 220) -> str:
    if isinstance(value, dict):
        text = clean_response(str({key: value[key] for key in list(value)[:4]}))
    elif isinstance(value, list):
        text = clean_response(", ".join(str(item) for item in value[:4]))
    else:
        text = clean_response(str(value or ""))
    return text[:limit] if len(text) > limit else text


def _with_telemetry(
    payload: Dict[str, Any],
    telemetry: Optional[ProcessingTelemetry],
    *,
    publish: bool = True,
) -> Dict[str, Any]:
    if telemetry is None:
        return payload
    telemetry_payload = telemetry.get_telemetry()
    payload["telemetry"] = telemetry_payload
    if publish:
        set_last_telemetry(telemetry_payload)
    return payload


def _llm_response_with_provider(user_input: str, language: str) -> Dict[str, Any]:
    system_prompt = build_system_prompt(language)
    messages = build_messages(user_input, system_prompt)
    started = time.perf_counter()
    provider_response = generate_response_payload(
        messages,
        system_override=system_prompt,
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=DEFAULT_TEMPERATURE,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    if not provider_response.get("success"):
        attempts = provider_response.get("providers_tried") or []
        last_attempt = str(attempts[-1]).strip() if attempts else ""
        provider_name = last_attempt.split(":", 1)[0].strip() if ":" in last_attempt else "unavailable"
        return {
            "success": False,
            "text": provider_response.get("degraded_reply") or build_degraded_reply(user_input, attempts),
            "provider_name": provider_name,
            "model": provider_response.get("model") or "unknown",
            "tokens_used": None,
            "time_ms": elapsed_ms,
            "error": str(provider_response.get("error") or "No configured provider produced a response."),
            "providers_tried": attempts,
            "degraded": True,
        }

    raw_result = str(provider_response.get("content", "")).strip()
    cleaned = clean_response(raw_result)
    if not is_meaningful_text(cleaned):
        return {
            "success": False,
            "text": provider_response.get("degraded_reply") or build_degraded_reply(user_input, provider_response.get("providers_tried") or []),
            "provider_name": provider_response.get("provider") or "unknown",
            "model": provider_response.get("model") or "unknown",
            "tokens_used": provider_response.get("tokens_used"),
            "time_ms": elapsed_ms,
            "error": provider_response.get("error") or "Provider returned empty content.",
            "providers_tried": provider_response.get("providers_tried") or [],
            "degraded": True,
        }

    return {
        "success": True,
        "text": cleaned,
        "provider_name": provider_response.get("provider") or "unknown",
        "model": provider_response.get("model") or "unknown",
        "tokens_used": provider_response.get("tokens_used"),
        "time_ms": elapsed_ms,
        "providers_tried": provider_response.get("providers_tried") or [],
    }


def _max_trust_level(levels: List[str]) -> str:
    order = {"safe": 0, "private": 1, "sensitive": 2, "critical": 3}
    normalized = [str(level or "safe").strip().lower() for level in levels if level]
    if not normalized:
        return "safe"
    return max(normalized, key=lambda item: order.get(item, 0))


def extract_currency_request(command: str) -> tuple[float, str, str]:
    amount_match = re.search(r"(\d+(\.\d+)?)", command)
    currency_matches = re.findall(r"\b[A-Z]{3}\b", command.upper())

    amount = float(amount_match.group(1)) if amount_match else 1.0

    if len(currency_matches) >= 2:
        return amount, currency_matches[0], currency_matches[1]

    return amount, "USD", "PKR"


def extract_translation_target(command: str) -> str:
    command_lower = command.lower()

    language_map = {
        "urdu": "urdu",
        "english": "english",
        "arabic": "arabic",
        "french": "french",
        "spanish": "spanish",
        "hindi": "hindi",
        "punjabi": "punjabi",
    }

    for lang, target in language_map.items():
        if f"in {lang}" in command_lower or f"to {lang}" in command_lower:
            return target

    return "english"


def extract_numeric_id(command: str) -> Optional[int]:
    match = re.search(r"\b(\d+)\b", command)
    if not match:
        return None
    return int(match.group(1))


def contains_phrase(command_lower: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in command_lower for phrase in phrases)


TASK_READ_PHRASES = ("show tasks", "list tasks", "my tasks")
TASK_COMPLETE_PHRASES = ("complete task", "finish task", "done task")
TASK_DELETE_PHRASES = ("delete task", "remove task")
REMINDER_READ_PHRASES = ("show reminders", "list reminders", "my reminders")
REMINDER_COMPLETE_PHRASES = ("complete reminder", "done reminder")
REMINDER_DELETE_PHRASES = ("delete reminder", "remove reminder")


def normalize_agent_output(result: Any) -> str:
    if isinstance(result, dict):
        message = result.get("message")
        if message:
            return str(message).strip()
    if result is None:
        return ""
    return str(result).strip()


def store_and_learn(
    user_input: str,
    response: str,
    intent: str,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    metadata = {"type": "user_input", "intent": intent}
    if extra_metadata:
        metadata.update(extra_metadata)

    try:
        process_interaction_memory(
            user_input,
            response,
            intent,
            float(metadata.get("confidence", 1.0)),
        )
    except Exception:
        pass

    store_memory(user_input, metadata)
    learn_from_interaction(user_input, response, intent)


def route_quiz_command(command: str) -> str:
    if "flashcard" in command.lower():
        return generate_flashcards(command)
    return generate_quiz(command)


def handle_task_command(command: str) -> str:
    command_lower = command.lower()
    task_id = extract_numeric_id(command)

    if any(phrase in command_lower for phrase in ("show tasks", "list tasks", "my tasks")):
        return get_tasks()

    if task_id and any(phrase in command_lower for phrase in ("complete task", "finish task", "done task")):
        return complete_task(task_id)

    if task_id and any(phrase in command_lower for phrase in ("delete task", "remove task")):
        return delete_task(task_id)

    add_match = re.search(r"(?:add task|task)\s+(.+)$", command, flags=re.IGNORECASE)
    if add_match:
        return add_task(add_match.group(1).strip())

    return plan_tasks(command)


def handle_reminder_command(command: str) -> str:
    command_lower = command.lower()
    reminder_id = extract_numeric_id(command)

    if any(phrase in command_lower for phrase in ("show reminders", "list reminders", "my reminders")):
        return normalize_agent_output(get_reminders())

    if reminder_id and any(phrase in command_lower for phrase in ("complete reminder", "done reminder")):
        return normalize_agent_output(complete_reminder(reminder_id))

    if reminder_id and any(phrase in command_lower for phrase in ("delete reminder", "remove reminder")):
        return normalize_agent_output(delete_reminder(reminder_id))

    add_match = re.search(r"remind me to\s+(.+)$", command, flags=re.IGNORECASE)
    if add_match:
        return normalize_agent_output(add_reminder(add_match.group(1).strip()))

    return normalize_agent_output(get_reminders())


def resolve_permission_action(
    command: str,
    detected_intent: str,
    orchestration: Dict[str, Any],
) -> str:
    command_lower = command.lower()
    primary_agent = (orchestration.get("primary_agent") or detected_intent or "general").strip().lower()
    safe_aliases = {
        "code": "coding",
        "content": "general",
        "email": "general",
        "fitness": "general",
    }

    if primary_agent == "task":
        if contains_phrase(command_lower, TASK_READ_PHRASES):
            return "task_read"
        if extract_numeric_id(command) and contains_phrase(command_lower, TASK_COMPLETE_PHRASES):
            return "task_complete"
        if extract_numeric_id(command) and contains_phrase(command_lower, TASK_DELETE_PHRASES):
            return "task_delete"
        if re.search(r"(?:add task|task)\s+(.+)$", command, flags=re.IGNORECASE):
            return "task_add"
        return "task_plan"

    if primary_agent == "reminder":
        if contains_phrase(command_lower, REMINDER_READ_PHRASES):
            return "reminder_read"
        if extract_numeric_id(command) and contains_phrase(command_lower, REMINDER_COMPLETE_PHRASES):
            return "reminder_complete"
        if extract_numeric_id(command) and contains_phrase(command_lower, REMINDER_DELETE_PHRASES):
            return "reminder_delete"
        if re.search(r"remind me to\s+(.+)$", command, flags=re.IGNORECASE):
            return "reminder_add"
        return "reminder_read"

    if primary_agent == "file":
        return "file_read"

    if primary_agent == "list_files":
        return "file_list"

    if primary_agent in {"insights", "memory"}:
        return "memory_read" if primary_agent == "memory" else "insights"

    return safe_aliases.get(primary_agent, primary_agent)


def build_agent_capability_cards(
    used_agents: List[str],
    detected_intent: str,
    orchestration: Dict[str, Any],
) -> List[Dict[str, Any]]:
    agent_ids = [agent_name for agent_name in used_agents if agent_name]
    if not agent_ids:
        primary_agent = orchestration.get("primary_agent") or detected_intent
        if primary_agent:
            agent_ids = [str(primary_agent)]
    return build_runtime_agent_cards(agent_ids)


AGENT_ROUTER: Dict[str, Callable[[str], str]] = {
    "weather": lambda cmd: normalize_agent_output(get_weather(cmd)),
    "news": lambda cmd: normalize_agent_output(get_news(cmd)),
    "math": lambda cmd: normalize_agent_output(solve_math(cmd)),
    "fitness": lambda cmd: normalize_agent_output(get_workout_plan(cmd)),
    "translation": lambda cmd: normalize_agent_output(translate(cmd, extract_translation_target(cmd))),
    "research": lambda cmd: normalize_agent_output(research(cmd)),
    "study": lambda cmd: normalize_agent_output(study(cmd)),
    "code": lambda cmd: normalize_agent_output(code_help(cmd)),
    "content": lambda cmd: normalize_agent_output(write_content(cmd, "blog")),
    "email": lambda cmd: normalize_agent_output(write_email(cmd, cmd)),
    "summarize": lambda cmd: normalize_agent_output(summarize_topic(cmd)),
    "grammar": lambda cmd: normalize_agent_output(check_grammar(cmd)),
    "quiz": route_quiz_command,
    "dictionary": lambda cmd: normalize_agent_output(define_word(cmd)),
    "synonyms": lambda cmd: normalize_agent_output(get_synonyms(cmd)),
    "web_search": lambda cmd: normalize_agent_output(web_search(cmd)),
    "youtube": lambda cmd: normalize_agent_output(search_youtube_topic(cmd)),
    "currency": lambda cmd: normalize_agent_output(convert_currency(*extract_currency_request(cmd))),
    "crypto": lambda cmd: normalize_agent_output(get_crypto_price("bitcoin")),
    "joke": lambda cmd: normalize_agent_output(get_joke()),
    "quote": lambda cmd: normalize_agent_output(get_quote()),
    "file": lambda cmd: normalize_agent_output(analyze_file(cmd)),
    "list_files": lambda cmd: normalize_agent_output(list_files(".")),
    "screenshot": lambda cmd: normalize_agent_output(take_screenshot()),
    "reasoning": lambda cmd: normalize_agent_output(reason(cmd)),
    "compare": lambda cmd: normalize_agent_output(compare(cmd)),
    "task": handle_task_command,
    "reminder": handle_reminder_command,
}


def research_summary_workflow(command: str) -> Dict[str, str]:
    research_result = normalize_agent_output(research(command))
    return {
        "research": research_result,
        "summarize": normalize_agent_output(summarize_text(research_result, summary_type="brief")),
    }


def email_grammar_workflow(command: str) -> Dict[str, str]:
    email_result = normalize_agent_output(write_email(command, command))
    return {
        "email": email_result,
        "grammar": normalize_agent_output(check_grammar(email_result)),
    }


WORKFLOW_HANDLERS: Dict[tuple[str, ...], Callable[[str], Dict[str, str]]] = {
    ("research", "summarize"): research_summary_workflow,
    ("email", "grammar"): email_grammar_workflow,
}


def handle_personal_memory(command: str) -> Optional[tuple[str, str]]:
    cmd = command.lower().strip()

    normalized = re.sub(r"^(hi|hey|hello)\s+", "", cmd).strip()
    normalized = re.sub(r"^(no\s+i\s+mean\s+|i\s+mean\s+)", "", normalized).strip()

    name_match = re.search(r"\bmy name is\s+([a-zA-Z ]{1,40})$", normalized)
    if name_match:
        name = name_match.group(1).strip().title()
        store_user_name(name)
        return "memory", f"Nice to meet you {name}!"

    if "what is my name" in normalized:
        name = get_user_name()
        return "memory", f"Your name is {name}." if name else "I don't know your name yet."

    return None


def handle_special_intents(intent: str) -> Optional[str]:
    if intent == "time":
        return f"The current time is {datetime.now().strftime('%I:%M %p')}."

    if intent == "date":
        return f"Today's date is {datetime.now().strftime('%A, %d %B %Y')}."

    if intent == "identity":
        return (
            "I am AURA, your Autonomous Universal Responsive Assistant. "
            "I help with research, coding, writing, planning, and agent-based task routing."
        )

    if intent == "insights":
        return get_user_insights()

    return None


def build_enhanced_input(raw_command: str, confidence: float) -> str:
    try:
        enhanced_input = build_context(raw_command)
    except Exception:
        enhanced_input = raw_command

    if should_add_low_confidence_note(confidence):
        enhanced_input += (
            "\n\nIntent confidence is low. "
            "Respond carefully, infer user meaning safely, and handle imperfect wording gracefully."
        )

    return enhanced_input


def run_agent(agent_name: str, raw_command: str) -> str:
    try:
        return normalize_agent_output(AGENT_ROUTER[agent_name](raw_command))
    except Exception as error:
        log_agent_error(agent_name, str(error))
        return f"{agent_name} agent failed: {str(error)}"


def should_use_orchestrated_agents(
    detected_intent: str,
    confidence: float,
    orchestration: Dict[str, Any],
) -> bool:
    primary_agent = orchestration.get("primary_agent", "general")
    selection_source = orchestration.get("primary_selection_source", "intent")

    if primary_agent not in AGENT_ROUTER:
        return False

    if selection_source == "keyword_scoring":
        return bool(orchestration.get("requires_multiple")) or orchestration.get("top_score", 0) >= 2

    return should_use_agent(primary_agent, confidence, AGENT_ROUTER) or should_use_agent(
        detected_intent,
        confidence,
        AGENT_ROUTER,
    )


def execute_orchestrated_agents(
    raw_command: str,
    detected_intent: str,
    confidence: float,
    orchestration: Dict[str, Any],
) -> tuple[str, List[str], str]:
    if not should_use_orchestrated_agents(detected_intent, confidence, orchestration):
        return "", [], "fallback_llm"

    execution_order = []
    for agent_name in orchestration.get("execution_order", []):
        if agent_name in AGENT_ROUTER and agent_name not in execution_order:
            execution_order.append(agent_name)

    if not execution_order:
        primary_agent = orchestration.get("primary_agent", "general")
        if primary_agent in AGENT_ROUTER:
            execution_order = [primary_agent]

    if not execution_order:
        return "", [], "fallback_llm"

    workflow_key = tuple(execution_order[:2])
    if len(execution_order) > 1 and workflow_key in WORKFLOW_HANDLERS:
        responses = WORKFLOW_HANDLERS[workflow_key](raw_command)
    else:
        responses = {agent_name: run_agent(agent_name, raw_command) for agent_name in execution_order}

    synthesis = master_orchestrator.synthesize_responses(raw_command, responses)
    mode = "multi_agent" if len(responses) > 1 else "single_agent"
    return synthesis.get("response", ""), list(responses.keys()), mode


def build_plan_steps(raw_command: str, intent: str, confidence: float, orchestration: Dict[str, Any]) -> List[str]:
    deterministic_plan = summarize_execution_plan(raw_command)
    if deterministic_plan:
        return deterministic_plan[:8]

    if should_plan(intent, confidence):
        try:
            plan_text = create_plan(raw_command)
            if isinstance(plan_text, str):
                parsed = parse_plan_to_steps(plan_text)
                if parsed:
                    return parsed[:8]
            if isinstance(plan_text, list):
                parsed = [str(step).strip() for step in plan_text if str(step).strip()]
                if parsed:
                    return parsed[:8]
        except Exception as error:
            log_failure(raw_command, f"Planning failed: {str(error)}")

    execution_order = [
        agent_name.replace("_", " ").title()
        for agent_name in orchestration.get("execution_order", [])
        if agent_name and agent_name != "general"
    ]

    if not execution_order:
        return []

    steps = [f"Route request to {execution_order[0]}"]
    steps.extend(f"Support with {agent_name}" for agent_name in execution_order[1:])
    steps.append("Synthesize and deliver the final response")
    return steps


def build_result(
    *,
    raw_command: str,
    detected_intent: str,
    confidence: float,
    response: str,
    language: str,
    orchestration: Dict[str, Any],
    used_agents: List[str],
    execution_mode: str,
    plan_steps: Optional[List[str]] = None,
    permission_action: Optional[str] = None,
    permission: Optional[Dict[str, Any]] = None,
    provider_name: Optional[str] = None,
    provider_model: Optional[str] = None,
    providers_tried: Optional[List[str]] = None,
    telemetry: Optional[ProcessingTelemetry] = None,
    publish_telemetry: bool = True,
) -> Dict[str, Any]:
    translated_response = respond_in_language(response, language)
    final_intent = detected_intent if detected_intent != "general" else orchestration.get("primary_agent", "general")
    agent_capabilities = build_agent_capability_cards(used_agents, final_intent, orchestration)
    confidence_detail = evaluate_confidence(raw_command).to_dict()

    store_and_learn(
        raw_command,
        translated_response,
        final_intent,
        extra_metadata={
            "confidence": round(confidence, 4),
            "used_agents": used_agents,
            "execution_mode": execution_mode,
            "plan_steps": plan_steps or [],
        },
    )
    try:
        update_context_from_command(
            raw_command,
            agent=used_agents[0] if used_agents else final_intent,
        )
        record_reflection(
            requested_action=detected_intent,
            actual_action=final_intent,
            success=True,
            blocked_by_permission=False,
            retry_possible=False,
            learning_signal="successful_runtime_path",
        )
    except Exception:
        pass

    return _with_telemetry({
        "intent": final_intent,
        "detected_intent": detected_intent,
        "confidence": confidence,
        "response": translated_response,
        "plan": plan_steps or [],
        "used_agents": used_agents,
        "agent_capabilities": agent_capabilities,
        "execution_mode": execution_mode,
        "decision": build_decision_summary(detected_intent, confidence, AGENT_ROUTER),
        "orchestration": orchestration,
        "language": language,
        "confidence_detail": confidence_detail,
        "permission_action": permission_action,
        "permission": permission,
        "provider": provider_name,
        "model": provider_model,
        "providers_tried": list(providers_tried or []),
        "degraded": execution_mode == "degraded_assistant",
    }, telemetry, publish=publish_telemetry)


def process_single_command_detailed(
    command: str,
    telemetry: Optional[ProcessingTelemetry] = None,
    *,
    publish_telemetry: bool = True,
) -> Dict[str, Any]:
    active_telemetry = telemetry or ProcessingTelemetry()
    raw_input = str(command or "")
    understanding_started = time.perf_counter()
    raw_command = clean_user_input(command)
    entities = parse_entities(raw_command).to_dict()
    active_telemetry.record_understanding(
        raw_input=raw_input,
        normalized=raw_command,
        entities=entities,
        time_ms=(time.perf_counter() - understanding_started) * 1000,
    )
    command_lower = raw_command.lower()

    if not raw_command:
        active_telemetry.record_intent("general", 0.0, [], 0.0)
        active_telemetry.record_routing("general", "No message was provided.", "safe", 0.0)
        active_telemetry.record_execution("general", "Please type something.", False, 0.0)
        return _with_telemetry({
            "intent": "general",
            "detected_intent": "general",
            "confidence": 0.0,
            "response": "Please type something.",
            "plan": [],
            "used_agents": [],
            "agent_capabilities": build_runtime_agent_cards(["general"]),
            "execution_mode": "empty",
            "decision": build_decision_summary("general", 0.0, AGENT_ROUTER),
            "orchestration": master_orchestrator.analyze_task("", intent="general"),
            "language": "english",
            "permission_action": "general",
            "permission": build_permission_response("general"),
        }, active_telemetry, publish=publish_telemetry)

    if command_lower in GREETING_INPUTS:
        response = get_personalized_greeting()
        active_telemetry.record_intent("greeting", 1.0, [], 0.0)
        active_telemetry.record_routing("general", "Greeting shortcut matched a known greeting input.", "safe", 0.0)
        active_telemetry.record_execution("general", response, True, 0.0)
        store_and_learn(raw_command, response, "greeting")
        return _with_telemetry({
            "intent": "greeting",
            "detected_intent": "greeting",
            "confidence": 1.0,
            "response": response,
            "plan": [],
            "used_agents": ["general"],
            "agent_capabilities": build_runtime_agent_cards(["general"]),
            "execution_mode": "greeting",
            "decision": build_decision_summary("greeting", 1.0, AGENT_ROUTER),
            "orchestration": master_orchestrator.analyze_task(raw_command, intent="general"),
            "language": "english",
            "permission_action": "general",
            "permission": build_permission_response("general"),
        }, active_telemetry, publish=publish_telemetry)

    memory_response = handle_personal_memory(raw_command)
    if memory_response:
        active_telemetry.record_intent(memory_response[0], 1.0, [], 0.0)
        active_telemetry.record_routing("memory", "Personal memory handler matched the request.", "safe", 0.0)
        active_telemetry.record_execution("memory", memory_response[1], True, 0.0)
        store_and_learn(raw_command, memory_response[1], memory_response[0])
        return _with_telemetry({
            "intent": memory_response[0],
            "detected_intent": memory_response[0],
            "confidence": 1.0,
            "response": memory_response[1],
            "plan": [],
            "used_agents": ["memory"],
            "agent_capabilities": build_runtime_agent_cards(["memory"]),
            "execution_mode": "memory",
            "decision": build_decision_summary("general", 1.0, AGENT_ROUTER),
            "orchestration": master_orchestrator.analyze_task(raw_command, intent="general"),
            "language": "english",
            "permission_action": "memory_read",
            "permission": build_permission_response("memory_read", confirmed=True),
        }, active_telemetry, publish=publish_telemetry)

    language = detect_language(raw_command)

    intent_started = time.perf_counter()
    detected_intent, confidence = detect_intent_with_confidence(raw_command)
    confidence_detail = evaluate_confidence(raw_command).to_dict()
    alternatives = [
        {
            "intent": item.get("intent"),
            "score": item.get("score"),
            "matched_rules": item.get("matched_rules", []),
        }
        for item in (confidence_detail.get("candidates") or [])[:3]
    ]
    active_telemetry.record_intent(
        primary_intent=detected_intent,
        confidence=confidence,
        alternatives=alternatives,
        time_ms=(time.perf_counter() - intent_started) * 1000,
    )

    routing_started = time.perf_counter()
    orchestration = master_orchestrator.analyze_task(raw_command, intent=detected_intent)
    permission_action = resolve_permission_action(raw_command, detected_intent, orchestration)
    permission = build_permission_response(permission_action)
    selected_agent = orchestration.get("primary_agent") or detected_intent or "general"
    routing_reason = (
        orchestration.get("reason")
        or orchestration.get("routing_reason")
        or f"Detected intent '{detected_intent}' and selected '{selected_agent}'."
    )
    trust_level = get_trust_level(permission_action).value if permission_action else "safe"
    active_telemetry.record_routing(
        agent_selected=selected_agent,
        reason=str(routing_reason),
        trust_level=trust_level,
        time_ms=(time.perf_counter() - routing_started) * 1000,
    )

    if not permission["success"]:
        active_telemetry.record_execution(
            selected_agent,
            permission["permission"]["reason"],
            False,
            0.0,
        )
        try:
            update_context_from_command(raw_command, agent=selected_agent)
            record_reflection(
                requested_action=detected_intent,
                actual_action="permission_blocked",
                success=False,
                blocked_by_permission=True,
                retry_possible=True,
                learning_signal="permission_enforcement_blocked_execution",
            )
        except Exception:
            pass
        return _with_telemetry({
            "intent": "permission",
            "detected_intent": detected_intent,
            "confidence": confidence,
            "response": permission["permission"]["reason"],
            "plan": [],
            "used_agents": [selected_agent] if selected_agent else [],
            "agent_capabilities": build_agent_capability_cards(
                [selected_agent],
                detected_intent,
                orchestration,
            ),
            "execution_mode": "permission_blocked",
            "decision": build_decision_summary(detected_intent, confidence, AGENT_ROUTER),
            "orchestration": orchestration,
            "language": language,
            "confidence_detail": confidence_detail,
            "permission_action": permission_action,
            "permission": permission,
        }, active_telemetry, publish=publish_telemetry)

    if confidence < 0.40:
        log_low_confidence(raw_command, confidence)

    special_response = handle_special_intents(detected_intent)
    if special_response:
        active_telemetry.record_execution(detected_intent, special_response, True, 0.0)
        return build_result(
            raw_command=raw_command,
            detected_intent=detected_intent,
            confidence=confidence,
            response=special_response,
            language=language,
            orchestration=orchestration,
            used_agents=[detected_intent],
            execution_mode="special_intent",
            plan_steps=[],
            permission_action=permission_action,
            permission=permission,
            telemetry=active_telemetry,
            publish_telemetry=publish_telemetry,
        )

    resolved_intent = detected_intent
    if should_fallback_to_general(confidence):
        resolved_intent = "general"

    response = ""
    used_agents: List[str] = []
    execution_mode = "fallback_llm"
    provider_name: Optional[str] = None
    provider_model: Optional[str] = None
    providers_tried: List[str] = []
    execution_started = time.perf_counter()

    try:
        orchestrated_response, orchestrated_agents, execution_mode = execute_orchestrated_agents(
            raw_command,
            detected_intent,
            confidence,
            orchestration,
        )

        if orchestrated_response:
            response = orchestrated_response
            used_agents = orchestrated_agents
        elif should_use_agent(resolved_intent, confidence, AGENT_ROUTER):
            response = run_agent(resolved_intent, raw_command)
            used_agents = [resolved_intent]
            execution_mode = "single_agent"
        else:
            generated_match = match_generated_agent_request(raw_command, exclude_ids=AGENT_ROUTER.keys())
            if generated_match:
                generated_result = run_generated_agent(generated_match.id, raw_command)
                response = normalize_agent_output(generated_result)
                used_agents = [generated_match.id]
                execution_mode = "generated_agent"
            else:
                enhanced_input = build_enhanced_input(raw_command, confidence)
                provider_result = _llm_response_with_provider(enhanced_input, language)
                if provider_result.get("success"):
                    response = str(provider_result.get("text") or "")
                    provider_name = str(provider_result.get("provider_name") or "").strip() or None
                    provider_model = str(provider_result.get("model") or "").strip() or None
                    providers_tried = list(provider_result.get("providers_tried") or [])
                    active_telemetry.record_provider(
                        provider_result.get("provider_name") or "unknown",
                        provider_result.get("model") or "unknown",
                        provider_result.get("tokens_used"),
                        provider_result.get("time_ms") or 0.0,
                    )
                else:
                    response = str(provider_result.get("text") or "").strip()
                    providers_tried = list(provider_result.get("providers_tried") or [])
                    execution_mode = "degraded_assistant"
                    active_telemetry.record_provider(
                        provider_result.get("provider_name") or "unavailable",
                        provider_result.get("model") or "unknown",
                        provider_result.get("tokens_used"),
                        provider_result.get("time_ms") or 0.0,
                        success=False,
                        error=provider_result.get("error"),
                    )
                    log_failure(raw_command, str(provider_result.get("error") or "Provider response failed"))
        normalized_response = clean_response(response).lower()
        success = bool(normalized_response) and execution_mode != "degraded_assistant" and "i ran into a problem" not in normalized_response
    except Exception as error:
        execution_time_ms = (time.perf_counter() - execution_started) * 1000
        active_telemetry.record_execution(
            used_agents[0] if used_agents else (orchestration.get("primary_agent") or resolved_intent or "general"),
            str(error),
            False,
            execution_time_ms,
        )
        raise

    execution_time_ms = (time.perf_counter() - execution_started) * 1000
    active_telemetry.record_execution(
        used_agents[0] if used_agents else (orchestration.get("primary_agent") or resolved_intent or "general"),
        _telemetry_excerpt(response),
        success,
        execution_time_ms,
    )

    plan_steps = build_plan_steps(raw_command, resolved_intent, confidence, orchestration)

    return build_result(
        raw_command=raw_command,
        detected_intent=resolved_intent,
        confidence=confidence,
        response=response,
        language=language,
        orchestration=orchestration,
        used_agents=used_agents,
        execution_mode=execution_mode,
        plan_steps=plan_steps,
        permission_action=permission_action,
        permission=permission,
        provider_name=provider_name,
        provider_model=provider_model,
        providers_tried=providers_tried,
        telemetry=active_telemetry,
        publish_telemetry=publish_telemetry,
    )


def process_single_command(command: str) -> tuple[str, str]:
    result = process_single_command_detailed(command)
    return result["intent"], result["response"]


def process_command_detailed(command: str) -> Dict[str, Any]:
    raw_input = str(command or "")
    raw_command = clean_user_input(command)

    if not raw_command:
        return process_single_command_detailed(raw_command)

    sub_commands = split_commands(raw_command)

    if not should_treat_as_multi_command(sub_commands):
        return process_single_command_detailed(raw_command)

    aggregate_telemetry = ProcessingTelemetry()
    understanding_started = time.perf_counter()
    aggregate_telemetry.record_understanding(
        raw_input=raw_input,
        normalized=raw_command,
        entities=parse_entities(raw_command).to_dict(),
        time_ms=(time.perf_counter() - understanding_started) * 1000,
    )

    results = [
        process_single_command_detailed(sub_command, publish_telemetry=False)
        for sub_command in sub_commands
    ]
    responses = [item["response"] for item in results]

    used_agents: List[str] = []
    for item in results:
        for agent_name in item.get("used_agents", []):
            if agent_name not in used_agents:
                used_agents.append(agent_name)

    plan_steps = []
    for index, item in enumerate(results, start=1):
        routed_agents = ", ".join(item.get("used_agents") or [item.get("intent", "general")])
        plan_steps.append(f"Command {index}: handle with {routed_agents}")

    blocked_permissions = [
        {
            "command": sub_command,
            "permission_action": item.get("permission_action"),
            "permission": item.get("permission"),
        }
        for sub_command, item in zip(sub_commands, results)
        if not bool(item.get("permission", {}).get("success", False))
    ]

    aggregated_permission = {
        "success": not blocked_permissions,
        "status": "aggregated_blocked" if blocked_permissions else "aggregated",
        "mode": "real",
        "blocked_commands": blocked_permissions,
    }
    intent_alternatives = []
    routing_levels = []
    execution_success = True
    execution_time_ms = 0.0
    last_provider_stage: Optional[Dict[str, Any]] = None

    for sub_command, item in zip(sub_commands, results):
        telemetry = item.get("telemetry") or {}
        stages = telemetry.get("stages") or {}
        intent_stage = stages.get("intent") or {}
        routing_stage = stages.get("routing") or {}
        execution_stage = stages.get("execution") or {}
        provider_stage = stages.get("provider") or {}

        if intent_stage:
            intent_alternatives.append(
                {
                    "intent": intent_stage.get("primary_intent") or item.get("detected_intent"),
                    "score": intent_stage.get("confidence"),
                    "matched_rules": [],
                    "command": sub_command,
                }
            )
        if routing_stage.get("trust_level"):
            routing_levels.append(routing_stage.get("trust_level"))
        if execution_stage.get("status") == "failed":
            execution_success = False
        execution_time_ms += float(execution_stage.get("time_ms") or 0.0)
        if provider_stage.get("status") and provider_stage.get("status") != "idle":
            last_provider_stage = provider_stage

    aggregate_telemetry.record_intent(
        primary_intent="multi_command",
        confidence=max((item.get("confidence", 0.0) for item in results), default=0.0),
        alternatives=intent_alternatives[:3],
        time_ms=sum(
            float(((item.get("telemetry") or {}).get("stages", {}).get("intent", {}) or {}).get("time_ms") or 0.0)
            for item in results
        ),
    )
    aggregate_telemetry.record_routing(
        agent_selected=", ".join(used_agents) if used_agents else "multi_command",
        reason=f"Split the request into {len(sub_commands)} actionable commands.",
        trust_level=_max_trust_level(routing_levels),
        time_ms=sum(
            float(((item.get("telemetry") or {}).get("stages", {}).get("routing", {}) or {}).get("time_ms") or 0.0)
            for item in results
        ),
    )
    aggregate_telemetry.record_execution(
        "multi_command",
        f"Processed {len(results)} commands.",
        execution_success,
        execution_time_ms,
    )
    if last_provider_stage:
        aggregate_telemetry.record_provider(
            last_provider_stage.get("provider_name") or "unknown",
            last_provider_stage.get("model") or "unknown",
            last_provider_stage.get("tokens_used"),
            float(last_provider_stage.get("time_ms") or 0.0),
            success=last_provider_stage.get("status") != "failed",
            error=last_provider_stage.get("error"),
        )

    return _with_telemetry({
        "intent": "multi_command",
        "detected_intent": "multi_command",
        "confidence": max((item.get("confidence", 0.0) for item in results), default=0.0),
        "response": format_multi_response(responses),
        "plan": plan_steps,
        "used_agents": used_agents,
        "agent_capabilities": build_runtime_agent_cards(used_agents),
        "execution_mode": "multi_command",
        "decision": {
            "multi_command": True,
            "command_count": len(results),
        },
        "orchestration": {
            "primary_agent": "multi_command",
            "execution_order": used_agents,
            "requires_multiple": True,
            "mode": "real",
        },
        "language": detect_language(raw_command),
        "permission_action": "multi_command",
        "permission": aggregated_permission,
    }, aggregate_telemetry, publish=True)


def process_command(command: str) -> tuple[str, str]:
    result = process_command_detailed(command)
    return result["intent"], result["response"]
