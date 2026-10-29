from pathlib import Path

from agent_predykcje.persona import load_persona, render_system_prompt

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"

STEMS = [
    "value",
    "technical",
    "momentum",
    "contrarian",
    "macro",
    "news",
    "bull",
    "bear",
    "dividend",
    "quant",
]

DISPLAY_NAMES = {
    "Fundamentalista wartościowy",
    "Analityk techniczny",
    "Trader momentum",
    "Kontrarianin",
    "Makroekonomista",
    "Analityk newsowy",
    "Wieczny byk",
    "Wieczny niedźwiedź",
    "Rentier dywidendowy",
    "Statystyk-quant",
}

REQUIRED_FIELDS = {"name", "display_name", "temperament", "biases", "style"}


def test_all_ten_persona_files_load_with_required_fields():
    seen = set()
    for stem in STEMS:
        persona = load_persona(PERSONAS_DIR / f"{stem}.yaml")
        assert REQUIRED_FIELDS <= persona.keys()
        biases = persona["biases"]
        assert isinstance(biases, list) and len(biases) >= 2
        assert all(isinstance(bias, str) and bias.strip() for bias in biases)
        assert persona["display_name"] in DISPLAY_NAMES
        seen.add(persona["display_name"])
    # Ten files, ten distinct archetypes: every pinned label is used exactly once.
    assert seen == DISPLAY_NAMES


def test_render_system_prompt_contains_persona_and_task():
    persona = {
        "name": "Jan Testowy",
        "display_name": "Analityk testowy",
        "temperament": "spokojny i metodyczny",
    }
    prompt = render_system_prompt(persona)
    assert "Jan Testowy" in prompt
    assert "Analityk testowy" in prompt
    assert "spokojny i metodyczny" in prompt
    assert "1 dzień" in prompt
    assert "1 tydzień" in prompt
    assert "1 miesiąc" in prompt
    assert "3 miesiące" in prompt
    assert "6 miesięcy" in prompt
    assert '"3m"' in prompt
    assert '"6m"' in prompt
    assert "JSON" in prompt
    assert "schemat" in prompt
    # The task instruction is the final paragraph, so it is the freshest one.
    last = prompt.rstrip().split("\n\n")[-1]
    assert last.startswith("Twoje zadanie")
    assert "skłonności" in last
