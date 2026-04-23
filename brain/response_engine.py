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

DOCUMENT_STYLE_ALIASES = {
    "professional": "professional",
    "simple": "simple",
    "detailed": "detailed",
}

CITATION_STYLE_ALIASES = {
    "apa": "apa",
    "mla": "mla",
    "chicago": "chicago",
    "harvard": "harvard",
    "ieee": "ieee",
    "basic": "basic",
}

DOCUMENT_NOTES_PROMPT = (
    "You are an expert academic content writer. Write REAL, factual study notes about the given topic. "
    "REQUIRED SECTIONS (use these exact headings): Overview, History, Core Concepts, How It Works, Applications, Advantages, Limitations, Quick Summary. "
    "Under each heading write actual facts, definitions, and specific information about the topic. "
    "CRITICAL: Never write meta-instructions like 'this section should...' or 'the reader should understand' or 'it is important to know'. "
    "Write as a subject-matter expert explaining the topic directly. "
    "Use plain-text section headings only — no # symbols, no markdown. Use bullet points starting with '- ' under each heading."
)

DOCUMENT_ASSIGNMENT_PROMPT = (
    "You are an expert academic writer. Write a REAL, informative academic assignment on the given topic. "
    "CRITICAL: Write actual facts, analysis, and domain-specific explanations — never write meta-instructions or placeholder sentences. "
    "Start directly with 'Introduction' as the first heading. "
    "REQUIRED SECTIONS: Introduction, Background, Core Concepts, How It Works, Applications, Challenges, Conclusion. "
    "Use plain-text section headings only — no # symbols, no bold markers, no numbered headings. "
    "Write coherent academic paragraphs (3–5 sentences each) under every heading. "
    "NEVER write phrases like 'this section should explore', 'the student should understand', or 'a strong assignment must'. "
    "Write in formal academic prose with specific facts, examples, and analytical depth."
)

TRANSFORMATION_NOTES_PROMPT = (
    "You are a professional academic content specialist converting source material into structured study notes.\n\n"
    "OUTPUT FORMAT:\n"
    "- Start with a concise, informative title for the topic\n"
    "- Use PLAIN-TEXT SECTION HEADINGS in title case (no # symbols, no markdown formatting)\n"
    "- Under each heading, write bullet points starting with '- '\n"
    "- Bullets must be concise but information-dense — capture the key fact, not a vague summary\n"
    "- Group related concepts under logical headings\n\n"
    "QUALITY STANDARDS:\n"
    "- Extract ALL key concepts, definitions, data, and examples from the source\n"
    "- Preserve technical vocabulary and terminology from the source\n"
    "- If source material has lists or tables, convert them into clean bullet points\n"
    "- Never invent details absent from the source\n"
    "- Begin directly with the title — no preamble, no 'Here are your notes:', no chatbot phrases"
)

TRANSFORMATION_ASSIGNMENT_PROMPT = (
    "You are a professional academic writer converting source material into a structured assignment.\n\n"
    "OUTPUT FORMAT:\n"
    "- Introduction: Establish context and scope clearly in 1–2 focused paragraphs\n"
    "- 3–5 analytical sections with plain-text headings appropriate to the topic\n"
    "- Each section: 1–3 paragraphs of formal academic prose developing a single argument\n"
    "- Conclusion: Synthesize the main findings — no new information\n\n"
    "QUALITY STANDARDS:\n"
    "- Build the assignment from key information in the source material\n"
    "- Write in formal academic tone: precise, analytical, and well-structured\n"
    "- Each paragraph must develop a coherent point with explanation and where relevant, evidence\n"
    "- Connect sections logically — use transitional framing\n"
    "- Do not invent facts, statistics, or claims not supported by the source\n"
    "- Begin directly with the Introduction — no chatbot opening, no 'In this assignment I will' sentence"
)

TECHNICAL_ASSIGNMENT_MARKERS = (
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "transformer",
    "transformers",
    "neural",
    "language model",
    "llm",
    "algorithm",
    "system",
    "software",
    "computer",
    "computing",
    "data",
    "database",
    "network",
    "api",
    "cybersecurity",
    "cloud",
)

