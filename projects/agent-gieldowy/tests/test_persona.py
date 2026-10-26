from pathlib import Path

from agent_gieldowy.persona import load_persona, render_system_prompt

PERSONA_YAML = """\
name: "Andrzej Malinowski"
age: 55
city: "Kraków"
profession: "analityk w towarzystwie funduszy inwestycyjnych (TFI)"
social_position: "wyższa klasa średnia"
education: "mgr ekonomii"
life_history:
  - "Przeżył krach 2008 roku."
biases:
  - "awersja do ryzyka"
  - "ufa spółkom dywidendowym"
temperament: "spokojny"
style: "konkretny, po polsku"
"""


def test_load_persona(tmp_path):
    p = tmp_path / "persona.yaml"
    p.write_text(PERSONA_YAML, encoding="utf-8")
    persona = load_persona(p)
    assert persona["name"] == "Andrzej Malinowski"
    assert persona["age"] == 55


def test_render_system_prompt_contains_identity_history_and_biases(tmp_path):
    p = tmp_path / "persona.yaml"
    p.write_text(PERSONA_YAML, encoding="utf-8")
    prompt = render_system_prompt(load_persona(p))
    assert "Andrzej Malinowski" in prompt
    assert "analityk w towarzystwie funduszy inwestycyjnych" in prompt
    assert "Przeżył krach 2008 roku." in prompt
    assert "awersja do ryzyka" in prompt
    assert "ufa spółkom dywidendowym" in prompt
    assert "dziennika" in prompt  # instruction to weigh the journaled past


def test_render_tolerates_missing_fields(tmp_path):
    p = tmp_path / "minimal.yaml"
    p.write_text('name: "X"\n', encoding="utf-8")
    prompt = render_system_prompt(load_persona(p))
    assert "X" in prompt
    assert "dziennika" in prompt


def test_shipped_persona_renders_all_sections():
    import agent_gieldowy

    persona_path = Path(agent_gieldowy.__file__).parent.parent.parent / "persona.yaml"
    persona = load_persona(persona_path)
    prompt = render_system_prompt(persona)
    for key in (
        "name",
        "age",
        "city",
        "profession",
        "social_position",
        "education",
        "temperament",
        "style",
    ):
        assert str(persona[key]) in prompt
    for line in persona["life_history"]:
        assert line in prompt
    for bias in persona["biases"]:
        assert bias in prompt
