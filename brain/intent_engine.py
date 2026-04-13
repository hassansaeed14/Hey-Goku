import re

COMMON_CURRENCY_CODES = {
    "AED", "AUD", "BDT", "CAD", "CHF", "CNY", "EUR", "GBP", "HKD", "INR",
    "JPY", "KRW", "NOK", "NZD", "PKR", "SAR", "SEK", "SGD", "TRY", "USD",
}

CASUAL_CONVERSATION_PHRASES = (
    "how are you",
    "how are you doing",
    "what is up",
    "whats up",
    "what's up",
    "are you there",
    "good morning",
    "good afternoon",
    "good evening",
    "nice to meet you",
    "good to see you",
)

TOOL_HINT_PHRASES = (
    "convert",
    "exchange",
    "rate",
    "calculate",
    "solve",
    "search",
    "google",
    "translate",
    "remind me",
    "task",
    "todo",
    "weather",
    "news",
    "youtube",
    "open file",
    "read file",
)


# -----------------------------
# Normalization (NEW - IMPORTANT)
# -----------------------------

def normalize_text(text: str) -> str:
    text = text.lower().strip()

    # remove filler words
    text = re.sub(r"\b(please|kindly|just|can you|could you|i want to)\b", "", text)

    # normalize spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# -----------------------------
# Helpers
# -----------------------------

def _has_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def _score_match(text, phrases, starts_with=False, whole_match=False):
    score = 0

    for phrase in phrases:
        if whole_match and text == phrase:
            score += 4
        elif starts_with and text.startswith(phrase):
            score += 3
        elif phrase in text:
            score += 1

    return score


def _has_math_expression(text):
    pattern = r"^\s*[\d\.\+\-\*\/\(\)\s%]+$"
    return bool(re.match(pattern, text))


def _has_number(text):
    return any(char.isdigit() for char in text)


def _has_currency_code(text):
    codes = re.findall(r"\b[A-Z]{3}\b", text.upper())
    codes = [code for code in codes if code in COMMON_CURRENCY_CODES]
    if len(set(codes)) < 2:
        return False

    lowered = text.lower()
    return (
        any(keyword in lowered for keyword in ("convert", "exchange", "rate", "currency"))
        or " to " in lowered
        or " from " in lowered
        or _has_number(text)
    )


def _is_casual_conversation(text: str) -> bool:
    lowered = normalize_text(text)
    if lowered in {"hi", "hello", "hey", "hello aura", "hi aura", "hey aura"}:
        return True
    if any(phrase in lowered for phrase in CASUAL_CONVERSATION_PHRASES):
        return not any(hint in lowered for hint in TOOL_HINT_PHRASES)
    return False


# -----------------------------
# Intent Detection
# -----------------------------

def detect_intent_with_confidence(command: str):
    if not command:
        return "general", 0.0

    text = normalize_text(command)
    words = text.split()

    if len(text) < 2:
        return "general", 0.0

    if text in {"hi", "hello", "hey", "hello aura", "hi aura", "hey aura"}:
        return "greeting", 0.95

    if _is_casual_conversation(text):
        return "general", 0.82

    scores = {}

    def add(intent, value):
        if value > 0:
            scores[intent] = scores.get(intent, 0) + value

    # -----------------------------
    # Core Intents
    # -----------------------------

    add("greeting", _score_match(text, [
        "hi", "hello", "hey", "hey aura", "hi aura"
    ], whole_match=True))

    add("shutdown", _score_match(text, [
        "bye", "goodbye", "exit", "quit"
    ]))

    add("identity", _score_match(text, [
        "who are you", "your name"
    ]))

    add("dictionary", _score_match(text, [
        "define", "meaning"
    ], starts_with=True))

    translation_score = _score_match(text, [
        "translate", "how to say"
    ], starts_with=True)
    if "translate" in text:
        translation_score += 2
    add("translation", translation_score)

    add("weather", _score_match(text, [
        "weather", "temperature", "forecast"
    ]))

    add("news", _score_match(text, [
        "news", "headlines"
    ]))

    # -----------------------------
    # Smart Detection
    # -----------------------------

    if _has_currency_code(text):
        add("currency", 4)

    if _has_math_expression(text):
        add("math", 5)

    elif _has_any(text, ["calculate", "solve"]) and _has_number(text):
        add("math", 3)

    # -----------------------------
    # Productivity
    # -----------------------------

    add("email", _score_match(text, ["write email"]))
    add("content", _score_match(text, ["write blog", "write article"]))
    add("grammar", _score_match(text, ["check grammar"]))
    add("summarize", _score_match(text, ["summarize"]))
    add("quiz", _score_match(text, ["quiz", "test me"]))
    add("task", _score_match(text, ["task", "todo"]))
    add("reminder", _score_match(text, ["remind me"]))

    # -----------------------------
    # System / Integration
    # -----------------------------

    add("web_search", _score_match(text, ["search", "google"]))
    add("youtube", _score_match(text, ["youtube", "video"]))
    add("file", _score_match(text, ["open file", "read file"]))
    add("list_files", _score_match(text, ["list files"]))
    screenshot_score = _score_match(text, ["screenshot", "take a screenshot", "capture screen"])
    if "screenshot" in text:
        screenshot_score += 2
    add("screenshot", screenshot_score)
    add("compare", _score_match(text, ["compare"]))
    add("code", _score_match(text, ["code", "debug"]))
    add("study", _score_match(text, ["explain", "teach"]))
    add("research", _score_match(text, ["research", "analyze"]))
    add("purchase", _score_match(text, ["buy", "purchase"]))

    # -----------------------------
    # Time / Date
    # -----------------------------

    if len(words) <= 6 and _has_any(text, ["time"]):
        add("time", 3)

    if len(words) <= 6 and _has_any(text, ["date"]):
        add("date", 3)

    # -----------------------------
    # Final Decision
    # -----------------------------

    if not scores:
        return "general", 0.0

    sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    best_intent, best_score = sorted_intents[0]

    # Ambiguity protection
    if len(sorted_intents) > 1:
        second_score = sorted_intents[1][1]
        if best_score - second_score <= 1:
            return "general", 0.3

    confidence = min(1.0, best_score / 5.0)

    # Hard alignment with decision engine
    if confidence < 0.35:
        return "general", confidence

    return best_intent, confidence


def detect_intent(command: str):
    intent, confidence = detect_intent_with_confidence(command)

    if confidence < 0.35:
        return "general"

    return intent
