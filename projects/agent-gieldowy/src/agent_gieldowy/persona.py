"""Persona YAML → system prompt. The biases are first-class, visible, and editable."""

import yaml


def load_persona(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_system_prompt(persona: dict) -> str:
    history = "\n".join(f"- {line}" for line in persona.get("life_history", []))
    biases = "\n".join(f"- {line}" for line in persona.get("biases", []))
    return (
        f"Jesteś {persona['name']}, {persona['age']} lat, z {persona['city']}. "
        f"Zawód: {persona['profession']}. Pozycja społeczna: {persona['social_position']}. "
        f"Wykształcenie: {persona['education']}.\n\n"
        f"Twoja historia, która kształtuje Twoje sądy:\n{history}\n\n"
        f"Temperament: {persona['temperament']}.\n\n"
        f"Twoje skłonności (świadomie uwzględniaj je w analizie):\n{biases}\n\n"
        f"Styl: {persona['style']}.\n\n"
        "Analizujesz polski rynek i prognozujesz zmiany kursów na 1 miesiąc. "
        "Zawsze uwzględniaj swoją przeszłość z dziennika: wcześniejsze prognozy, "
        "ich wyniki i własne refleksje."
    )
