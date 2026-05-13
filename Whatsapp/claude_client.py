import anthropic
from cumbia_info import SYSTEM_PROMPT, RESERVATION_TOOL

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

client = anthropic.Anthropic()


def get_response(history: list[dict], user_message: str) -> tuple[str, dict | None]:
    """
    Send conversation history + new user message to Claude.
    Returns (assistant_text, reservation_data | None).
    reservation_data is set when Claude calls the save_reservation tool.
    """
    messages = history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[RESERVATION_TOOL],
        messages=messages,
    )

    reservation_data = None
    text_parts = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use" and block.name == "save_reservation":
            reservation_data = block.input

    if reservation_data:
        # Let Claude produce a confirmation message after tool call
        tool_result_messages = messages + [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": next(
                            b.id for b in response.content if b.type == "tool_use"
                        ),
                        "content": "Reservation saved successfully.",
                    }
                ],
            },
        ]
        confirmation = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[RESERVATION_TOOL],
            messages=tool_result_messages,
        )
        for block in confirmation.content:
            if block.type == "text":
                text_parts.append(block.text)

    assistant_text = "\n".join(text_parts).strip()
    return assistant_text, reservation_data
