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

    return "general"