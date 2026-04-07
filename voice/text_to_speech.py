import pyttsx3
import json
import os

VOICE_SETTINGS_FILE = "memory/voice_settings.json"

def load_settings():
    if os.path.exists(VOICE_SETTINGS_FILE):
        with open(VOICE_SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"voice_index": 0, "speed": 170}

def save_settings(settings):
    with open(VOICE_SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def set_voice_preference(voice=None, speed=None):
    settings = load_settings()
    if voice == "male":
        settings["voice_index"] = 1
    elif voice == "female":
        settings["voice_index"] = 0
    if speed == "slow":
        settings["speed"] = 130
    elif speed == "normal":
        settings["speed"] = 170
    elif speed == "fast":
        settings["speed"] = 210
    save_settings(settings)
    print(f"Saved — Voice index: {settings['voice_index']} | Speed: {settings['speed']}")

def get_voice_preference():
    settings = load_settings()
    return settings["voice_index"], settings["speed"]

def speak(text):
    print(f"AURA: {text}")
    try:
        settings = load_settings()
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[settings["voice_index"]].id)
        engine.setProperty('rate', settings["speed"])
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"Voice error: {e}")