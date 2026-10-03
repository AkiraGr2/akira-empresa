"""Helpers puros para preparar contexto conversacional seguro."""


def sanitize_historical_assistant_message(role, model, content):
    """Marca como no verificables las afirmaciones operativas no respaldadas."""
    text = str(content or "").strip()
    if str(role or "").strip().lower() != "assistant" or not text:
        return text
    if str(model or "").strip() == "learning_engine":
        return text

    low = text.lower()
    if (
        "id de aprendizaje:" in low
        or "he recibido la corrección y la he registrado" in low
    ):
        return (
            "[RESPUESTA HISTORICA NO VERIFICABLE: "
            "no usar como evidencia de una accion ejecutada.]"
        )
    return text
