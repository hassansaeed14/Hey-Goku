import datetime
from brain.intent_engine import detect_intent
from brain.response_engine import generate_response
from memory.knowledge_base import store_user_name, get_user_name

def process_command(command):

    command_lower = command.lower()

    # Remember user name
    if "my name is" in command_lower:
        name = command_lower.replace("my name is", "").strip()
        store_user_name(name)
        return "memory", f"Nice to meet you {name}! I will remember your name."

    # Recall user name
    if "what is my name" in command_lower or "what's my name" in command_lower:
        name = get_user_name()
        if name:
            return "memory", f"Your name is {name}."
        else:
            return "memory", "I don't know your name yet. Tell me by saying 'my name is ...'"

    # Detect intent
    intent = detect_intent(command)

    # Time
    if intent == "time":
        now = datetime.datetime.now().strftime("%H:%M:%S")
        return intent, f"The current time is {now}"

    # Date
    if intent == "date":
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return intent, f"Today is {today}"

    # Greeting
    if intent == "greeting":
        name = get_user_name()
        if name:
            return intent, f"Hello {name}! How can I help you today?"
        return intent, "Hello! How can I help you today?"

    # Identity
    if intent == "identity":
        return intent, "I am Hey Goku, your personal AI assistant!"

    # Shutdown
    if intent == "shutdown":
        return intent, "Goodbye! Shutting down Hey Goku."

    # General — use Groq AI
    response = generate_response(command)
    return intent, response