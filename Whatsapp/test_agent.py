"""
Prueba interactiva del agente en la terminal.
Uso:
    python test_agent.py          # Claude (Anthropic)
    python test_agent.py --groq   # Groq / Llama (gratis)
    python test_agent.py --mock   # Mock sin API
"""
import os
import sys

# Cargar .env
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()

if "--mock" in sys.argv:
    import mock_claude as client
    print("\n[MODO MOCK - sin API]")
elif "--groq" in sys.argv:
    import groq_client as client
    print("\n[MODO GROQ - Llama 3.3 70B]")
else:
    import claude_client as client
    print("\n[MODO CLAUDE - Anthropic]")

from conversation import ConversationManager

conversations = ConversationManager()
TEST_PHONE = "whatsapp:+61400000000"

print("*** Cumbia Bar & Kitchen -- WhatsApp Agent Test ***")
print("=" * 50)
print("Escribi mensajes como si fueras un cliente.")
print("Escribi 'salir' para terminar.\n")

while True:
    try:
        user_input = input("Vos: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCerrando...")
        sys.exit(0)

    if user_input.lower() in ("salir", "exit", "quit"):
        print("Hasta luego!")
        break

    if not user_input:
        continue

    history = conversations.get_history(TEST_PHONE)

    try:
        reply, reservation = client.get_response(history, user_input)
    except Exception as e:
        print(f"\n[ERROR] {e}\n")
        continue

    conversations.add_turn(TEST_PHONE, user_input, reply)

    print(f"\nAgente: {reply}\n")

    if reservation:
        print("[RESERVA DETECTADA]")
        for k, v in reservation.items():
            print(f"  {k}: {v}")
        import email_client
        email_client.send_reservation_email(reservation, TEST_PHONE)
        print("(En produccion esto tambien se guarda en Google Sheets)\n")