SOCIAL_ASSIGNMENT_MARKERS = (
    "education",
    "poverty",
    "inequality",
    "gender",
    "human rights",
    "social justice",
    "mental health",
    "public health",
    "climate change",
    "migration",
    "unemployment",
    "community",
    "communities",
    "society",
    "policy",
    "governance",
    "labor",
    "healthcare",
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


def _build_local_notes_content(
    topic: str,
    *,
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
) -> str:
    title_topic = topic.title()
    normalized_style = normalize_document_style(style)
    content = clean_response(
        f"""{title_topic}

Overview
- {title_topic} is a field of study with established theory, practical applications, and ongoing academic importance.
- It encompasses core principles, historical development, and real-world use across multiple domains.
- Understanding {topic} requires mastery of its definitions, mechanisms, key use cases, and known limitations.

History
- {title_topic} has evolved over time through contributions from researchers, practitioners, and institutions.
- Early developments established foundational principles; later advancements expanded its scope and applicability.
- Key milestones in the history of {topic} shaped how it is understood and applied today.

Core Concepts
- The fundamental ideas in {topic} include its defining characteristics, structural components, and governing principles.
- Central terminology must be understood precisely to engage with the subject at an academic level.
- Relationships between core concepts explain how different aspects of {topic} interact and function together.

How It Works
- {title_topic} operates through a defined process involving specific inputs, transformation steps, and outputs.
- The internal mechanism follows logical rules or natural principles that determine its behaviour and outcomes.
- Understanding the step-by-step workflow connects the theory of {topic} to its practical results.

Applications
- {title_topic} is applied across industries including technology, healthcare, education, business, and research.
- Real-world implementations demonstrate how {topic} solves problems or creates value in practical settings.
- Use cases vary from foundational academic study to advanced professional and industrial applications.

Advantages
- {title_topic} offers significant benefits such as improved efficiency, stronger analytical capability, or enhanced decision-making.
- Its core strengths make it a preferred approach in contexts where accuracy, scalability, or depth of insight are required.
- Academic and professional recognition of {topic} reflects its proven value across diverse fields.

Limitations
- {title_topic} is subject to constraints including cost, complexity, data requirements, or implementation barriers.
- Known limitations affect its performance, accessibility, or adoption in certain environments.
- A critical understanding of the subject includes awareness of where {topic} falls short or requires careful management.

Quick Summary
- {title_topic}: master the definition, historical development, core concepts, mechanism, applications, strengths, and limitations.
- Key revision priorities: terminology, real-world use cases, and the balance between advantages and constraints.
- For deeper understanding, connect how {topic} works in theory to how it performs in practice."""
    )
    if normalized_style == "detailed":
        content = clean_response(
            f"{content}\n\nFuture Directions\n"
            f"- {title_topic} continues to develop with new research, improved methods, and broader adoption.\n"
            f"- Emerging trends suggest ongoing relevance of {topic} in academic and professional contexts.\n"
            f"- Critical engagement with current literature provides deeper perspective on where the field is heading."
        )
    elif normalized_style == "simple":
        content = clean_response(
            f"{content}\n\nFast Review\n"
            f"- What is {topic}? — Definition and core idea.\n"
            f"- How does it work? — Key mechanism or process.\n"
            f"- Where is it used? — Main real-world applications.\n"
            f"- What are the tradeoffs? — Main strength vs. main limitation."
        )
    if include_references:
        content = _append_references_section(content, topic, citation_style)
    return content


def normalize_document_style(style: Optional[str]) -> str:
    normalized = str(style or "professional").strip().lower()
    return DOCUMENT_STYLE_ALIASES.get(normalized, "professional")


def normalize_citation_style(style: Optional[str]) -> Optional[str]:
    if style is None:
        return None
    normalized = str(style).strip().lower()
    return CITATION_STYLE_ALIASES.get(normalized)


def _build_document_style_guidance(document_type: str, style: Optional[str]) -> str:
    normalized_style = normalize_document_style(style)
    if normalized_style == "simple":
        return (
            "Use straightforward language, short paragraphs, and clear explanation without unnecessary jargon."
            if document_type == "assignment"
            else "Keep the notes concise, revision-friendly, and easy to scan quickly."
        )
    if normalized_style == "detailed":
        return (
            "Use fuller academic depth, stronger explanation, and clearer development of examples, implications, and structure."
            if document_type == "assignment"
            else "Make the notes fuller and more instructive, with slightly deeper explanation under each heading."
        )
    return (
        "Keep the writing polished, structured, and academically professional."
        if document_type == "assignment"
        else "Keep the notes polished, organized, and professionally structured for study use."
    )


def _build_reference_template_lines(topic: str, citation_style: Optional[str]) -> list[str]:
    normalized_style = normalize_citation_style(citation_style) or "basic"
    title_topic = topic.title()
    templates = {
        "apa": [
            f"- Author or institution. (Year). Title related to {title_topic}. Publisher or journal.",
            f"- Course-approved textbook chapters and review articles focused on {title_topic}.",
            "- Replace these template entries with verified academic sources before final submission.",
        ],
        "mla": [
            f"- Author or institution. \"Title Related to {title_topic}.\" Publisher or Journal, Year.",
            f"- Course-approved books, articles, and reports directly connected to {title_topic}.",
            "- Replace these template entries with verified academic sources before final submission.",
        ],
        "chicago": [
            f"- Author or institution. Year. Title related to {title_topic}. Place: Publisher.",
            f"- Academic books, journal articles, and institutional reports about {title_topic}.",
            "- Replace these template entries with verified academic sources before final submission.",
        ],
        "harvard": [
            f"- Author or institution (Year) Title related to {title_topic}, Publisher or Journal.",
            f"- Use relevant scholarly books, articles, and institutional reports on {title_topic}.",
            "- Replace these template entries with verified academic sources before final submission.",
        ],
        "ieee": [
            f"- [1] Author or institution, \"Title related to {title_topic},\" Publisher or Journal, Year.",
            f"- [2] Verified technical or academic sources directly relevant to {title_topic}.",
            "- Replace these template entries with verified academic sources before final submission.",
        ],
        "basic": [
            f"- Use course-approved textbooks, review articles, and institutional sources related to {title_topic}.",
            "- Keep the reference entries consistent in author, year, title, and source formatting.",
            "- Replace these guidance lines with verified academic sources before final submission.",
        ],
    }
    return templates.get(normalized_style, templates["basic"])


def _append_references_section(content: str, topic: str, citation_style: Optional[str]) -> str:
    cleaned = clean_response(content)
    if re.search(r"(?im)^references\s*$", cleaned) or re.search(r"(?im)^works cited\s*$", cleaned):
        return cleaned
    reference_heading = "References"
    if normalize_citation_style(citation_style):
        reference_heading = f"References ({normalize_citation_style(citation_style).upper()} Style)"
    reference_lines = "\n".join(_build_reference_template_lines(topic, citation_style))
    return clean_response(f"{cleaned}\n\n{reference_heading}\n{reference_lines}")


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
            "base_paragraph_target": 3,
            "paragraph_ceiling": 4,
            "max_tokens": 760,
            "temperature": 0.35,
            "depth_guidance": (
                "Use fuller academic depth. Add explanation, evaluation, and concrete implications where they fit, "
                "but keep the section controlled, readable, and academically organized."
            ),
        }
    if normalized_pages and normalized_pages >= 7:
        return {
            "band": "expanded",
            "base_paragraph_target": 2,
            "paragraph_ceiling": 3,
            "max_tokens": 620,
            "temperature": 0.34,
            "depth_guidance": (
                "Use clear academic depth with a little more explanation than a short assignment. "
                "Include at least one concrete implication, example, or evaluative point where it helps."
            ),
        }
    return {
        "band": "compact",
        "base_paragraph_target": 2,
        "paragraph_ceiling": 2,
        "max_tokens": 480,
        "temperature": 0.33,
        "depth_guidance": (
            "Keep the section concise and focused. Explain the essential point clearly without padding it into a long discussion."
        ),
    }


