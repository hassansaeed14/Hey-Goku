from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME, APP_NAME

client = Groq(api_key=GROQ_API_KEY)

def generate_response(user_input):

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": f"You are {APP_NAME}, a helpful and friendly AI assistant. Keep responses short and clear."
            },
            {
                "role": "user",
                "content": user_input
            }
        ]
    )

    return response.choices[0].message.content