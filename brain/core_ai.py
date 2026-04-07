import datetime
from brain.intent_engine import detect_intent
from brain.response_engine import generate_response
from memory.knowledge_base import (
    store_user_name, get_user_name,
    store_user_age, get_user_age,
    store_user_city, get_user_city,
    store_info, get_info
)

def process_command(command):

    command_lower = command.lower()

    # Remember name
    if "my name is" in command_lower:
        name = command_lower.replace("my name is", "").strip()
        store_user_name(name)
        return "memory", f"Nice to meet you {name}! I will remember your name."

    # Recall name
    if "what is my name" in command_lower or "what's my name" in command_lower:
        name = get_user_name()
        if name:
            return "memory", f"Your name is {name}."
        return "memory", "I don't know your name yet. Tell me by saying 'my name is ...'"

    # Remember age
    if "my age is" in command_lower:
        age = command_lower.replace("my age is", "").strip()
        store_user_age(age)
        return "memory", f"Got it! I will remember that you are {age} years old."

    # Recall age
    if "what is my age" in command_lower or "how old am i" in command_lower:
        age = get_user_age()
        if age:
            return "memory", f"You are {age} years old."
        return "memory", "I don't know your age yet. Tell me by saying 'my age is ...'"

    # Remember city
    if "i live in" in command_lower:
        city = command_lower.replace("i live in", "").strip()
        store_user_city(city)
        return "memory", f"Got it! I will remember that you live in {city}."

    # Recall city
    if "where do i live" in command_lower:
        city = get_user_city()
        if city:
            return "memory", f"You live in {city}."
        return "memory", "I don't know where you live yet. Tell me by saying 'I live in ...'"

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