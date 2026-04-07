def detect_intent(command):
    command = command.lower()

    if any(word in command for word in ["time", "clock"]):
        return "time"

    if any(word in command for word in ["date", "today"]):
        return "date"

    if any(word in command for word in ["hello", "hi", "hey"]):
        return "greeting"

    if any(word in command for word in ["bye", "exit", "quit", "shutdown"]):
        return "shutdown"

    if any(word in command for word in ["your name", "who are you"]):
        return "identity"

    if any(word in command for word in ["weather"]):
        return "weather"

    if any(word in command for word in ["joke"]):
        return "joke"

    if any(word in command for word in ["study", "explain", "teach", "learn"]):
        return "study"

    if any(word in command for word in ["research", "search", "find", "look up"]):
        return "research"

    if any(word in command for word in ["code", "program", "debug", "fix", "write code"]):
        return "code"

    return "general"