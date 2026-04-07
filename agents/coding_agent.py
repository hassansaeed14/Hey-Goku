from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME
from memory.vector_memory import store_memory
import re

client = Groq(api_key=GROQ_API_KEY)

def clean(text):
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def code_help(request):
    print(f"\nAURA Coding Agent: {request}")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are AURA Coding Agent, an expert software engineer. "
                    "Help with programming using this structure:\n\n"
                    "CODING SOLUTION: [Problem]\n\n"
                    "1. UNDERSTANDING THE PROBLEM\n"
                    "[Explain what needs to be solved]\n\n"
                    "2. APPROACH\n"
                    "[Explain the approach and algorithm]\n\n"
                    "3. CODE SOLUTION\n"
                    "[Write the complete code here]\n\n"
                    "4. CODE EXPLANATION\n"
                    "Step 1: [Explain first part]\n"
                    "Step 2: [Explain second part]\n"
                    "Step 3: [Explain third part]\n\n"
                    "5. HOW TO RUN\n"
                    "[Instructions to run the code]\n\n"
                    "6. EXAMPLE OUTPUT\n"
                    "[Show expected output]\n\n"
                    "7. POSSIBLE IMPROVEMENTS\n"
                    "[Suggest improvements]\n\n"
                    "Be detailed and educational. "
                    "Do not use ** or ## markdown. Keep code blocks clean."
                )
            },
            {
                "role": "user",
                "content": f"Help me with this coding request: {request}"
            }
        ],
        max_tokens=2500
    )

    result = response.choices[0].message.content
    cleaned = clean(result)
    store_memory(f"Code: {request}", {"type": "code"})
    return cleaned