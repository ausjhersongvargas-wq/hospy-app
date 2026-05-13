import os
import json
from groq import Groq
from cumbia_info import SYSTEM_PROMPT, RESERVATION_TOOL

# Modelos disponibles en Groq (cada uno tiene su propio límite diario):
# llama-3.3-70b-versatile  — mejor calidad
# llama-3.1-8b-instant     — más rápido, límite separado
# gemma2-9b-it             — Google Gemma, límite separado
PRIMARY_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL = "llama-3.1-8b-instant"
MAX_TOKENS = 1024

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Groq usa formato OpenAI para tools
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": RESERVATION_TOOL["name"],
            "description": RESERVATION_TOOL["description"],
            "parameters": RESERVATION_TOOL["input_schema"],
        },
    }
]


def _call(model: str, messages: list, tools=None) -> object:
    kwargs = dict(model=model, max_tokens=MAX_TOKENS, temperature=0, messages=messages)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)


def get_response(history: list[dict], user_message: str) -> tuple[str, dict | None]:
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    try:
        response = _call(PRIMARY_MODEL, messages, _TOOLS)
    except Exception as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            print(f"[groq] {PRIMARY_MODEL} rate limited — switching to {FALLBACK_MODEL}")
            response = _call(FALLBACK_MODEL, messages, _TOOLS)
        else:
            raise

    choice = response.choices[0]
    msg = choice.message
    reservation_data = None
    text = msg.content or ""

    # Manejar tool call
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        reservation_data = json.loads(tool_call.function.arguments)

        # Segunda llamada para que el modelo genere la confirmación
        messages.append({"role": "assistant", "content": None, "tool_calls": msg.tool_calls})
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": "Reservation saved successfully.",
        })

        try:
            confirmation = _call(PRIMARY_MODEL, messages)
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                confirmation = _call(FALLBACK_MODEL, messages)
            else:
                raise
        text = confirmation.choices[0].message.content or ""

    return text.strip(), reservation_data
