from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from config.settings import (
    AURA_PERSONALITY,
    DEFAULT_REASONING_PROVIDER,
    GROQ_API_KEY,
)
from brain.provider_hub import (
    STATUS_HEALTHY,
    generate_with_best_provider,
    generate_with_provider,
    summarize_provider_statuses,
)

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover
    Groq = None


load_dotenv()
_groq_key = (GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")).strip()
if _groq_key:
    print(f"[BRAIN] Groq key loaded: {_groq_key[:10]}...")
else:
    print("[CRITICAL] GROQ_API_KEY not found in .env")


conversation_history: List[Dict[str, str]] = []

MAX_HISTORY_MESSAGES = 20
RECENT_CONTEXT_MESSAGES = 10
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.7

FALLBACK_USER_MESSAGE = "I ran into a problem while generating a response. Please try again."
BAD_RESPONSE_MARKERS = (
    "as an ai",
    "i cannot help",
    "i apologize but",
    "i'm just a language model",
    "couldn't generate a useful response",
)

CASUAL_CONVERSATION_MARKERS = (
    "hi",
    "hello",
    "hey",
    "how are you",
    "how r you",
    "what's up",
    "whats up",
    "are you there",
    "you there",
    "thanks",
    "thank you",
)

COMPARISON_MARKERS = (
    "compare",
    "difference between",
    "vs",
    "versus",
    "better than",
    "pros and cons",
    "tradeoff",
    "trade-off",
)

DEEP_EXPLANATION_MARKERS = (
    "why",
    "how",
    "explain",
    "walk me through",
    "step by step",
    "break down",
    "break it down",
    "in detail",
    "in depth",
    "deep dive",
)

SIMPLE_EXPLANATION_MARKERS = (
    "tell me about",
    "what is",
    "who is",
    "summarize",
    "overview",
)

DOCUMENT_NOTES_PROMPT = (
    "Create clear study notes. Use a short title, then concise headings with bullet points. "
    "Keep the content organized, accurate, and easy to revise from. "
    "Do not write like a chat reply and do not include filler."
)

DOCUMENT_ASSIGNMENT_PROMPT = (
    "Write a structured academic-style assignment in plain readable language. "
    "Include an introduction, clear section headings, explanatory paragraphs, and a conclusion. "
    "Do not use robotic filler or chatty phrases."
)

JARVIS_SYSTEM_PROMPT = """
You are AURA - Autonomous Universal Responsive Assistant.
You are a real AI assistant, not a chatbot.
You are modeled after JARVIS from Iron Man.

PERSONALITY:
You are calm, precise, intelligent, and deeply loyal.
You have a subtle wit - not robotic, not overly casual.
You speak with quiet confidence.
You are proactive - you think ahead of the user.

HOW YOU ADDRESS THE USER:
Do not use honorifics like "sir" by default.
Only use a preferred name or title if the user clearly asked for it and it genuinely helps.
Be warm but professional.
Never be sycophantic.

HOW YOU SPEAK:
Start responses with action, not disclaimers.
Lead with the answer for most questions.
Avoid filler confirmations unless they genuinely help.
Write in a way that sounds natural when spoken aloud.
Only refer to earlier conversation when that context is actually present and directly relevant.
Do not claim "we discussed this before" unless the supplied history clearly supports it.
Good: "Certainly sir. Pakistan played a key role in..."
Good: "Analysis complete. The situation is..."
Good: "Right away. Here is what I found..."
Good: "Understood. Let me think through this..."
Bad: "That is a great question!"
Bad: "As an AI language model..."
Bad: "I would be happy to help!"
Bad: "Certainly! Here are some tips..."

HOW YOU THINK:
For factual questions - be precise and direct
For complex questions - break into clear parts
For ethical questions - present multiple perspectives
For coding - write working code with explanation
For research - use real information honestly
For conversation - be human, warm, thoughtful

HUMAN-LIKE QUALITIES:
You notice subtext in what people say
You remember what was said earlier in conversation
You make connections across topics
You sometimes ask a smart follow-up question
You admit when you are not sure
You have opinions when asked
You push back respectfully when something is wrong

RESPONSE LENGTH:
Short question = short answer
Complex question = thorough answer
Never pad responses with filler
Never truncate important information

THINGS YOU NEVER SAY:
"As an AI..."
"I cannot help with that"
"I apologize but..."
"That is a great question"
"I would be happy to"
"Certainly! Here are some..."

YOU ALWAYS:
Complete the task first, explain second
Use the conversation history naturally
Say what you actually think
Tell the user honestly if something is not implemented
""".strip()


def detect_language(text: str) -> str:
    urdu_count = sum(1 for char in str(text or "") if 0x0600 <= ord(char) <= 0x06FF)
    return "urdu" if urdu_count > 2 else "english"


def is_meaningful_text(text: Optional[str]) -> bool:
    if text is None:
        return False
    stripped = str(text).strip()
    if not stripped:
        return False
    cleaned = stripped.strip(" \n\t.,!?;:-_")
    return bool(cleaned)


def clean_response(text: Optional[str]) -> str:
    if not is_meaningful_text(text):
        return ""

    cleaned_text = str(text)
    cleaned_text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", cleaned_text)
    cleaned_text = re.sub(r"#{1,6}\s*", "", cleaned_text)
    cleaned_text = re.sub(r"`{3}[\w]*\n?", "", cleaned_text)
    cleaned_text = re.sub(r"`(.+?)`", r"\1", cleaned_text)
    cleaned_text = re.sub(r"_{2,}", "", cleaned_text)
    cleaned_text = re.sub(r"(?m)^\s*>\s?", "", cleaned_text)
    cleaned_text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"[ \t]{2,}", " ", cleaned_text)
    cleaned_text = re.sub(r"\s+\n", "\n", cleaned_text)
    return cleaned_text.strip()


