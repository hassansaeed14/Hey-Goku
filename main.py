from brain.core_ai import process_command
from config.settings import APP_NAME, VERSION
from voice.text_to_speech import speak
from voice.speech_to_text import listen

def start_goku():
    print(f"\n{'='*40}")
    print(f"  Welcome to {APP_NAME} v{VERSION}")
    print(f"  Your Personal AI Assistant")
    print(f"{'='*40}\n")
    print("Commands: 'voice mode' to talk | 'bye' to exit\n")

    speak(f"Hello! I am {APP_NAME}, your personal AI assistant. How can I help you?")

    voice_mode = False

    while True:
        try:
            if voice_mode:
                print("🎤 Voice Mode ON - Speak now...")
                user_input = listen()
                if not user_input:
                    continue
            else:
                user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "voice mode":
                voice_mode = True
                speak("Voice mode activated! I am listening.")
                continue

            if user_input.lower() == "text mode":
                voice_mode = False
                print("Text mode activated!")
                continue

            intent, response = process_command(user_input)

            speak(response)

            if intent == "shutdown":
                break

        except KeyboardInterrupt:
            speak("Goodbye!")
            break

if __name__ == "__main__":
    start_goku()