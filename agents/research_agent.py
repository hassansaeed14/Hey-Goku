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

def research(topic):
    print(f"\nAURA Research Agent: {topic}")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are AURA Research Agent, an expert researcher. "
                    "Provide thorough research reports with this structure:\n\n"
                    "RESEARCH REPORT: [Topic]\n\n"
                    "EXECUTIVE SUMMARY\n"
                    "[Brief overview of findings]\n\n"
                    "1. BACKGROUND AND OVERVIEW\n"
                    "[Detailed background information]\n\n"
                    "2. KEY FINDINGS\n"
                    "Finding 1: [Title]\n"
                    "[Detailed explanation]\n"
                    "Finding 2: [Title]\n"
                    "[Detailed explanation]\n"
                    "Finding 3: [Title]\n"
                    "[Detailed explanation]\n\n"
                    "3. CURRENT DEVELOPMENTS\n"
                    "[Latest developments and trends]\n\n"
                    "4. STATISTICS AND DATA\n"
                    "[Relevant statistics and data points]\n\n"
                    "5. EXPERT OPINIONS\n"
                    "[What experts say about this topic]\n\n"
                    "6. CHALLENGES\n"
                    "[Current challenges and limitations]\n\n"
                    "7. RECOMMENDATIONS\n"
                    "[Recommendations based on research]\n\n"
                    "8. CONCLUSION\n"
                    "[Summary of research findings]\n\n"
                    "Write minimum 600 words. "
                    "Do not use * # ` or markdown. Use plain numbered text."
                )
            },
            {
                "role": "user",
                "content": f"Research this topic thoroughly: {topic}"
            }
        ],
        max_tokens=2500
    )

    result = response.choices[0].message.content
    cleaned = clean(result)
    store_memory(f"Research: {topic}", {"type": "research", "topic": topic})
    return cleaned

def web_search_simulation(query):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are a web search agent. Give accurate information as clear numbered points. No markdown."
            },
            {
                "role": "user",
                "content": f"Search for: {query}"
            }
        ],
        max_tokens=1000
    )
    result = response.choices[0].message.content
    store_memory(f"Search: {query}", {"type": "web_search"})
    return clean(result)