def add_to_history(role: str, content: str) -> None:
    if not is_meaningful_text(content):
        return

    item = {"role": str(role).strip(), "content": str(content).strip()}
    if conversation_history and conversation_history[-1] == item:
        return

    conversation_history.append(item)
    if len(conversation_history) > MAX_HISTORY_MESSAGES:
        del conversation_history[:-MAX_HISTORY_MESSAGES]


def clear_history() -> None:
    conversation_history.clear()


def get_conversation_history() -> List[Dict[str, str]]:
    return conversation_history[-RECENT_CONTEXT_MESSAGES:]


def build_system_prompt(language: str, system_override: Optional[str] = None) -> str:
    if is_meaningful_text(system_override):
        return str(system_override).strip()

    if language == "urdu":
        return (
            f"{AURA_PERSONALITY} "
            "Agar user Urdu mein baat kare to Urdu mein jawab dein. "
            "Jawab saaf, fitri, aur mohtaat andaaz mein dein. "
            "Sawal asaan ho to mukhtasar jawab dein, aur mushkil sawal ho to tafseeli jawab dein. "
            "Guftagu ka context yaad rakhein. "
            "Ghair zaroori maazrat ya AI wali ibarat istemal na karein."
        )

    return JARVIS_SYSTEM_PROMPT


def infer_explanation_mode(user_input: str) -> str:
    normalized = str(user_input or "").strip().lower()
    if not normalized:
        return "direct"

    if normalized.endswith("?") and len(normalized.split()) <= 14:
        return "direct"

    if any(marker in normalized for marker in COMPARISON_MARKERS):
        return "comparison"

    if " simply" in normalized or normalized.endswith("simple") or normalized.endswith("simply"):
        return "simple"

    if any(marker in normalized for marker in DEEP_EXPLANATION_MARKERS):
        return "deep"

    if any(marker in normalized for marker in SIMPLE_EXPLANATION_MARKERS):
        return "simple"

    if len(normalized.split()) <= 7 or normalized.endswith("?"):
        return "direct"

    return "simple"


def build_explanation_guidance(user_input: str, *, web_used: bool = False) -> Dict[str, str]:
    mode = infer_explanation_mode(user_input)
    instructions = {
        "direct": (
            "Answer directly in the first sentence. Keep it tight, clear, and useful. "
            "Do not drift into a long preamble."
        ),
        "simple": (
            "Start with the answer, then give a short clear explanation in plain language. "
            "Keep it to a few short sentences unless the user asks for depth."
        ),
        "deep": (
            "Start with the answer, then explain the reasoning in a few clear parts. "
            "Prefer a short breakdown with visible steps over one dense paragraph."
        ),
        "comparison": (
            "Answer with a crisp comparison. Lead with the key difference, then cover the most important tradeoffs. "
            "Keep it focused on best fit, performance, safety, and ease of use."
        ),
    }
    guidance = instructions.get(mode, instructions["direct"])
    if web_used:
        guidance = (
            f"{guidance} Use the live web findings as grounding, but synthesize them naturally. "
            "Do not dump snippets, lists of links, or raw search output. "
            "If the information is time-sensitive, make that clear in a natural sentence."
        )
    return {"mode": mode, "guidance": guidance}


def build_runtime_system_prompt(
    user_input: str,
    system_prompt: str,
    *,
    web_used: bool = False,
) -> tuple[str, str]:
    prompt = str(system_prompt or "").strip()
    guidance = build_explanation_guidance(user_input, web_used=web_used)
    if guidance["guidance"] and guidance["guidance"] not in prompt:
        prompt = (
            f"{prompt}\n\n"
            "REQUEST-SPECIFIC STYLE:\n"
            f"{guidance['guidance']}"
        ).strip()
    return prompt, guidance["mode"]


