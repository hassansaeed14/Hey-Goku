from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME

client = Groq(api_key=GROQ_API_KEY)

def research(topic):
    print(f"\nAURA Research Agent activated for: {topic}")
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": """You are AURA's Research Agent.
                Research topics thoroughly and present findings clearly.
                Structure: 1) Overview 2) Key Facts 3) Important Details 4) Conclusion
                Keep it under 200 words."""
            },
            {
                "role": "user",
                "content": f"Research this topic and give me a summary: {topic}"
            }
        ]
    )
    
    return response.choices[0].message.content