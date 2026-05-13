"""
Mock del cliente Claude — máquina de estados para simular reservas sin API.
"""

# Estado de conversación por "teléfono" (en pruebas siempre el mismo)
_state: dict[str, dict] = {}


def _get(phone: str) -> dict:
    if phone not in _state:
        _state[phone] = {"step": "idle", "data": {}}
    return _state[phone]


def get_response(history: list[dict], user_message: str) -> tuple[str, dict | None]:
    phone = "test"
    msg = user_message.lower().strip()
    state = _get(phone)
    step = state["step"]
    data = state["data"]

    # --- IDLE / SALUDO ---
    if step == "idle":
        if any(w in msg for w in ("reserv", "book", "mesa", "table", "lugar")):
            state["step"] = "ask_date"
            return "Perfecto! Para que fecha te gustaria venir?", None

        if any(w in msg for w in ("menu", "comida", "food", "carta")):
            return (
                "Tenemos dos menus:\n\n"
                "Desayuno (7:30am-12pm): Empanadas $15, Big Breakfast $23, Corn Fritters $22, y mas.\n\n"
                "Almuerzo/Cena: Shared plates (Ceviche $24, Lamb Skewers $16) y mains como Deluxe Paella $30 o Argentinian Steak $42.\n\n"
                "Queres hacer una reserva?",
                None,
            )

        if any(w in msg for w in ("horario", "hora", "open", "abre", "cierra", "cuando")):
            return (
                "Nuestros horarios:\n"
                "- Mar a Jue: 7:30am - 5:30pm\n"
                "- Vie: 7:30am - 10:00pm\n"
                "- Sab: 7:00am - 9:30pm\n"
                "- Lun y Dom: cerrado\n\n"
                "Estamos en Adelaide Central Market, Shop GR43.",
                None,
            )

        return (
            "Hola! Bienvenido a Cumbia Bar & Kitchen!\n"
            "Puedo ayudarte con el menu, horarios o hacer una reserva. Como te puedo ayudar?",
            None,
        )

    # --- FLUJO DE RESERVA ---
    if step == "ask_date":
        data["date"] = user_message.strip()
        state["step"] = "ask_time"
        return f"Genial! A que hora?", None

    if step == "ask_time":
        data["time"] = user_message.strip()
        state["step"] = "ask_guests"
        return "Cuantas personas son?", None

    if step == "ask_guests":
        data["party_size"] = user_message.strip()
        state["step"] = "ask_name"
        return "Y a nombre de quien hago la reserva?", None

    if step == "ask_name":
        data["name"] = user_message.strip()
        state["step"] = "confirm"
        return (
            f"Confirmo la reserva:\n"
            f"  Fecha: {data['date']}\n"
            f"  Hora: {data['time']}\n"
            f"  Personas: {data['party_size']}\n"
            f"  Nombre: {data['name']}\n\n"
            f"Es correcto? (si / no)",
            None,
        )

    if step == "confirm":
        if any(w in msg for w in ("si", "yes", "ok", "correcto", "dale", "confirm")):
            reservation = {
                "date": data.get("date"),
                "time": data.get("time"),
                "party_size": data.get("party_size"),
                "name": data.get("name"),
                "notes": "",
            }
            state["step"] = "idle"
            state["data"] = {}
            return (
                f"Tu reserva esta confirmada!\n"
                f"Te esperamos en Adelaide Central Market, Shop GR43.\n"
                f"Cualquier cambio llamanos al 08 8221 6879.",
                reservation,
            )
        else:
            state["step"] = "ask_date"
            state["data"] = {}
            return "Sin problema! Para que fecha te gustaria venir?", None

    # Fallback
    state["step"] = "idle"
    return "Gracias por tu mensaje! En que te puedo ayudar?", None