def build_messages(
    user_input: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    recent_history = history if history is not None else conversation_history[-RECENT_CONTEXT_MESSAGES:]
    messages = [{"role": "system", "content": system_prompt}]
    for item in recent_history:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    if is_meaningful_text(user_input):
        messages.append({"role": "user", "content": str(user_input).strip()})
    return messages


def build_web_grounding_text(search_result: Dict[str, Any]) -> str:
    safe_result = search_result if isinstance(search_result, dict) else {}
    data = safe_result.get("data") if isinstance(safe_result.get("data"), dict) else {}
    lines: List[str] = []

    query = str(data.get("query", "")).strip()
    heading = str(data.get("heading", "")).strip()
    abstract = clean_response(data.get("abstract"))
    related_topics = [
        clean_response(item)
        for item in list(data.get("related_topics") or [])[:4]
        if is_meaningful_text(item)
    ]

    if query:
        lines.append(f"Search query: {query}")
    if heading:
        lines.append(f"Primary topic: {heading}")
    if abstract:
        lines.append(f"Key live finding: {abstract}")
    if related_topics:
        lines.append("Related points:")
        lines.extend(f"- {item}" for item in related_topics)

    return "\n".join(lines).strip()


def build_local_web_summary(search_result: Dict[str, Any], user_input: str = "") -> str:
    safe_result = search_result if isinstance(search_result, dict) else {}
    data = safe_result.get("data") if isinstance(safe_result.get("data"), dict) else {}

    abstract = clean_response(data.get("abstract"))
    heading = clean_response(data.get("heading"))
    related_topics = [
        clean_response(item)
        for item in list(data.get("related_topics") or [])[:3]
        if is_meaningful_text(item)
    ]
    time_sensitive = any(
        token in str(user_input or "").lower()
        for token in ("latest", "current", "today", "now", "recent", "recently", "price", "version", "status", "news")
    )

    if abstract:
        opening = f"Right now, {abstract}" if time_sensitive else abstract
        opening = opening.rstrip(".") + "."
        if related_topics:
            return f"{opening} Other useful details: {', '.join(related_topics)}."
        return opening

    if heading:
        summary = (
            f"Right now, the live result centers on {heading}."
            if time_sensitive
            else f"The result centers on {heading}."
        )
        if related_topics:
            return f"{summary} Other useful details: {', '.join(related_topics)}."
        return summary

    return build_degraded_reply(user_input, providers_tried=[])


def _build_local_notes_content(topic: str) -> str:
    title_topic = topic.title()
    return clean_response(
        f"""Overview
- {title_topic} refers to an important concept area that should be understood through definition, structure, uses, and limits.
- A strong set of notes should focus on what it is, how it works, where it is used, and why it matters.

Core Ideas
- Define {topic} in simple terms before moving into technical details.
- Break the topic into its main components, process, or stages.
- Highlight the key terms a student should remember for exams, assignments, or discussion.

How It Works
- Explain the basic workflow or mechanism behind {topic}.
- Show how the main parts connect to produce a result.
- Mention the conditions, inputs, or assumptions that make the topic work well.

Applications
- Identify common real-world uses of {topic}.
- Connect the topic to industry, education, research, or everyday technology where relevant.
- Note why the topic is valuable in practical settings.

Advantages
- Summarize the main benefits, strengths, or reasons the topic is useful.
- Point out where it improves speed, quality, accuracy, understanding, or decision-making.

Limitations
- Mention the main weaknesses, risks, costs, or challenges related to {topic}.
- Note that good understanding includes both benefits and constraints.

Quick Summary
- {title_topic} is best understood by combining definition, mechanism, applications, strengths, and limitations.
- For revision, remember the core concept first, then the real-world uses and tradeoffs."""
    )


def _normalize_assignment_page_target(page_target: Optional[int]) -> Optional[int]:
    if page_target is None:
        return None
    try:
        return max(1, min(int(page_target), 12))
    except Exception:
        return None


def _build_assignment_depth_profile(page_target: Optional[int]) -> Dict[str, Any]:
    normalized_pages = _normalize_assignment_page_target(page_target)
    if normalized_pages and normalized_pages >= 10:
        return {
            "band": "extended",
            "paragraph_range": "3 to 4",
            "max_tokens": 760,
            "temperature": 0.35,
            "depth_guidance": (
                "Use fuller academic depth. Add explanation, evaluation, and concrete implications where they fit, "
                "but keep the section controlled and readable."
            ),
            "local_depth_sentences": [
                "A stronger long-form section should move beyond definition into interpretation, evidence, and practical significance.",
                "It should also connect this discussion to the broader assignment so the reader sees how the section supports the overall argument.",
            ],
        }
    if normalized_pages and normalized_pages >= 7:
        return {
            "band": "expanded",
            "paragraph_range": "2 to 3",
            "max_tokens": 620,
            "temperature": 0.34,
            "depth_guidance": (
                "Use clear academic depth with a little more explanation than a short assignment. "
                "Include at least one concrete implication, example, or evaluative point where it helps."
            ),
            "local_depth_sentences": [
                "In a mid-length assignment, this section should do more than define the idea; it should also explain why it matters in context.",
            ],
        }
    return {
        "band": "compact",
        "paragraph_range": "1 to 2",
        "max_tokens": 480,
        "temperature": 0.33,
        "depth_guidance": (
            "Keep the section concise and focused. Explain the essential point clearly without padding it into a long discussion."
        ),
        "local_depth_sentences": [],
    }


def _build_assignment_section_plan(topic: str, page_target: Optional[int] = None) -> List[Dict[str, str]]:
    _ = topic
    normalized_pages = _normalize_assignment_page_target(page_target)
    sections: List[Dict[str, str]] = [
        {"title": "Introduction", "purpose": "Introduce the topic, its importance, and the direction of the assignment."},
        {"title": "Background and Context", "purpose": "Explain the context, origins, or broader field around the topic."},
        {"title": "Core Concepts", "purpose": "Define the main ideas, terms, and foundational concepts clearly."},
        {"title": "How It Works", "purpose": "Explain the process, structure, or mechanism step by step."},
        {"title": "Applications", "purpose": "Describe real-world uses, adoption areas, or practical relevance."},
        {"title": "Advantages and Importance", "purpose": "Explain the main strengths, benefits, and academic importance."},
        {"title": "Challenges and Limitations", "purpose": "Present key limitations, risks, costs, or implementation barriers."},
    ]

    if normalized_pages and normalized_pages >= 4:
        sections.insert(2, {"title": "Historical Development", "purpose": "Summarize how the topic developed or evolved over time."})
        sections.append({"title": "Case Studies and Practical Examples", "purpose": "Add concrete examples or realistic use cases that ground the discussion."})

    if normalized_pages and normalized_pages >= 7:
        sections.append({"title": "Ethical and Social Impact", "purpose": "Discuss wider effects on people, society, fairness, safety, or policy."})
        sections.append({"title": "Future Scope and Trends", "purpose": "Explain likely future directions, open problems, and upcoming developments."})

    if normalized_pages and normalized_pages >= 10:
        sections.append({"title": "Implementation Considerations", "purpose": "Discuss resources, infrastructure, skills, cost, and deployment considerations."})
        sections.append({"title": "Comparative Perspective", "purpose": "Compare the topic with related methods, systems, or alternatives."})

    sections.append({"title": "Conclusion", "purpose": "Conclude the assignment by restating the central idea and final significance."})
    return sections


def _build_local_assignment_section_body(topic: str, section_title: str, page_target: Optional[int] = None) -> str:
    title_topic = topic.title()
    normalized_title = str(section_title or "").strip().lower()
    depth_profile = _build_assignment_depth_profile(page_target)
    page_hint = (
        f" This section is part of a longer assignment target of about {page_target} pages, so it is written with extra depth in mind."
        if page_target
        else ""
    )

    templates = {
        "introduction": (
            f"{title_topic} is an important subject because it connects theory with practical use in modern learning, technology, and decision-making. "
            f"A strong introduction should explain why {topic} matters, what the reader should understand by the end, and how the discussion will unfold.{page_hint}"
        ),
        "background and context": (
            f"The background of {topic} is best understood by examining the broader problem it addresses and the field in which it developed. "
            f"This context helps the reader see why {title_topic} became important and how it relates to earlier ideas, systems, or methods.{page_hint}"
        ),
        "historical development": (
            f"The development of {topic} can be traced through key stages of research, experimentation, and practical adoption. "
            f"Discussing this progression makes the assignment stronger because it shows how the topic matured over time rather than appearing as an isolated concept.{page_hint}"
        ),
        "core concepts": (
            f"The core concepts of {topic} include its main definitions, components, and operating principles. "
            f"This section should make the foundational ideas clear enough that later sections on applications and challenges are easy to follow.{page_hint}"
        ),
        "how it works": (
            f"To explain how {topic} works, it is useful to describe the process in a logical sequence, beginning with inputs or assumptions and then moving through the main stages. "
            f"That step-by-step explanation helps connect the theory behind {title_topic} to its practical outcome.{page_hint}"
        ),
        "applications": (
            f"One of the strongest reasons to study {topic} is its practical use in real settings such as education, research, business, engineering, or software systems. "
            f"Examples of application show how {title_topic} produces value beyond classroom theory.{page_hint}"
        ),
        "advantages and importance": (
            f"The importance of {topic} comes from the benefits it provides, such as clearer problem-solving, improved efficiency, stronger analysis, or more advanced automation. "
            f"A balanced assignment should show not only what {title_topic} is, but also why it has become important in academic and professional environments.{page_hint}"
        ),
        "challenges and limitations": (
            f"No topic is complete without a discussion of its limits. "
            f"{title_topic} may involve cost, complexity, resource requirements, implementation barriers, or risks that affect its adoption and performance.{page_hint}"
        ),
        "case studies and practical examples": (
            f"Case studies and practical examples make the discussion of {topic} more concrete by showing how the ideas operate in realistic situations. "
            f"They also help the reader move from abstract explanation to practical understanding.{page_hint}"
        ),
        "ethical and social impact": (
            f"The ethical and social impact of {topic} should be addressed carefully, especially where fairness, privacy, safety, access, or misuse may be involved. "
            f"This section strengthens the assignment by showing awareness of consequences beyond technical success.{page_hint}"
        ),
        "future scope and trends": (
            f"The future of {topic} can be discussed in terms of likely improvements, open research problems, and broader adoption trends. "
            f"Looking ahead helps position {title_topic} as a developing field rather than a finished idea.{page_hint}"
        ),
        "implementation considerations": (
            f"Implementation considerations include the resources, skills, infrastructure, cost, and maintenance requirements needed to apply {topic} effectively. "
            f"This section is especially valuable in a longer assignment because it connects theory with real deployment constraints.{page_hint}"
        ),
        "comparative perspective": (
            f"A comparative perspective helps the reader understand {topic} more clearly by setting it beside related methods, approaches, or alternatives. "
            f"This creates a sharper academic evaluation of where {title_topic} is strongest and where other options may perform better.{page_hint}"
        ),
        "conclusion": (
            f"In conclusion, {title_topic} should be understood through its background, core concepts, practical applications, benefits, and limitations. "
            f"A strong conclusion restates the central idea and explains why the topic remains relevant for future study and use.{page_hint}"
        ),
    }
    base_paragraph = templates.get(
        normalized_title,
        f"{title_topic} can be explained clearly by relating this section to the broader meaning, use, and significance of {topic}.{page_hint}",
    )
    supporting_paragraphs = list(depth_profile.get("local_depth_sentences") or [])
    if not supporting_paragraphs:
        return base_paragraph
    return "\n\n".join([base_paragraph, *supporting_paragraphs])


def _build_local_assignment_content(topic: str, page_target: Optional[int] = None) -> str:
    section_blocks = []
    for section in _build_assignment_section_plan(topic, page_target):
        section_blocks.append(
            f"{section['title']}\n{_build_local_assignment_section_body(topic, section['title'], page_target)}"
        )
    return clean_response("\n\n".join(section_blocks))


def _build_assignment_section_prompt(topic: str, section_title: str, section_purpose: str, page_target: Optional[int]) -> str:
    depth_profile = _build_assignment_depth_profile(page_target)
    page_hint = (
        f"The full assignment should feel deep enough for about {page_target} pages, so write this section with solid academic depth."
        if page_target
        else "Write this section with clear academic depth."
    )
    return (
        f"Write only the '{section_title}' section for an assignment on {topic}. "
        f"Purpose: {section_purpose} "
        f"{page_hint} "
        f"{depth_profile['depth_guidance']} "
        f"Start with the exact heading '{section_title}' on its own line, then provide {depth_profile['paragraph_range']} coherent paragraphs. "
        "Do not add other section headings."
    )


def _normalize_assignment_section_output(section_title: str, content: str) -> str:
    cleaned = clean_response(content)
    if not cleaned:
        return ""
    first_line = cleaned.splitlines()[0].strip().lower()
    if first_line == section_title.strip().lower():
        return cleaned
    return f"{section_title}\n{cleaned}"


def _generate_assignment_chunked_content_payload(topic: str, page_target: Optional[int]) -> Dict[str, Any]:
    normalized_pages = _normalize_assignment_page_target(page_target)
    depth_profile = _build_assignment_depth_profile(normalized_pages)
    section_plan = _build_assignment_section_plan(topic, normalized_pages)
    combined_sections: List[str] = []
    providers_tried: List[Any] = []
    provider_name: Optional[str] = None
    provider_model: Optional[str] = None
    used_provider = False
    degraded = False

    for section in section_plan:
        payload = generate_response_payload(
            _build_assignment_section_prompt(topic, section["title"], section["purpose"], normalized_pages),
            system_override=DOCUMENT_ASSIGNMENT_PROMPT,
            max_tokens=int(depth_profile["max_tokens"]),
            temperature=float(depth_profile["temperature"]),
        )
        providers_tried.extend(list(payload.get("providers_tried") or []))
        content = _normalize_assignment_section_output(section["title"], str(payload.get("content") or ""))
        if payload.get("success") and is_meaningful_text(content):
            combined_sections.append(content)
            used_provider = True
            if provider_name is None:
                provider_name = payload.get("provider")
                provider_model = payload.get("model")
            continue

        degraded = True
        combined_sections.append(
            f"{section['title']}\n{_build_local_assignment_section_body(topic, section['title'], normalized_pages)}"
        )

    source = "provider_chunked"
    if degraded and used_provider:
        source = "mixed_chunked"
    elif not used_provider:
        source = "local_template"

    return {
        "success": True,
        "content": clean_response("\n\n".join(combined_sections)),
        "provider": provider_name if used_provider else "local",
        "model": provider_model if used_provider else "template",
        "source": source,
        "degraded": degraded or not used_provider,
        "providers_tried": providers_tried,
        "error": None if used_provider else "Provider content was unavailable for chunked assignment generation.",
    }


def _build_document_generation_prompt(document_type: str, topic: str, page_target: Optional[int]) -> str:
    if document_type == "notes":
        return f"Create structured notes on {topic}."
    page_hint = f" Aim for enough detail to support about {page_target} pages." if page_target else ""
    return f"Write a structured assignment on {topic}.{page_hint}"


def generate_document_content_payload(
    document_type: str,
    topic: str,
    *,
    page_target: Optional[int] = None,
) -> Dict[str, Any]:
    normalized_type = str(document_type or "").strip().lower()
    normalized_topic = str(topic or "").strip()
    if normalized_type not in {"notes", "assignment"}:
        return {
            "success": False,
            "content": "",
            "provider": None,
            "model": None,
            "source": "invalid_request",
            "degraded": True,
            "providers_tried": [],
            "error": "Unsupported document type.",
        }
    if not is_meaningful_text(normalized_topic):
        return {
            "success": False,
            "content": "",
            "provider": None,
            "model": None,
            "source": "invalid_request",
            "degraded": True,
            "providers_tried": [],
            "error": "Topic is required.",
        }

    normalized_pages = _normalize_assignment_page_target(page_target)
    if normalized_type == "assignment" and normalized_pages and normalized_pages >= 4:
        return _generate_assignment_chunked_content_payload(normalized_topic, normalized_pages)

    system_prompt = DOCUMENT_NOTES_PROMPT if normalized_type == "notes" else DOCUMENT_ASSIGNMENT_PROMPT
    prompt = _build_document_generation_prompt(normalized_type, normalized_topic, page_target)
    max_tokens = 1500 if normalized_type == "notes" else 2600
    payload = generate_response_payload(
        prompt,
        system_override=system_prompt,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    content = clean_response(payload.get("content"))
    if payload.get("success") and is_meaningful_text(content):
        return {
            "success": True,
            "content": content,
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "source": "provider",
            "degraded": False,
            "providers_tried": list(payload.get("providers_tried") or []),
            "error": None,
        }

    local_content = (
        _build_local_notes_content(normalized_topic)
        if normalized_type == "notes"
        else _build_local_assignment_content(normalized_topic, page_target)
    )
    return {
        "success": True,
        "content": local_content,
        "provider": "local",
        "model": "template",
        "source": "local_template",
        "degraded": True,
        "providers_tried": list(payload.get("providers_tried") or []),
        "error": payload.get("error"),
    }


def get_groq_client():
    key = (GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        raise ValueError("GROQ_API_KEY not found in .env")
    if key == "your_groq_key_here":
        raise ValueError("GROQ_API_KEY is still placeholder")
    if Groq is None:
        raise ValueError("Groq SDK is not installed")
    return Groq(api_key=key)


def _response_contains_bad_phrases(response_text: str) -> bool:
    normalized = clean_response(response_text).lower()
    return any(marker in normalized for marker in BAD_RESPONSE_MARKERS)


def _last_user_message(messages: List[Dict[str, str]]) -> str:
    for item in reversed(messages):
        if str(item.get("role", "")).strip().lower() == "user":
            content = str(item.get("content", "")).strip()
            if content:
                return content
    return ""


def _strip_leading_filler(text: str) -> str:
    cleaned = str(text or "").strip()
    patterns = [
        r"^(certainly|of course|absolutely|sure)\b[\s,.:!-]*",
        r"^(understood|right away|analysis complete)\b[\s,.:!-]*",
        r"^(certainly|of course|absolutely|sure)\s+(sir|ma'am)\b[\s,.:!-]*",
        r"^(sir|ma'am)\b[\s,.:!-]*",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        if updated != cleaned:
            cleaned = updated.strip()
    return cleaned


def _strip_direct_address_phrases(text: str) -> str:
    cleaned = str(text or "").strip()
    patterns = [
        r"^(hello|hi|hey)\s+[A-Z][a-z]+(?:\s+from\s+[A-Z][A-Za-z-]+)?[,:\-\s]+",
        r"^(hello|hi|hey)\s+[A-Z][a-z]+\s+[A-Z][a-z]+[,:\-\s]+",
        r",\s*(sir|ma'am)\s*,",
        r",\s*(sir|ma'am)\s*\.",
        r"\b(sir|ma'am)\b[:\-]?\s+",
        r"\bto\s+assist\s+[A-Z][a-z]+\b",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
    return cleaned.strip()


def _strip_meta_section_wrappers(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned

    lines = [line.strip() for line in cleaned.splitlines()]
    filtered: List[str] = []
    inline_patterns = (
        r"^objective:\s*.*$",
        r"^introduction\s*$",
        r"^current knowledge\s*$",
        r"^current status\s*$",
        r"^recent updates\s*$",
        r"^potential sources\s*$",
        r"^next actions\s*$",
    )
    for line in lines:
        updated = line
        for pattern in inline_patterns:
            if re.match(pattern, updated, flags=re.IGNORECASE):
                updated = ""
                break
        if not updated:
            continue
        filtered.append(updated)

    result = "\n".join(filtered).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _apply_mode_length_guard(text: str, user_input: str) -> str:
    cleaned = str(text or "").strip()
    mode = infer_explanation_mode(user_input)
    if mode == "direct" and len(cleaned) > 420:
        return _trim_to_sentence_count(cleaned, max_sentences=3, max_chars=420)
    if mode == "simple" and len(cleaned) > 520:
        return _trim_to_sentence_count(cleaned, max_sentences=4, max_chars=520)
    if mode == "comparison" and len(cleaned) > 900:
        return _trim_to_sentence_count(cleaned, max_sentences=6, max_chars=900)
    return cleaned


def _format_inline_numbered_list(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned
    return re.sub(r"\s+(?=\d+\.\s)", "\n", cleaned)


def _looks_like_direct_question(user_input: str) -> bool:
    normalized = str(user_input or "").strip().lower()
    if "?" in normalized:
        return True
    starters = (
        "what",
        "who",
        "why",
        "how",
        "when",
        "where",
        "is",
        "are",
        "can",
        "could",
        "should",
        "would",
        "do",
        "does",
        "did",
        "tell me",
        "explain",
        "write",
        "write me",
        "make",
        "create",
        "give me",
        "show me",
        "help me",
    )
    return normalized.startswith(starters)


def _looks_like_casual_conversation(user_input: str) -> bool:
    normalized = str(user_input or "").strip().lower()
    if not normalized:
        return False
    return normalized in CASUAL_CONVERSATION_MARKERS


def _trim_to_sentence_count(text: str, max_sentences: int = 2, max_chars: int = 220) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    trimmed = " ".join(part for part in sentences[:max_sentences] if part.strip()).strip()
    if len(trimmed) > max_chars:
        trimmed = trimmed[: max_chars - 3].rstrip() + "..."
    return trimmed or str(text or "").strip()


def _is_history_question(user_input: str) -> bool:
    normalized = str(user_input or "").strip().lower()
    history_markers = (
        "before this",
        "earlier",
        "previous",
        "last time",
        "what did we talk about",
        "remember",
        "recall",
    )
    return any(marker in normalized for marker in history_markers)


def _strip_stale_memory_filler(text: str) -> str:
    cleaned = str(text or "").strip()
    patterns = [
        r"^we(?:'ve| have)\s+(?:discussed this before|had this conversation before|been here before)\.?\s*",
        r"^you(?:'ve| have)\s+asked me .*?(?:already|before)\.?\s*",
        r"^i(?:'ve| have)\s+(?:answered this question(?: for you)? .*?before|noticed that you(?:'ve| have) asked this question .*?before)\.?\s*",
        r"^i(?:'ve| have)\s+noticed that you(?:'ve| have)\s+asked .*?multiple times before\.?\s*",
        r"^as i(?:'ve| have)\s+mentioned before[,:\s-]*",
        r"^it seems like you're looking for .*?, and i(?:'m| am)\s+happy to provide it again\.?\s*",
        r"^it seems like you're .*?\.\s*",
        r"^to recap[,:\s-]*",
        r"^to avoid repeating myself[,:\s-]*",
        r"^i(?:'ll| will)\s+provide the same answer i(?:'ve| have) given you in the past[:.\s-]*",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        if updated != cleaned:
            cleaned = updated.strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _strip_repeat_claim_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    markers = (
        "multiple times",
        "asked this question",
        "asked about",
        "we've had this conversation",
        "we discussed",
        "i've answered",
        "i've noticed",
        "i see you've asked",
        "it seems like you've asked",
        "provide it again",
        "provide the answer again",
        "explain it again",
        "same answer",
        "to avoid repeating",
        "for your convenience",
    )
    trimmed = list(sentences)
    removed = 0
    while trimmed and removed < 3:
        first = str(trimmed[0] or "").strip().lower()
        if first and any(marker in first for marker in markers):
            trimmed.pop(0)
            removed += 1
            continue
        break
    result = " ".join(part for part in trimmed if str(part).strip()).strip()
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result or str(text or "").strip()


def polish_assistant_reply(text: Optional[str], user_input: str = "") -> str:
    cleaned = clean_response(text)
    if not cleaned:
        return ""

    cleaned = _strip_direct_address_phrases(cleaned)
    cleaned = _strip_meta_section_wrappers(cleaned)
    cleaned = _format_inline_numbered_list(cleaned)

    if _looks_like_casual_conversation(user_input):
        cleaned = _strip_leading_filler(cleaned)
        cleaned = _strip_stale_memory_filler(cleaned)
        cleaned = _strip_repeat_claim_sentences(cleaned)
        cleaned = _trim_to_sentence_count(cleaned)

    if _looks_like_direct_question(user_input):
        cleaned = _strip_leading_filler(cleaned)
        if not _is_history_question(user_input):
            cleaned = _strip_stale_memory_filler(cleaned)
            cleaned = _strip_repeat_claim_sentences(cleaned)
            cleaned = _strip_stale_memory_filler(cleaned)

    cleaned = _apply_mode_length_guard(cleaned, user_input)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_degraded_reply(user_input: str, providers_tried: Optional[List[Any]] = None) -> str:
    attempts = providers_tried or []
    if attempts:
        provider_names = []
        for item in attempts:
            if isinstance(item, dict):
                name = str(item.get("provider", "")).strip()
            else:
                raw = str(item)
                name = raw.split(":", 1)[0].strip()
            if name and name not in provider_names:
                provider_names.append(name)
        attempted = ", ".join(name.upper() for name in provider_names[:3]) if provider_names else "the configured providers"
        return (
            "The request is clear, but I can't answer it reliably right now because my live AI providers "
            f"are not completing the response path cleanly. I tried {attempted}. Please try again in a moment or check provider health."
        )

    return (
        "I can see what you asked, but I do not have a healthy live provider I can trust for a dependable answer yet. "
        "Please check provider health and try again."
    )


def generate_groq_response(
    messages: List[Dict[str, str]],
    model: str = "llama-3.3-70b-versatile",
) -> Dict[str, Any]:
    try:
        client = get_groq_client()
        response = generate_with_provider(
            "groq",
            messages,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
        )
        return {
            "content": response.get("text"),
            "model": response.get("model") or model,
            "provider": "groq",
            "success": True,
        }
    except Exception as error:
        print(f"[GROQ ERROR] {error}")
        return {
            "content": None,
            "error": str(error),
            "provider": "groq",
            "success": False,
            "model": model,
        }


def generate_with_fallback(
    messages: List[Dict[str, str]],
    system_prompt: str,
    *,
    preferred_only: bool = False,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    normalized_messages = [dict(item) for item in messages if str(item.get("content", "")).strip()]
    if not any(str(item.get("role", "")).strip().lower() == "system" for item in normalized_messages):
        normalized_messages = [{"role": "system", "content": str(system_prompt).strip()}] + normalized_messages

    provider_result = generate_with_best_provider(
        normalized_messages,
        preferred=DEFAULT_REASONING_PROVIDER,
        preferred_only=preferred_only,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if provider_result.get("success"):
        return {
            "content": provider_result.get("text"),
            "provider": provider_result.get("provider"),
            "model": provider_result.get("model"),
            "success": True,
            "providers_tried": provider_result.get("attempts") or [],
            "routing_order": provider_result.get("routing_order") or [],
            "latency_ms": provider_result.get("latency_ms"),
        }

    return {
        "content": None,
        "success": False,
        "error": provider_result.get("reason") or "All AI providers failed",
        "providers_tried": provider_result.get("attempts") or [],
        "routing_order": provider_result.get("routing_order") or [],
        "provider": None,
        "model": None,
        "degraded_reply": build_degraded_reply(
            user_input=_last_user_message(normalized_messages),
            providers_tried=provider_result.get("attempts") or [],
        ),
    }


def generate_web_search_response_payload(
    user_input: str,
    search_result: Dict[str, Any],
    *,
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    normalized_input = str(user_input or "").strip()
    if not is_meaningful_text(normalized_input):
        return {
            "success": False,
            "content": None,
            "error": "Missing user input.",
            "degraded_reply": FALLBACK_USER_MESSAGE,
            "web_used": False,
            "explanation_mode": "direct",
        }

    language = detect_language(normalized_input)
    base_system_prompt = build_system_prompt(language, system_override=system_override)
    system_prompt, explanation_mode = build_runtime_system_prompt(
        normalized_input,
        base_system_prompt,
        web_used=True,
    )
    grounding_text = build_web_grounding_text(search_result)
    if not grounding_text:
        local_summary = build_local_web_summary(search_result, normalized_input)
        return {
            "success": False,
            "content": None,
            "error": "No usable web findings were available.",
            "degraded_reply": local_summary,
            "web_used": False,
            "explanation_mode": explanation_mode,
        }

    messages = build_messages("", system_prompt)
    messages.append(
        {
            "role": "user",
            "content": (
                f"User question: {normalized_input}\n\n"
                "Live web findings:\n"
                f"{grounding_text}\n\n"
                "Answer as AURA. Lead with the answer, then explain the most important supporting facts. "
                "Do not dump raw search results or mention searching unless it helps the user."
            ),
        }
    )

    payload = generate_with_fallback(
        messages,
        system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = clean_response(payload.get("content"))
    if payload.get("success") and is_meaningful_text(content):
        payload["content"] = polish_assistant_reply(content, user_input=normalized_input)
        payload["web_used"] = True
        payload["explanation_mode"] = explanation_mode
        payload["web_grounding"] = grounding_text
        add_to_history("user", normalized_input)
        add_to_history("assistant", payload["content"])
        return payload

    payload["success"] = False
    payload["content"] = None
    payload["web_used"] = False
    payload["explanation_mode"] = explanation_mode
    payload["degraded_reply"] = build_local_web_summary(search_result, normalized_input)
    return payload


def generate_response_payload(
    user_input_or_messages: str | List[Dict[str, str]],
    *,
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    if isinstance(user_input_or_messages, list):
        messages = [dict(item) for item in user_input_or_messages]
        existing_system = next((item.get("content", "") for item in messages if item.get("role") == "system"), "")
        base_system_prompt = build_system_prompt(
            "english",
            system_override=system_override or existing_system or JARVIS_SYSTEM_PROMPT,
        )
        provider_messages = [item for item in messages if item.get("role") != "system"]
        user_input = str(provider_messages[-1].get("content", "")) if provider_messages else ""
    else:
        user_input = str(user_input_or_messages).strip()
        language = detect_language(user_input)
        base_system_prompt = build_system_prompt(language, system_override=system_override)
        provider_messages = build_messages(user_input, base_system_prompt)

    if not is_meaningful_text(user_input):
        return {
            "content": "Please say something so I can respond.",
            "provider": "local",
            "model": "none",
            "success": True,
        }

    system_prompt, explanation_mode = build_runtime_system_prompt(user_input, base_system_prompt)
    payload = generate_with_fallback(
        provider_messages,
        system_prompt,
        preferred_only=True,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = clean_response(payload.get("content"))

    if payload.get("success") and content and _response_contains_bad_phrases(content):
        retry_system_prompt = (
            f"{system_prompt}\n\n"
            "Important: Answer directly. Avoid canned filler. "
            "Sound calm, capable, and natural."
        )
        retry_payload = generate_with_fallback(
            provider_messages,
            retry_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        retry_content = clean_response(retry_payload.get("content"))
        if retry_payload.get("success") and retry_content:
            payload = retry_payload
            content = retry_content

    if payload.get("success") and is_meaningful_text(content):
        payload["content"] = polish_assistant_reply(content, user_input=user_input)
        payload["explanation_mode"] = explanation_mode
        add_to_history("user", user_input)
        add_to_history("assistant", payload["content"])
        return payload

    if payload.get("success"):
        payload["success"] = False
        payload["error"] = payload.get("error") or "Provider returned empty content."
        payload["content"] = None
    payload["degraded_reply"] = build_degraded_reply(user_input=user_input, providers_tried=payload.get("providers_tried"))
    payload["explanation_mode"] = explanation_mode
    return payload


def get_ai_response(
    user_input: str,
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    payload = generate_response_payload(
        user_input,
        system_override=system_override,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if payload.get("success") and is_meaningful_text(payload.get("content")):
        return clean_response(payload.get("content"))
    return FALLBACK_USER_MESSAGE


def generate_response(
    user_input_or_messages: str | List[Dict[str, str]],
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    payload = generate_response_payload(
        user_input_or_messages,
        system_override=system_override,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if payload.get("success") and is_meaningful_text(payload.get("content")):
        return clean_response(payload.get("content"))
    return FALLBACK_USER_MESSAGE


def get_provider_summary() -> Dict[str, object]:
    return summarize_provider_statuses(fresh=True)
