import datetime
from brain.intent_engine import detect_intent
from brain.response_engine import generate_response
from memory.knowledge_base import (
    store_user_name, get_user_name,
    store_user_age, get_user_age,
    store_user_city, get_user_city,
    store_info, get_info
)
from agents.study_agent import study
from agents.research_agent import research
from agents.coding_agent import code_help

def process_command(command):

    command_lower = command.lower()

    if "my name is" in command_lower:
        name = command_lower.replace("my name is", "").strip()
        store_user_name(name)
        return "memory", f"Nice to meet you {name}! I will remember your name."

    if "what is my name" in command_lower or "what's my name" in command_lower:
        name = get_user_name()
        if name:
            return "memory", f"Your name is {name}."
        return "memory", "I don't know your name yet. Tell me by saying 'my name is ...'"

    if "my age is" in command_lower:
        age = command_lower.replace("my age is", "").strip()
        store_user_age(age)
        return "memory", f"Got it! I will remember that you are {age} years old."

    if "what is my age" in command_lower or "how old am i" in command_lower:
        age = get_user_age()
        if age:
            return "memory", f"You are {age} years old."
        return "memory", "I don't know your age yet. Tell me by saying 'my age is ...'"

    # Urdu memory commands
    if "میرا نام" in command and "ہے" in command:
        name = command.replace("میرا نام", "").replace("ہے", "").strip()
        store_user_name(name)
        return "memory", f"ٹھیک ہے! میں آپ کا نام {name} یاد رکھوں گا۔"

    if "میرا نام کیا ہے" in command:
        name = get_user_name()
        if name:
            return "memory", f"آپ کا نام {name} ہے۔"
        return "memory", "مجھے ابھی تک آپ کا نام معلوم نہیں۔ بتائیں کہ آپ کا نام کیا ہے؟"

    if "وقت کیا ہے" in command or "ٹائم" in command:
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        return "time", f"ابھی وقت {now} ہے۔"

    if "السلام علیکم" in command or "ہیلو" in command:
        name = get_user_name()
        if name:
            return "greeting", f"وعلیکم السلام {name}! میں آپ کی کیا مدد کر سکتا ہوں؟"
        return "greeting", "وعلیکم السلام! میں آپ کی کیا مدد کر سکتا ہوں؟"
    
    if "i live in" in command_lower:
        city = command_lower.replace("i live in", "").strip()
        store_user_city(city)
        return "memory", f"Got it! I will remember that you live in {city}."

    if "where do i live" in command_lower:
        city = get_user_city()
        if city:
            return "memory", f"You live in {city}."
        return "memory", "I don't know where you live yet."

    intent = detect_intent(command)

    if intent == "time":
        now = datetime.datetime.now().strftime("%H:%M:%S")
        return intent, f"The current time is {now}"

    if intent == "date":
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return intent, f"Today is {today}"

    if intent == "greeting":
        name = get_user_name()
        if name:
            return intent, f"Hello {name}! How can I help you today?"
        return intent, "Hello! How can I help you today?"

    if intent == "identity":
        return intent, "I am AURA, your Autonomous Universal Responsive Assistant!"

    if intent == "shutdown":
        return intent, "Goodbye! Shutting down AURA."

    if intent == "study":
        topic = command_lower.replace("study", "").replace("explain", "").replace("teach me", "").replace("learn", "").strip()
        response = study(topic)
        return intent, response

    if intent == "research":
        topic = command_lower.replace("research", "").replace("search", "").replace("find", "").replace("look up", "").strip()
        response = research(topic)
        return intent, response

    if intent == "code":
        request = command_lower.replace("code", "").replace("program", "").replace("debug", "").strip()
        response = code_help(request)
        return intent, response

    response = generate_response(command)
    return intent, response