def _build_assignment_section_weight(section_title: str) -> Dict[str, Any]:
    normalized_title = str(section_title or "").strip().lower()
    section_profiles: Dict[str, Dict[str, Any]] = {
        "introduction": {
            "weight_label": "light",
            "token_multiplier": 0.55,
            "paragraph_delta": -1,
            "prompt_focus": "Keep this section brief, focused, and framing-oriented.",
            "local_support": [
                "It should quickly establish the scope of the discussion without expanding into details that belong in later analytical sections.",
            ],
        },
        "background and context": {
            "weight_label": "moderate",
            "token_multiplier": 0.72,
            "paragraph_delta": 0,
            "prompt_focus": "Give enough context to orient the reader before moving into analysis.",
            "local_support": [
                "A good background section explains the surrounding field, assumptions, and prior conditions that make the topic meaningful.",
                "It should help the reader understand how the topic fits into a wider academic or practical landscape.",
            ],
        },
        "historical development": {
            "weight_label": "moderate",
            "token_multiplier": 0.72,
            "paragraph_delta": 0,
            "prompt_focus": "Focus on the most relevant stages of development rather than turning this into a long chronology.",
            "local_support": [
                "The strongest historical discussion highlights the turning points that changed how the topic was understood or applied.",
                "This helps the reader see development as a progression of ideas rather than a disconnected timeline.",
            ],
        },
        "core concepts": {
            "weight_label": "high",
            "token_multiplier": 1.0,
            "paragraph_delta": 1,
            "prompt_focus": "Treat this as a major analytical section and go beyond basic definition into structure, relationships, and significance.",
            "local_support": [
                "A strong concepts section should clarify how the major ideas connect instead of listing them in isolation.",
                "It should also explain which ideas are foundational and which ones depend on earlier theoretical assumptions.",
            ],
        },
        "how it works": {
            "weight_label": "high",
            "token_multiplier": 1.0,
            "paragraph_delta": 1,
            "prompt_focus": "Treat this as a major analytical section and explain the mechanism clearly, step by step.",
            "local_support": [
                "The explanation becomes more convincing when each stage of the mechanism is linked to the result it produces.",
                "It is also useful to clarify where inputs, internal processes, and outputs interact so the section feels logically complete.",
            ],
        },
        "applications": {
            "weight_label": "high",
            "token_multiplier": 1.0,
            "paragraph_delta": 1,
            "prompt_focus": "Treat this as a major applied section and use concrete real-world use cases rather than broad claims.",
            "local_support": [
                "A strong applications section should show where the topic creates practical value in specific domains or industries.",
                "It should also distinguish between theoretical potential and evidence of real adoption or usefulness.",
            ],
        },
        "case studies and practical examples": {
            "weight_label": "high",
            "token_multiplier": 0.96,
            "paragraph_delta": 1,
            "prompt_focus": "Treat this as a major evidence section and ground the discussion in realistic examples.",
            "local_support": [
                "Case studies strengthen the assignment by showing how abstract ideas perform when they meet real constraints and goals.",
                "Well-chosen examples also make evaluation easier because the reader can see practical outcomes instead of only theory.",
            ],
        },
        "comparative perspective": {
            "weight_label": "high",
            "token_multiplier": 0.98,
            "paragraph_delta": 1,
            "prompt_focus": "Treat this as a major evaluative section and compare the topic with credible alternatives in a balanced way.",
            "local_support": [
                "A useful comparison should explain not only differences but also the contexts in which one approach is more suitable than another.",
                "This makes the assignment sound more academic because it evaluates tradeoffs instead of assuming a single best answer.",
            ],
        },
        "advantages and importance": {
            "weight_label": "moderate",
            "token_multiplier": 0.72,
            "paragraph_delta": 0,
            "prompt_focus": "Keep the discussion balanced and explain why these strengths matter, not just what they are.",
            "local_support": [
                "The best way to discuss advantages is to link each strength to a meaningful outcome such as efficiency, accuracy, accessibility, or impact.",
                "This prevents the section from sounding promotional and keeps it grounded in academic reasoning.",
            ],
        },
        "challenges and limitations": {
            "weight_label": "moderate_high",
            "token_multiplier": 0.86,
            "paragraph_delta": 1,
            "prompt_focus": "Give this section serious analytical weight and explain the implications of each limitation clearly.",
            "local_support": [
                "A stronger limitations section does more than list problems; it explains how those problems affect adoption, performance, or trust.",
                "It should also show whether the weaknesses are temporary, structural, or dependent on context.",
            ],
        },
        "ethical and social impact": {
            "weight_label": "moderate_high",
            "token_multiplier": 0.84,
            "paragraph_delta": 1,
            "prompt_focus": "Give this section analytical depth and discuss social consequences, fairness, safety, or policy implications with balance.",
            "local_support": [
                "This section becomes stronger when it connects ethical issues to real stakeholders rather than treating ethics as an abstract side note.",
                "A balanced academic discussion should also recognize that social impact depends on how the topic is designed, governed, and deployed.",
            ],
        },
        "implementation considerations": {
            "weight_label": "moderate_high",
            "token_multiplier": 0.88,
            "paragraph_delta": 1,
            "prompt_focus": "Give this section practical depth and connect theory to cost, skills, infrastructure, and deployment realities.",
            "local_support": [
                "Implementation is not only technical; it also depends on resources, expertise, maintenance, and organizational readiness.",
                "That practical framing helps the assignment explain why good ideas do not always translate directly into successful use.",
            ],
        },
        "future scope and trends": {
            "weight_label": "moderate",
            "token_multiplier": 0.7,
            "paragraph_delta": 0,
            "prompt_focus": "Keep this forward-looking but grounded in realistic development paths and open questions.",
            "local_support": [
                "The strongest future discussion identifies likely directions of growth while acknowledging uncertainty and unresolved challenges.",
                "It should show why the topic remains relevant for future study instead of relying on vague optimism.",
            ],
        },
        "conclusion": {
            "weight_label": "light",
            "token_multiplier": 0.58,
            "paragraph_delta": -1,
            "prompt_focus": "Keep this section brief but decisive, and end with a strong synthesis rather than new information.",
            "local_support": [
                "A strong conclusion should unite the major points of the assignment and leave the reader with a clear final judgement about the topic.",
            ],
        },
    }
    return section_profiles.get(
        normalized_title,
        {
            "weight_label": "moderate",
            "token_multiplier": 0.72,
            "paragraph_delta": 0,
            "prompt_focus": "Keep the section clear, useful, and academically grounded.",
            "local_support": [
                "This section should connect its ideas clearly to the larger assignment so the discussion feels coherent rather than isolated.",
            ],
        },
    )


