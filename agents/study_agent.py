from groq import Groq
from config.settings import GROQ_API_KEY, MODEL_NAME
from memory.vector_memory import store_memory
import re

client = Groq(api_key=GROQ_API_KEY)

def clean(text):
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`{3}[\w]*\n?', '', text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def study(topic):
    print(f"\nAURA Study Agent: {topic}")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are AURA Study Agent, an expert professor and academic writer. "
                    "Write detailed academic content for university students. "
                    "ALWAYS use this exact professional structure:\n\n"
                    "TITLE: [Topic Name]\n\n"
                    "1. INTRODUCTION\n"
                    "[Write 2-3 detailed paragraphs introducing the topic]\n\n"
                    "2. MAIN CONCEPTS\n"
                    "2.1 [Subtopic]\n"
                    "[Detailed explanation]\n"
                    "2.2 [Subtopic]\n"
                    "[Detailed explanation]\n\n"
                    "3. HOW IT WORKS\n"
                    "[Step by step detailed explanation]\n\n"
                    "4. REAL WORLD EXAMPLES\n"
                    "[Practical examples and applications]\n\n"
                    "5. ADVANTAGES AND DISADVANTAGES\n"
                    "Advantages:\n"
                    "[List advantages]\n"
                    "Disadvantages:\n"
                    "[List disadvantages]\n\n"
                    "6. FUTURE PROSPECTS\n"
                    "[Future developments and trends]\n\n"
                    "7. CONCLUSION\n"
                    "[Summarize key points]\n\n"
                    "Write minimum 800 words. "
                    "Do not use * # ` or markdown symbols. "
                    "Use plain text with the numbered structure above."
                )
            },
            {
                "role": "user",
                "content": f"Write a detailed academic study guide on: {topic}"
            }
        ],
        max_tokens=2500
    )

    result = response.choices[0].message.content
    cleaned = clean(result)
    store_memory(f"Studied: {topic}", {"type": "study", "topic": topic})
    return cleaned