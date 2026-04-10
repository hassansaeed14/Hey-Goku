from brain.core_ai import process_command
from config.settings import APP_NAME, VERSION
from voice.text_to_speech import speak, stop_speaking
from voice.speech_to_text import listen
from agents.core.orchestrator import orchestrator
try:
    from flask import Flask, jsonify, request
except ImportError:  # pragma: no cover - optional for CLI-only environments
    Flask = None
    jsonify = None
    request = None


app = Flask(__name__) if Flask else None


WELCOME_MESSAGE = (
    "Hello! I am AURA, your Autonomous Universal Responsive Assistant. "
    "How can I help you?"
)

STOP_COMMANDS = {"stop", "stop talking", "quiet", "silence", "shut up"}
VOICE_MODE_COMMANDS = {"voice mode", "start voice mode", "talk mode"}
TEXT_MODE_COMMANDS = {"text mode", "typing mode"}
EXIT_COMMANDS = {"bye", "goodbye", "exit", "quit", "shutdown"}


def _add_chat_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


if app is not None:
    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        try:
            payload = request.get_json(silent=True) or {}
            message = (payload.get("message") or "").strip()
            _mode = (payload.get("mode") or "hybrid").strip() or "hybrid"

            if not message:
                raise ValueError("message is required")

            routed_agent, _confidence = orchestrator.route(message)
            intent, response = process_command(message)
            response = orchestrator.process_response(response, intent, learn=False)

            reply_payload = {
                "reply": response,
                "agent": routed_agent or intent or "general",
                "status": "ok",
            }
            flask_response = jsonify(reply_payload)
            flask_response.status_code = 200
            return _add_chat_cors_headers(flask_response)
        except Exception as error:
            flask_response = jsonify({
                "error": str(error),
                "status": "error",
            })
            flask_response.status_code = 500
            return _add_chat_cors_headers(flask_response)


def print_banner():
    print(f"\n{'=' * 40}")
    print(f"  Welcome to {APP_NAME} v{VERSION}")
    print("  Your Personal AI Assistant")
    print(f"{'=' * 40}\n")

    print("Commands:")
    print("  'voice mode'  — talk to AURA")
    print("  'text mode'   — type to AURA")
    print("  'stop'        — stop speaking")
    print("  'read full'   — hear the complete last response")
    print("  'bye'         — exit\n")


def print_banner():
    print(f"\n{'=' * 40}")
    print(f"  Welcome to {APP_NAME} v{VERSION}")
    print("  Your Personal AI Assistant")
    print(f"{'=' * 40}\n")

    print("Commands:")
    print("  'voice mode'  - talk to AURA")
    print("  'text mode'   - type to AURA")
    print("  'stop'        - stop speaking")
    print("  'read full'   - hear the complete last response")
    print("  'bye'         - exit\n")


def get_user_input(voice_mode=False):
    if voice_mode:
        print("Listening...")
        heard = listen()
        return heard.strip() if heard else ""
    return input("You: ").strip()


def build_short_preview(text):
    text = text.strip()

    if "." in text:
        parts = [p.strip() for p in text.split(".") if p.strip()]
        preview = ". ".join(parts[:2]).strip()
        if preview and not preview.endswith("."):
            preview += "."
        return preview

    if len(text) > 250:
        return text[:250].rstrip() + "..."

    return text


def speak_response(response, read_full=False):
    if not response:
        return

    if read_full:
        speak(response, read_full=True)
        return

    if len(response) > 500:
        short_preview = build_short_preview(response)
        speak(short_preview)
        print("AURA: (Say 'read full' to hear the complete response)")
    else:
        speak(response)


def start_goku():
    print_banner()
    speak(WELCOME_MESSAGE)

    voice_mode = False
    last_response = ""

    while True:
        try:
            user_input = get_user_input(voice_mode=voice_mode)

            if not user_input:
                continue

            user_input_lower = user_input.lower().strip()

            if user_input_lower in STOP_COMMANDS:
                stop_speaking()
                print("AURA: Speech stopped.")
                continue

            if user_input_lower in VOICE_MODE_COMMANDS:
                voice_mode = True
                print("AURA: Voice mode activated.")
                speak("Voice mode activated. I am listening.")
                continue

            if user_input_lower in TEXT_MODE_COMMANDS:
                voice_mode = False
                stop_speaking()
                print("AURA: Text mode activated.")
                continue

            if user_input_lower == "read full":
                if last_response:
                    print("AURA: Reading full response...")
                    speak(last_response, read_full=True)
                else:
                    print("AURA: I do not have a previous response to read.")
                continue

            if user_input_lower in EXIT_COMMANDS:
                print("AURA: Goodbye!")
                stop_speaking()
                speak("Goodbye!")
                break

            # Orchestrator pre-routing
            routed_intent, confidence = orchestrator.route(user_input)

            # Core AI processing
            intent, response = process_command(user_input)

            # Orchestrator post-processing
            response = orchestrator.process_response(response, intent, learn=False)

            last_response = response

            print(f"\nAURA ({intent} | confidence: {confidence:.2f}): {response}\n")
            speak_response(response)

            if intent == "shutdown":
                print("AURA: Goodbye!")
                stop_speaking()
                speak("Goodbye!")
                break

        except KeyboardInterrupt:
            print("\nAURA: Goodbye!")
            stop_speaking()
            speak("Goodbye!")
            break

        except Exception as e:
            error_message = f"System error: {str(e)}"
            print(f"AURA: {error_message}")
            try:
                speak("I ran into a system error.")
            except Exception:
                pass


if __name__ == "__main__":
    start_goku()
