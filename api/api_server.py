from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from brain.core_ai import process_command
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

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("interface/web/login.html", "r") as f:
        return f.read()

@app.get("/register", response_class=HTMLResponse)
async def register_page():
    with open("interface/web/register.html", "r") as f:
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
    intent, response = process_command(command.text)
    save_chat(command.text, response)
    return {"intent": intent, "response": response}

@app.get("/history")
async def history():
    return load_chat_history()

@app.get("/api/user/{username}")
async def get_user_info(username: str):
    user = get_user(username)
    if user:
        return {"success": True, "user": user}
    raise HTTPException(status_code=404, detail="User not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)