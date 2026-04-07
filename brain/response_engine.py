from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME, APP_NAME

client = Groq(api_key=GROQ_API_KEY)

def detect_language(text):
    urdu_chars = set('ابتثجحخدذرزسشصضطظعغفقکگلمنوہیئاآ')
    count = sum(1 for char in text if char in urdu_chars)
    return "urdu" if count > 2 else "english"

def generate_response(user_input):
    language = detect_language(user_input)

    if language == "urdu":
        system_prompt = f"""آپ AURA ہیں، ایک ذہین اور مددگار AI اسسٹنٹ۔
        ہمیشہ اردو میں جواب دیں۔
        مختصر اور واضح جوابات دیں۔
        دوستانہ انداز میں بات کریں۔"""
    else:
        system_prompt = f"""You are {APP_NAME}, a helpful and friendly AI assistant. 
        Keep responses short and clear.
        Be conversational and warm."""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )

    return response.choices[0].message.content