def _build_assignment_section_distinction(section_title: str) -> Dict[str, str]:
    normalized_title = str(section_title or "").strip().lower()
    distinctions: Dict[str, Dict[str, str]] = {
        "introduction": {
            "focus": "the scope, relevance, and direction of the assignment",
            "avoid": "detailed theory, long history, or section-by-section analysis",
            "local_boundary": "Its job is to frame the discussion, not to perform the full explanation that belongs in later analytical sections.",
        },
        "background and context": {
            "focus": "the broader field, origins, assumptions, and problem space surrounding the topic",
            "avoid": "full concept definitions, step-by-step mechanism detail, or long application lists",
            "local_boundary": "This section should orient the reader to the setting of the topic rather than define every technical idea or explain the full internal workflow.",
        },
        "historical development": {
            "focus": "the progression of the topic over time and the key turning points in its development",
            "avoid": "deep mechanism explanation or a fresh list of modern applications",
            "local_boundary": "The emphasis here should stay on change over time, not on reteaching theory or expanding into present-day implementation details.",
        },
        "core concepts": {
            "focus": "the main concepts, principles, definitions, and relationships that make the topic understandable",
            "avoid": "background history, a full mechanism walkthrough, or use-case examples",
            "local_boundary": "This section should clarify what the core ideas mean and how they relate, rather than drift back into background narrative or forward into applications.",
        },
        "how it works": {
            "focus": "the internal process, structure, sequence, and mechanism by which the topic operates",
            "avoid": "broad background recap, repeated term definitions, or a shift into an applications section",
            "local_boundary": "The reader should come away understanding the mechanism in motion, not just the surrounding context or the list of real-world uses.",
        },
        "applications": {
            "focus": "real-world adoption, use cases, outcomes, and where the topic creates value",
            "avoid": "a full internal mechanism retelling, repeated theory explanation, or generic strengths without examples",
            "local_boundary": "This section should stay centered on practical use and visible outcomes rather than slipping back into theory or process explanation.",
        },
        "case studies and practical examples": {
            "focus": "specific examples that show how the topic behaves in realistic conditions",
            "avoid": "abstract theory-only discussion or repeating the general applications list",
            "local_boundary": "The goal here is to ground the assignment in examples, not to restate the broader applications section in more general terms.",
        },
        "comparative perspective": {
            "focus": "tradeoffs, contrasts, and best-fit comparisons with relevant alternatives",
            "avoid": "retelling the full background or repeating the basic applications section without evaluation",
            "local_boundary": "This section should evaluate differences and tradeoffs, not just describe the topic again in slightly different words.",
        },
        "advantages and importance": {
            "focus": "why the topic matters and what meaningful strengths it brings",
            "avoid": "a simple feature list, repeated application examples, or promotional language",
            "local_boundary": "The emphasis should be on significance and meaningful strengths, not on repeating use cases or sounding like advocacy.",
        },
        "challenges and limitations": {
            "focus": "the main constraints, weaknesses, barriers, and their practical consequences",
            "avoid": "generic negativity or a repeat of the strengths section with opposite wording",
            "local_boundary": "This section should explain why limitations matter in practice instead of listing drawbacks without analysis.",
        },
        "ethical and social impact": {
            "focus": "the wider human, institutional, fairness, safety, and policy implications of the topic",
            "avoid": "repeating technical mechanism details or collapsing into a general limitations section",
            "local_boundary": "The discussion should stay on broader consequences and stakeholders rather than circling back to purely technical constraints.",
        },
        "implementation considerations": {
            "focus": "deployment realities such as infrastructure, cost, skills, maintenance, and organizational readiness",
            "avoid": "pure theory recap or a duplicate of the mechanism section",
            "local_boundary": "This section should connect the topic to real deployment conditions instead of re-explaining how the mechanism works in theory.",
        },
        "future scope and trends": {
            "focus": "likely future developments, unresolved questions, and emerging directions",
            "avoid": "repeating the current-state applications section or making vague predictions without context",
            "local_boundary": "It should look forward in a grounded way, not simply restate what the topic already does today.",
        },
        "conclusion": {
            "focus": "final synthesis and the central takeaway of the assignment",
            "avoid": "introducing fresh evidence, new arguments, or another full explanation",
            "local_boundary": "A conclusion should unify the assignment rather than reopen sections that were already explained in detail.",
        },
    }
    return distinctions.get(
        normalized_title,
        {
            "focus": "the specific purpose of this section within the larger assignment",
            "avoid": "repeating the surrounding sections in different words",
            "local_boundary": "This section should make a distinct contribution to the assignment instead of echoing nearby sections.",
        },
    )


def _infer_assignment_style(topic: str) -> str:
    normalized = str(topic or "").strip().lower()
    if not normalized:
        return "standard"
    if any(marker in normalized for marker in COMPARISON_MARKERS):
        return "comparative"
    if any(marker in normalized for marker in TECHNICAL_ASSIGNMENT_MARKERS):
        return "technical"
    return "standard"


def _infer_assignment_domain(topic: str, style: str) -> str:
    normalized = str(topic or "").strip().lower()
    if style == "comparative":
        return "comparative"
    if any(marker in normalized for marker in TECHNICAL_ASSIGNMENT_MARKERS):
        return "technical"
    if any(marker in normalized for marker in SOCIAL_ASSIGNMENT_MARKERS):
        return "social"
    return "general"


def _build_assignment_domain_guidance(topic: str, section_kind: str, style: str) -> Dict[str, str]:
    domain = _infer_assignment_domain(topic, style)
    normalized_kind = str(section_kind or "").strip().lower()

    if domain == "technical":
        example_map = {
            "background and context": "When examples help, frame them around technical problem spaces, research development, engineering constraints, or system requirements.",
            "core concepts": "When examples help, use precise references to system components, representations, workflows, abstractions, or model behavior.",
            "how it works": "When examples help, refer to inputs, outputs, data flow, processing stages, architecture, or infrastructure interaction.",
            "applications": "When examples help, use concrete cases such as automation, analytics, software systems, prediction, deployment settings, or operational workflows.",
            "implementation considerations": "When examples help, refer to deployment infrastructure, maintenance, scalability, monitoring, resource cost, or engineering skills.",
        }
        local_map = {
            "background and context": "In a technical topic, the background should connect the subject to system requirements, research development, or engineering constraints rather than staying abstract.",
            "core concepts": "The terminology here should feel technically precise, with attention to components, representations, abstractions, and how the major ideas relate inside a system.",
            "how it works": "A strong technical explanation should make the mechanism feel concrete by referring to data flow, processing stages, architectural roles, or infrastructure interaction.",
            "applications": "Domain-aware examples here should point to automation, analytics, software systems, deployment environments, or operational workflows where the topic creates value.",
        }
        return {
            "domain": domain,
            "prompt_terminology": "Use domain-aware technical terminology such as system components, architecture, data flow, model behavior, deployment, performance, and engineering constraints where relevant.",
            "prompt_examples": example_map.get(normalized_kind, "Use examples and terminology that sound native to technical systems, engineering workflows, and implementation realities."),
            "local_domain_support": local_map.get(normalized_kind, "The wording should remain technically grounded, using examples and terminology that fit systems, engineering workflows, or implementation realities."),
        }

    if domain == "social":
        example_map = {
            "background and context": "When examples help, frame them around communities, institutions, policy environments, historical conditions, or public life.",
            "core concepts": "When examples help, use terminology tied to institutions, social structures, access, inequality, governance, rights, or collective outcomes.",
            "how it works": "When examples help, explain the social mechanism through incentives, institutions, actors, power relations, public behavior, or policy processes.",
            "applications": "When examples help, refer to schools, healthcare systems, workplaces, civic institutions, social programs, or community-level outcomes.",
            "ethical and social impact": "When examples help, discuss fairness, access, rights, stakeholder impact, governance choices, or long-term public consequences.",
        }
        local_map = {
            "background and context": "In a social topic, the background should connect the subject to institutions, communities, policy environments, or historical conditions that shape the issue.",
            "core concepts": "The terminology should feel socially grounded, referring to institutions, stakeholders, inequality, access, governance, rights, or collective outcomes where relevant.",
            "how it works": "A strong social explanation should show how people, institutions, incentives, or policy processes interact rather than treating the topic like a technical pipeline.",
            "applications": "Domain-aware examples here should point to communities, schools, workplaces, healthcare systems, public programs, or civic institutions where real effects are visible.",
        }
        return {
            "domain": domain,
            "prompt_terminology": "Use domain-aware social terminology such as institutions, communities, policy, access, inequality, governance, incentives, rights, and public outcomes where relevant.",
            "prompt_examples": example_map.get(normalized_kind, "Use examples and terminology that feel grounded in institutions, communities, public life, and social consequences."),
            "local_domain_support": local_map.get(normalized_kind, "The wording should remain socially grounded, using examples and terminology that fit institutions, communities, public life, and social consequences."),
        }

    if domain == "comparative":
        example_map = {
            "background and context": "When examples help, frame them around the decision context, evaluation criteria, and why the comparison matters.",
            "core concepts": "When examples help, define the comparison criteria, baseline differences, and terms that make the tradeoffs understandable.",
            "comparative perspective": "When examples help, use side-by-side scenarios that show tradeoffs, alternatives, suitability, and best-fit conditions.",
            "applications": "When examples help, compare which option fits which environment, user need, deployment context, or performance goal.",
        }
        local_map = {
            "background and context": "In a comparison topic, the framing should clarify why these alternatives belong in the same discussion and what criteria make the comparison meaningful.",
            "core concepts": "The terminology should feel evaluative, helping the reader distinguish criteria, tradeoffs, baseline differences, and conditions for best fit.",
            "comparative perspective": "A strong comparative section should sound naturally side-by-side, using alternatives, suitability, tradeoffs, and best-fit conditions rather than generic description.",
            "applications": "Domain-aware examples here should show which option works better in which scenario instead of listing uses without comparative judgment.",
        }
        return {
            "domain": domain,
            "prompt_terminology": "Use comparative terminology such as criteria, tradeoffs, alternatives, suitability, performance, constraints, and best-fit conditions where relevant.",
            "prompt_examples": example_map.get(normalized_kind, "Use examples and terminology that feel natural for comparison, evaluation, alternatives, and tradeoff reasoning."),
            "local_domain_support": local_map.get(normalized_kind, "The wording should remain comparative, using examples and terminology that fit criteria, alternatives, tradeoffs, and best-fit reasoning."),
        }

    return {
        "domain": "general",
        "prompt_terminology": "Use subject-appropriate terminology and examples where they help the reader understand the topic clearly.",
        "prompt_examples": "Keep the examples concrete and relevant to the topic instead of relying on vague general statements.",
        "local_domain_support": "The wording should stay aligned with the topic itself, using concrete examples and terminology where they improve clarity.",
    }


