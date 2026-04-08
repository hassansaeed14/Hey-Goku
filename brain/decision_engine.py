def should_fallback_to_general(confidence: float) -> bool:
    return confidence < 0.25


def should_use_agent(intent: str, confidence: float, agent_router: dict) -> bool:
    return intent in agent_router and confidence >= 0.25


def should_plan(intent: str, confidence: float) -> bool:
    return intent in {"research", "study", "task"} and confidence >= 0.40


def should_add_low_confidence_note(confidence: float) -> bool:
    return confidence < 0.40


def should_treat_as_multi_command(parts: list) -> bool:
    return len(parts) > 1


def format_multi_response(results: list) -> str:
    if not results:
        return "I couldn't understand the request clearly."

    if len(results) == 1:
        return results[0]

    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"Response {i}:\n{result}")

    return "\n\n".join(formatted)