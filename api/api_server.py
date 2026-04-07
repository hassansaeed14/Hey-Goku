from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from brain.core_ai import process_command
import uvicorn

app = FastAPI()

app.mount("/static", StaticFiles(directory="interface/web"), name="static")

class Command(BaseModel):
    text: str

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("interface/web/index.html", "r") as f:
        return f.read()

@app.post("/chat")
async def chat(command: Command):
    intent, response = process_command(command.text)
    return {"intent": intent, "response": response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)