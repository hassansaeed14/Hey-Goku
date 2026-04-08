from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from brain.core_ai import process_command
from brain.intent_engine import detect_intent_with_confidence
from memory.memory_manager import save_chat, load_chat_history
from api.auth import register_user, login_user, get_user
import uvicorn


app = FastAPI()

app.mount("/static", StaticFiles(directory="interface/web"), name="static")


class Command(BaseModel):
    text: str
    username: str = "guest"


class LoginData(BaseModel):
    username: str
    password: str


class RegisterData(BaseModel):
    username: str
    password: str
    name: str


@app.get("/", response_class=HTMLResponse)
async def home():
    with open("interface/web/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("interface/web/login.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    with open("interface/web/register.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/login")
async def login(data: LoginData):
    success, result = login_user(data.username, data.password)
    if success:
        return {"success": True, "user": result}
    raise HTTPException(status_code=401, detail=result)


@app.post("/api/register")
async def register(data: RegisterData):
    success, message = register_user(data.username, data.password, data.name)
    if success:
        return {"success": True, "message": message}
    raise HTTPException(status_code=400, detail=message)


@app.post("/chat")
async def chat(command: Command):
    try:
        detected_intent, confidence = detect_intent_with_confidence(command.text)
        final_intent, response = process_command(command.text)

        save_chat(command.text, response)

        return {
            "intent": final_intent,
            "detected_intent": detected_intent,
            "confidence": round(confidence, 2),
            "response": response,
            "username": command.username,
            "plan": []
        }

    except Exception as e:
        return {
            "intent": "error",
            "detected_intent": "error",
            "confidence": 0.0,
            "response": f"Sorry, I encountered an error: {str(e)}",
            "username": command.username,
            "plan": []
        }


@app.get("/history")
async def history():
    return load_chat_history()


@app.get("/api/user/{username}")
async def get_user_info(username: str):
    user = get_user(username)
    if user:
        return {"success": True, "user": user}
    raise HTTPException(status_code=404, detail="User not found")


@app.get("/api/system/status")
async def system_status():
    return {
        "status": "online",
        "version": "1.0.0",
        "model": "Llama 3.3 70B",
        "orchestrator": "online",
        "reasoning": "active",
        "memory": "connected",
        "planner": "ready"
    }


@app.get("/api/agents")
async def get_agents():
    return {
        "agents": [
            {"id": "general", "name": "General AURA", "icon": "🤖", "description": "General AI assistant"},
            {"id": "study", "name": "Study Agent", "icon": "📚", "description": "Learn any topic"},
            {"id": "research", "name": "Research Agent", "icon": "🔍", "description": "Deep research"},
            {"id": "code", "name": "Coding Agent", "icon": "💻", "description": "Programming help"},
            {"id": "weather", "name": "Weather Agent", "icon": "🌤️", "description": "Weather info"},
            {"id": "news", "name": "News Agent", "icon": "📰", "description": "Latest news"},
            {"id": "math", "name": "Math Agent", "icon": "🧮", "description": "Math solver"},
            {"id": "translation", "name": "Translation Agent", "icon": "🌍", "description": "Translate languages"},
            {"id": "email", "name": "Email Writer", "icon": "📧", "description": "Write emails"},
            {"id": "content", "name": "Content Writer", "icon": "✍️", "description": "Write content"},
            {"id": "summarize", "name": "Summarizer", "icon": "📝", "description": "Summarize text"},
            {"id": "grammar", "name": "Grammar Check", "icon": "✅", "description": "Fix grammar"},
            {"id": "quiz", "name": "Quiz Agent", "icon": "🎯", "description": "Generate quizzes"},
            {"id": "joke", "name": "Joke Agent", "icon": "😄", "description": "Tell jokes"},
            {"id": "quote", "name": "Quote Agent", "icon": "💭", "description": "Inspiring quotes"},
            {"id": "password", "name": "Password Agent", "icon": "🔐", "description": "Generate passwords"},
            {"id": "task", "name": "Task Manager", "icon": "📋", "description": "Manage tasks"},
            {"id": "reminder", "name": "Reminder Agent", "icon": "⏰", "description": "Set reminders"},
            {"id": "resume", "name": "Resume Builder", "icon": "📄", "description": "Build resume"},
            {"id": "currency", "name": "Currency Agent", "icon": "💱", "description": "Convert currency"},
            {"id": "dictionary", "name": "Dictionary", "icon": "📖", "description": "Define words"},
            {"id": "youtube", "name": "YouTube Agent", "icon": "▶️", "description": "YouTube search"},
            {"id": "web_search", "name": "Web Search", "icon": "🌐", "description": "Search web"},
            {"id": "file", "name": "File Agent", "icon": "📁", "description": "Read files"},
            {"id": "screenshot", "name": "Screenshot", "icon": "📸", "description": "Take screenshots"},
            {"id": "fitness", "name": "Fitness Agent", "icon": "💪", "description": "Workout and fitness plans"}
        ]
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)