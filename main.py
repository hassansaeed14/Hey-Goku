from brain.core_ai import process_command
from config.settings import APP_NAME, VERSION

def start_goku():
    print(f"\n{'='*40}")
    print(f"  Welcome to {APP_NAME} v{VERSION}")
    print(f"  Your Personal AI Assistant")
    print(f"{'='*40}\n")
    print("Type 'bye' to exit\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            intent, response = process_command(user_input)

            print(f"Goku: {response}\n")

            if intent == "shutdown":
                break

        except KeyboardInterrupt:
            print("\nGoku: Goodbye!")
            break

if __name__ == "__main__":
    start_goku()