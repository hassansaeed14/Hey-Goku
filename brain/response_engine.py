from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME, APP_NAME
import re

client = Groq(api_key=GROQ_API_KEY)
conversation_history = []

def detect_language(text):
    urdu_chars = set('ابتثجحخدذرزسشصضطظعغفقکگلمنوہیئاآ')
    count = sum(1 for char in text if char in urdu_chars)
    return "urdu" if count > 2 else "english"

def clean_response(text):
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`{3}[\w]*\n?', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'>\s*', '', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def add_to_history(role, content):
    conversation_history.append({"role": role, "content": content})
    if len(conversation_history) > 20:
        conversation_history.pop(0)

def get_ai_response(user_input, system_override=None):
    language = detect_language(user_input)

    if system_override:
        system_prompt = system_override
    elif language == "urdu":
        system_prompt = (
            "آپ AURA ہیں۔ ہمیشہ اردو میں جواب دیں۔ "
            "پچھلی گفتگو کو یاد رکھیں۔ "
            "تفصیلی اور واضح جوابات دیں۔"
        )
    else:
        system_prompt = (
            f"You are {APP_NAME}, a highly intelligent personal AI assistant. "
            "You are talking to a university student. "
            "CRITICAL: Always remember the FULL conversation history. "
            "When user says this topic or previous question always refer to what was discussed. "
            "Give detailed educational responses. "
            "Be like a knowledgeable professor."
        )

    add_to_history("user", user_input)
    recent_history = conversation_history[-10:]
    messages = [{"role": "system", "content": system_prompt}] + recent_history

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=2000
    )

    result = response.choices[0].message.content
    cleaned = clean_response(result)
    add_to_history("assistant", cleaned)
    return cleaned

def generate_response(user_input):
    return get_ai_response(user_input)

def clear_history():
    global conversation_history
    conversation_history = []