def _resolve_assignment_section_depth(section_title: str, page_target: Optional[int]) -> Dict[str, Any]:
    depth_profile = _build_assignment_depth_profile(page_target)
    weight_profile = _build_assignment_section_weight(section_title)
    distinction_profile = _build_assignment_section_distinction(section_title)

    paragraph_target = max(
        1,
        min(
            int(depth_profile["paragraph_ceiling"]),
            int(depth_profile["base_paragraph_target"]) + int(weight_profile["paragraph_delta"]),
        ),
    )
    token_budget = max(
        240,
        min(
            int(depth_profile["max_tokens"]),
            int(round(int(depth_profile["max_tokens"]) * float(weight_profile["token_multiplier"]))),
        ),
    )

    return {
        "band": depth_profile["band"],
        "weight_label": weight_profile["weight_label"],
        "paragraph_target": paragraph_target,
        "token_budget": token_budget,
        "temperature": float(depth_profile["temperature"]),
        "depth_guidance": str(depth_profile["depth_guidance"]).strip(),
        "prompt_focus": str(weight_profile["prompt_focus"]).strip(),
        "local_support": list(weight_profile.get("local_support") or []),
        "distinct_focus": str(distinction_profile["focus"]).strip(),
        "distinct_avoid": str(distinction_profile["avoid"]).strip(),
        "local_boundary": str(distinction_profile["local_boundary"]).strip(),
    }


def _build_assignment_section_plan(topic: str, page_target: Optional[int] = None) -> List[Dict[str, str]]:
    normalized_pages = _normalize_assignment_page_target(page_target)
    style = _infer_assignment_style(topic)

    def make_section(kind: str, title: str, purpose: str) -> Dict[str, str]:
        return {"kind": kind, "title": title, "purpose": purpose, "style": style}

    if style == "comparative":
        sections: List[Dict[str, str]] = [
            make_section("introduction", "Introduction", "Introduce the comparison, why it matters, and what the assignment will evaluate."),
            make_section("background and context", "Background", "Frame the broader context, decision environment, and why these topics belong in the same comparison without turning this section into a full analysis."),
            make_section("core concepts", "Key Criteria and Core Differences", "Define the main criteria, concepts, and baseline differences clearly before deeper evaluation begins."),
            make_section("comparative perspective", "Comparative Analysis", "Evaluate the most important differences, tradeoffs, and best-fit conditions instead of repeating basic definitions."),
            make_section("applications", "Applications", "Show where each side of the comparison is most useful in practice without re-running the full comparison logic."),
            make_section("advantages and importance", "Relative Strengths", "Present the strongest advantages of each side and why they matter."),
            make_section("challenges and limitations", "Challenges", "Explain practical weaknesses, limitations, and adoption tradeoffs."),
        ]

        if normalized_pages and normalized_pages >= 4:
            sections.insert(2, make_section("historical development", "Historical Development", "Summarize how each side of the comparison developed over time."))
            sections.append(make_section("case studies and practical examples", "Illustrative Examples", "Use practical examples to show where the comparison becomes clearer."))

        if normalized_pages and normalized_pages >= 7:
            sections.append(make_section("future scope and trends", "Future Outlook and Trends", "Explain how the comparison may shift as tools, methods, or needs evolve."))

        if normalized_pages and normalized_pages >= 10:
            sections.append(make_section("implementation considerations", "Adoption and Implementation Considerations", "Explain what real-world implementation or adoption looks like for each side."))
            sections.append(make_section("ethical and social impact", "Broader Social and Ethical Impact", "Discuss wider consequences, fairness, access, or policy implications where relevant."))

        sections.append(make_section("conclusion", "Conclusion", "Conclude the comparison with a clear final judgement and best-fit summary."))
        return sections

    if style == "technical":
        sections = [
            make_section("introduction", "Introduction", "Introduce the topic, its importance, and the direction of the assignment."),
            make_section("background and context", "Background", "Explain the technical field, origins, and problem space around the topic without moving into full definitions or mechanism detail."),
            make_section("core concepts", "Core Concepts", "Define the main ideas, terms, and foundational relationships clearly before the assignment moves into mechanism or use cases."),
            make_section("how it works", "Architecture and Mechanism", "Explain the structure, internal mechanism, or workflow step by step without drifting back into background or forward into use-case discussion."),
            make_section("applications", "Applications", "Describe real-world uses, adoption areas, and outcomes without re-explaining the mechanism in full."),
            make_section("advantages and importance", "Advantages and Importance", "Explain the main strengths, benefits, and academic importance."),
            make_section("challenges and limitations", "Challenges", "Present key limitations, risks, costs, or implementation barriers."),
        ]

        if normalized_pages and normalized_pages >= 4:
            sections.insert(2, make_section("historical development", "Historical Development", "Summarize how the topic developed or evolved over time."))
            sections.append(make_section("case studies and practical examples", "Case Studies and Practical Examples", "Add concrete examples or realistic use cases that ground the discussion."))

        if normalized_pages and normalized_pages >= 7:
            sections.append(make_section("ethical and social impact", "Ethical and Social Impact", "Discuss wider effects on people, society, fairness, safety, or policy."))
            sections.append(make_section("future scope and trends", "Future Scope and Trends", "Explain likely future directions, open problems, and upcoming developments."))

        if normalized_pages and normalized_pages >= 10:
            sections.insert(-2, make_section("implementation considerations", "Implementation Considerations", "Discuss resources, infrastructure, skills, cost, and deployment considerations."))
            sections.append(make_section("comparative perspective", "Comparative Perspective", "Compare the topic with related methods, systems, or alternatives."))

        sections.append(make_section("conclusion", "Conclusion", "Conclude the assignment by restating the central idea and final significance."))
        return sections

    sections = [
        make_section("introduction", "Introduction", "Introduce the topic, its importance, and the direction of the assignment."),
        make_section("background and context", "Background", "Explain the context, origins, or broader field around the topic without turning this section into a full theory or mechanism discussion."),
        make_section("core concepts", "Core Concepts", "Define the main ideas, terms, and foundational concepts clearly before the assignment moves into process or application."),
        make_section("how it works", "How It Works", "Explain the process, structure, or mechanism step by step without repeating the broader background or drifting into use cases."),
        make_section("applications", "Applications", "Describe real-world uses, adoption areas, or practical relevance without re-teaching the mechanism."),
        make_section("advantages and importance", "Advantages and Importance", "Explain the main strengths, benefits, and academic importance."),
        make_section("challenges and limitations", "Challenges", "Present key limitations, risks, costs, or implementation barriers."),
    ]

    if normalized_pages and normalized_pages >= 4:
        sections.insert(2, make_section("historical development", "Historical Development", "Summarize how the topic developed or evolved over time."))
        sections.append(make_section("case studies and practical examples", "Case Studies and Practical Examples", "Add concrete examples or realistic use cases that ground the discussion."))

    if normalized_pages and normalized_pages >= 7:
        sections.append(make_section("ethical and social impact", "Ethical and Social Impact", "Discuss wider effects on people, society, fairness, safety, or policy."))
        sections.append(make_section("future scope and trends", "Future Scope and Trends", "Explain likely future directions, open problems, and upcoming developments."))

    if normalized_pages and normalized_pages >= 10:
        sections.append(make_section("implementation considerations", "Implementation Considerations", "Discuss resources, infrastructure, skills, cost, and deployment considerations."))
        sections.append(make_section("comparative perspective", "Comparative Perspective", "Compare the topic with related methods, systems, or alternatives."))

    sections.append(make_section("conclusion", "Conclusion", "Conclude the assignment by restating the central idea and final significance."))
    return sections


