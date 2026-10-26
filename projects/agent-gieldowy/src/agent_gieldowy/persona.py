"""Persona YAML → system prompt. The biases are first-class, visible, and editable."""

import yaml


def load_persona(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_system_prompt(persona: dict) -> str:
    name = persona.get("name", "Anonimowy analityk")
    age = persona.get("age", "—")
    city = persona.get("city", "Polska")
    profession = persona.get("profession", "analityk finansowy")
    social_position = persona.get("social_position", "—")
    education = persona.get("education", "—")
    temperament = persona.get("temperament", "spokojny")
    style = persona.get("style", "konkretny, po polsku")
    history = "\n".join(f"- {line}" for line in persona.get("life_history") or [])
    biases = "\n".join(f"- {line}" for line in persona.get("biases") or [])
    return (
        f"Jesteś {name}, {age} lat, z {city}. "
        f"Zawód: {profession}. Pozycja społeczna: {social_position}. "
        f"Wykształcenie: {education}.\n\n"
        f"Twoja historia, która kształtuje Twoje sądy:\n{history}\n\n"
        f"Temperament: {temperament}.\n\n"
        f"Twoje skłonności (świadomie uwzględniaj je w analizie):\n{biases}\n\n"
        f"Styl: {style}.\n\n"
        "Analizujesz polski rynek i prognozujesz zmiany kursów na 1 miesiąc. "
        "Zawsze uwzględniaj swoją przeszłość z dziennika: wcześniejsze prognozy, "
        "ich wyniki i własne refleksje."
    )
