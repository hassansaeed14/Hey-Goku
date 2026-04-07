from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME

client = Groq(api_key=GROQ_API_KEY)

def study(topic):
    print(f"\nAURA Study Agent activated for: {topic}")
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": """You are AURA's Study Agent. 
                Explain topics clearly and simply.
                Use examples. Keep it under 150 words.
                Structure: 1) What it is 2) How it works 3) Example"""
            },
            {
                "role": "user",
                "content": f"Explain this topic for studying: {topic}"
            }
        ]
    )
    
    return response.choices[0].message.content