def _build_local_assignment_section_body(
    topic: str,
    section_kind: str,
    page_target: Optional[int] = None,
    *,
    display_title: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    title_topic = topic.title()
    normalized_title = str(section_kind or "").strip().lower()
    visible_title = str(display_title or section_kind or "").strip() or "Section"
    section_depth = _resolve_assignment_section_depth(section_kind, page_target)
    assignment_style = _infer_assignment_style(topic)
    domain_guidance = _build_assignment_domain_guidance(topic, section_kind, assignment_style)
    document_style = normalize_document_style(style)
    page_hint = ""  # never append meta-instructions to document output

    templates = {
        "introduction": (
            f"{title_topic} is a significant area of academic and practical study that has grown in relevance across multiple disciplines. "
            f"It encompasses a broad range of concepts, methods, and applications that continue to shape how problems are understood and addressed in both research and professional contexts. "
            f"This assignment examines the core dimensions of {topic}, tracing its development, principles, real-world uses, and the key debates surrounding its adoption and impact.{page_hint}"
        ),
        "background and context": (
            f"{title_topic} emerged from foundational work in its parent disciplines, driven by growing demand for more effective methods of understanding and solving complex problems. "
            f"The broader academic and institutional context in which {topic} developed includes contributions from early theorists, landmark studies, and cross-disciplinary collaboration. "
            f"Situating {topic} within this wider environment reveals why it gained traction and how it continues to evolve in response to new challenges.{page_hint}"
        ),
        "historical development": (
            f"The history of {topic} reflects a trajectory of incremental refinement and occasional paradigm shifts that transformed how practitioners and researchers approach its core challenges. "
            f"Early frameworks established the conceptual vocabulary and baseline models; subsequent decades brought empirical validation, methodological diversification, and expanded application domains. "
            f"Tracing this progression reveals how the field responded to criticism, absorbed new evidence, and adapted to changes in technology, society, and disciplinary norms.{page_hint}"
        ),
        "core concepts": (
            f"The foundational concepts of {topic} provide the analytical framework necessary for engaging with the subject at an academic level. "
            f"Key terms, definitions, and structural principles form the vocabulary through which practitioners describe, measure, and evaluate phenomena in this domain. "
            f"Understanding these concepts in relation to each other — rather than in isolation — is essential for applying {topic} accurately and critically in research or professional contexts.{page_hint}"
        ),
        "how it works": (
            f"{title_topic} operates through a structured process that transforms inputs into outputs via a defined set of operations, rules, or mechanisms. "
            f"The internal workflow typically involves distinct stages such as data collection, analysis, processing, decision-making, and output generation, each governed by the principles specific to the field. "
            f"A precise understanding of this mechanism clarifies both the capabilities and the boundaries of {topic} in real-world implementation.{page_hint}"
        ),
        "applications": (
            f"{title_topic} has been successfully adopted across a wide range of sectors including technology, healthcare, education, finance, engineering, and public policy. "
            f"In each domain, its application has enabled more accurate analysis, improved decision-making, greater operational efficiency, or novel solutions to longstanding problems. "
            f"These real-world implementations demonstrate the practical value of {topic} and illustrate why investment in its development has accelerated in recent decades.{page_hint}"
        ),
        "advantages and importance": (
            f"The primary strengths of {topic} lie in its capacity to provide systematic, evidence-based approaches to complex problems that resist simpler methods of analysis or intervention. "
            f"It offers meaningful advantages in terms of scalability, reproducibility, and depth of insight, making it a preferred framework in academic research and applied professional settings. "
            f"Its continued importance reflects the growing recognition that {title_topic} addresses challenges that are not only persistent but increasingly central to how modern organisations and institutions function.{page_hint}"
        ),
        "challenges and limitations": (
            f"Despite its strengths, {topic} faces significant practical and theoretical constraints that limit its universal applicability. "
            f"Common challenges include high implementation costs, computational or resource demands, sensitivity to data quality, and the expertise required to deploy and maintain systems effectively. "
            f"Theoretical limitations — such as assumptions that may not hold across all contexts, or the difficulty of interpreting complex outputs — further constrain the scope in which {title_topic} can be applied without risk of error or misuse.{page_hint}"
        ),
        "case studies and practical examples": (
            f"Examining specific instances of {topic} in practice provides concrete evidence of both its potential and its performance under real-world conditions. "
            f"Case studies from industry and academia illustrate how theoretical principles translate into operational decisions, reveal unexpected implementation challenges, and highlight the conditions under which {title_topic} delivers the strongest results. "
            f"These examples ground the discussion in observable outcomes and allow for more rigorous evaluation of the subject's overall effectiveness.{page_hint}"
        ),
        "ethical and social impact": (
            f"The deployment of {topic} raises important questions about fairness, accountability, privacy, access, and the distribution of its benefits and risks across different populations and communities. "
            f"Ethical concerns include potential biases embedded in data or design decisions, the concentration of capability in well-resourced organisations, and the challenge of ensuring transparent and explainable outcomes. "
            f"Addressing these dimensions is essential not only for responsible practice but also for maintaining public trust in {title_topic} as it becomes more deeply integrated into institutional and social infrastructure.{page_hint}"
        ),
        "future scope and trends": (
            f"The future development of {topic} is shaped by advances in underlying technologies, evolving research priorities, and the expanding range of problems to which the field is being applied. "
            f"Emerging directions include greater automation, improved interpretability, interdisciplinary integration, and the scaling of successful methods to address larger and more complex challenges. "
            f"Open questions remain around robustness, generalisation, and equitable access, suggesting that the field will continue to attract critical examination alongside technical progress.{page_hint}"
        ),
        "implementation considerations": (
            f"Deploying {topic} in practice requires careful attention to infrastructure, workforce skills, data governance, cost management, and ongoing maintenance. "
            f"Organisations that have successfully implemented {title_topic} typically invest in both technical capability and the organisational processes needed to manage, interpret, and act on outputs responsibly. "
            f"Implementation barriers — including legacy systems, skills gaps, regulatory constraints, and change management challenges — must be addressed systematically to realise the full potential of the approach.{page_hint}"
        ),
        "comparative perspective": (
            f"Placing {topic} in comparative context reveals where it excels relative to alternatives and where other methods or frameworks may be better suited. "
            f"Comparative analysis considers criteria such as performance, cost, accessibility, interpretability, and suitability for specific problem types. "
            f"This perspective is valuable for decision-makers who must choose between {title_topic} and competing approaches in constrained or specialised environments.{page_hint}"
        ),
        "conclusion": (
            f"This assignment has examined {topic} across its historical development, conceptual foundations, operational mechanisms, practical applications, and critical limitations. "
            f"The evidence presented demonstrates that {title_topic} occupies a significant and growing role in its field, valued for its ability to address complex challenges systematically and at scale. "
            f"As the field continues to evolve, ongoing engagement with both its potential and its constraints will be essential for responsible and effective application.{page_hint}"
        ),
    }
    return templates.get(
        normalized_title,
        f"{title_topic} represents an important dimension of the broader subject, contributing to a more complete and analytically grounded understanding of {topic} and its place in academic and applied contexts.",
    )


def _build_local_assignment_content(
    topic: str,
    page_target: Optional[int] = None,
    *,
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
) -> str:
    section_blocks = []
    for section in _build_assignment_section_plan(topic, page_target):
        section_blocks.append(
            f"{section['title']}\n{_build_local_assignment_section_body(topic, section['kind'], page_target, display_title=section['title'], style=style)}"
        )
    content = clean_response("\n\n".join(section_blocks))
    if include_references:
        content = _append_references_section(content, topic, citation_style)
    return content


def _build_assignment_section_prompt(
    topic: str,
    section_kind: str,
    section_title: str,
    section_purpose: str,
    page_target: Optional[int],
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
) -> str:
    section_depth = _resolve_assignment_section_depth(section_kind, page_target)
    assignment_style = _infer_assignment_style(topic)
    domain_guidance = _build_assignment_domain_guidance(topic, section_kind, assignment_style)
    document_style = normalize_document_style(style)
    page_hint = (
        f"The full assignment should feel deep enough for about {page_target} pages, so write this section with solid academic depth."
        if page_target
        else "Write this section with clear academic depth."
    )
    style_hint = _build_document_style_guidance("assignment", document_style)
    references_hint = (
        f" The full assignment will include a references section in basic {normalize_citation_style(citation_style).upper() if normalize_citation_style(citation_style) else 'academic'} style."
        if include_references
        else ""
    )
    return (
        f"Write only the '{section_title}' section for an assignment on {topic}. "
        f"Purpose: {section_purpose} "
        f"{page_hint} "
        f"{style_hint} "
        f"Section weight: {section_depth['weight_label']}. "
        f"{section_depth['depth_guidance']} "
        f"{section_depth['prompt_focus']} "
        f"Focus on {section_depth['distinct_focus']}. "
        f"Do not repeat {section_depth['distinct_avoid']}. "
        f"{domain_guidance['prompt_terminology']} "
        f"{domain_guidance['prompt_examples']} "
        f"{references_hint} "
        f"Start with the exact heading '{section_title}' on its own line, then provide {section_depth['paragraph_target']} coherent paragraphs. "
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


def _generate_assignment_chunked_content_payload(
    topic: str,
    page_target: Optional[int],
    *,
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_pages = _normalize_assignment_page_target(page_target)
    section_plan = _build_assignment_section_plan(topic, normalized_pages)
    combined_sections: List[str] = []
    providers_tried: List[Any] = []
    provider_name: Optional[str] = None
    provider_model: Optional[str] = None
    used_provider = False
    degraded = False

    for section in section_plan:
        section_depth = _resolve_assignment_section_depth(section["kind"], normalized_pages)
        payload = generate_response_payload(
            _build_assignment_section_prompt(
                topic,
                section["kind"],
                section["title"],
                section["purpose"],
                normalized_pages,
                style=style,
                include_references=include_references,
                citation_style=citation_style,
            ),
            system_override=DOCUMENT_ASSIGNMENT_PROMPT,
            max_tokens=int(section_depth["token_budget"]),
            temperature=float(section_depth["temperature"]),
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
            f"{section['title']}\n{_build_local_assignment_section_body(topic, section['kind'], normalized_pages, display_title=section['title'], style=style)}"
        )

    source = "provider_chunked"
    if degraded and used_provider:
        source = "mixed_chunked"
    elif not used_provider:
        source = "local_template"

    content = clean_response("\n\n".join(combined_sections))
    if include_references:
        content = _append_references_section(content, topic, citation_style)

    return {
        "success": True,
        "content": content,
        "provider": provider_name if used_provider else "local",
        "model": provider_model if used_provider else "template",
        "source": source,
        "degraded": degraded or not used_provider,
        "providers_tried": providers_tried,
        "error": None if used_provider else "Provider content was unavailable for chunked assignment generation.",
    }


def _build_document_generation_prompt(
    document_type: str,
    topic: str,
    page_target: Optional[int],
    *,
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
) -> str:
    style_guidance = _build_document_style_guidance(document_type, style)
    references_hint = (
        f" Include a final References section using basic {normalize_citation_style(citation_style).upper() if normalize_citation_style(citation_style) else 'academic'} style."
        if include_references
        else ""
    )
    if document_type == "notes":
        return (
            f"Create study notes on: {topic}. "
            f"Sections required: Overview, History, Core Concepts, How It Works, Applications, Advantages, Limitations, Quick Summary. "
            f"Write actual facts about {topic} under every section — not instructions or meta-commentary. "
            f"{style_guidance}{references_hint}"
        )
    page_hint = f" Aim for enough detail to support about {page_target} pages." if page_target else ""
    return (
        f"Write an academic assignment on: {topic}.{page_hint} "
        f"Sections required: Introduction, Background and History, Core Concepts, How It Works, Applications, Advantages and Importance, Challenges and Limitations, Conclusion. "
        f"Write real, specific academic content about {topic} in every section. "
        f"{style_guidance}{references_hint} "
        "Start directly with 'Introduction'. No title, no table of contents, no numbered headings. "
        "Use plain-text headings only — no markdown, no bold, no symbols."
    )


def generate_document_content_payload(
    document_type: str,
    topic: str,
    *,
    page_target: Optional[int] = None,
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
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

    normalized_style = normalize_document_style(style)
    normalized_citation_style = normalize_citation_style(citation_style)
    normalized_pages = _normalize_assignment_page_target(page_target)
    if normalized_type == "assignment" and normalized_pages is None and normalized_style == "detailed":
        normalized_pages = 4
    if normalized_type == "assignment" and normalized_pages and normalized_pages >= 4:
        return _generate_assignment_chunked_content_payload(
            normalized_topic,
            normalized_pages,
            style=normalized_style,
            include_references=include_references,
            citation_style=normalized_citation_style,
        )

    system_prompt = DOCUMENT_NOTES_PROMPT if normalized_type == "notes" else DOCUMENT_ASSIGNMENT_PROMPT
    prompt = _build_document_generation_prompt(
        normalized_type,
        normalized_topic,
        normalized_pages,
        style=normalized_style,
        include_references=include_references,
        citation_style=normalized_citation_style,
    )
    max_tokens = 1500 if normalized_type == "notes" else 2600
    if normalized_style == "detailed":
        max_tokens += 300 if normalized_type == "assignment" else 180
    elif normalized_style == "simple":
        max_tokens -= 180 if normalized_type == "assignment" else 120
    payload = generate_response_payload(
        prompt,
        system_override=system_prompt,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    content = clean_response(payload.get("content"))
    if payload.get("success") and is_meaningful_text(content):
        if include_references:
            content = _append_references_section(content, normalized_topic, normalized_citation_style)
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
        _build_local_notes_content(
            normalized_topic,
            style=normalized_style,
            include_references=include_references,
            citation_style=normalized_citation_style,
        )
        if normalized_type == "notes"
        else _build_local_assignment_content(
            normalized_topic,
            normalized_pages,
            style=normalized_style,
            include_references=include_references,
            citation_style=normalized_citation_style,
        )
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


def generate_transformation_content_payload(
    source_text: str,
    document_type: str,
    topic: str,
    *,
    page_target: Optional[int] = None,
    style: Optional[str] = None,
    include_references: bool = False,
    citation_style: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Dict[str, Any]:
    """Transform extracted source text into structured document content via LLM."""
    normalized_type = str(document_type or "notes").strip().lower()
    if normalized_type not in {"notes", "assignment"}:
        normalized_type = "notes"

    normalized_style = normalize_document_style(style)
    normalized_citation = normalize_citation_style(citation_style)
    style_guidance = _build_document_style_guidance(normalized_type, normalized_style)
    page_hint = f" Aim for approximately {page_target} pages of content." if page_target else ""

    truncated = source_text[:6000] if len(source_text) > 6000 else source_text

    if normalized_type == "notes":
        system_prompt = TRANSFORMATION_NOTES_PROMPT
        prompt = (
            f"Topic: {topic}\n"
            f"Task: Convert the source material below into professional structured study notes.\n"
            f"Style: {style_guidance}{page_hint}\n"
            f"Important: Use only information present in the source. Begin with the topic title "
            f"then organize under clear section headings with bullet points.\n\n"
            f"SOURCE MATERIAL:\n{truncated}"
        )
        tokens = 1800
    else:
        system_prompt = TRANSFORMATION_ASSIGNMENT_PROMPT
        prompt = (
            f"Topic: {topic}\n"
            f"Task: Convert the source material below into a structured academic assignment.\n"
            f"Style: {style_guidance}{page_hint}\n"
            f"Important: Use information from the source as your foundation. Write in formal "
            f"academic prose with clear section headings. Do not open with 'In this assignment'.\n\n"
            f"SOURCE MATERIAL:\n{truncated}"
        )
        tokens = 2800

    if normalized_style == "detailed":
        tokens += 300
    elif normalized_style == "simple":
        tokens = max(tokens - 200, 600)

    payload = generate_response_payload(
        prompt,
        system_override=system_prompt,
        max_tokens=min(tokens, max_tokens),
        temperature=0.4,
    )

    content = clean_response(payload.get("content"))
    if payload.get("success") and is_meaningful_text(content):
        if include_references:
            content = _append_references_section(content, topic, normalized_citation)
        return {
            "success": True,
            "content": content,
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "source": "transformation",
            "degraded": False,
            "providers_tried": list(payload.get("providers_tried") or []),
            "error": None,
        }

    fallback_content = source_text[:4000].strip()
    if include_references:
        fallback_content = _append_references_section(fallback_content, topic, normalized_citation)
    return {
        "success": False,
        "content": fallback_content,
        "provider": "local",
        "model": "passthrough",
        "source": "transformation_fallback",
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

    providers_tried = payload.get("providers_tried") or []
    print(
        f"[RESPONSE ENGINE] All providers failed or returned empty content. "
        f"providers_tried={providers_tried}  "
        f"error={payload.get('error')!r}  "
        f"input={repr(user_input[:80])}"
    )
    payload["degraded_reply"] = build_degraded_reply(user_input=user_input, providers_tried=providers_tried)
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
    print(
        f"[RESPONSE ENGINE] get_ai_response returning FALLBACK. "
        f"success={payload.get('success')}  error={payload.get('error')!r}  "
        f"input={repr(str(user_input)[:80])}"
    )
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
    user_input_repr = repr(str(user_input_or_messages)[:80]) if isinstance(user_input_or_messages, str) else repr(f"<{len(user_input_or_messages)} messages>")
    print(
        f"[RESPONSE ENGINE] generate_response returning FALLBACK. "
        f"success={payload.get('success')}  error={payload.get('error')!r}  "
        f"input={user_input_repr}"
    )
    return FALLBACK_USER_MESSAGE


def get_provider_summary() -> Dict[str, object]:
    return summarize_provider_statuses(fresh=True)
