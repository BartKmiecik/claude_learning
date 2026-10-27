import pytest
import yaml

from agent_predykcje.config import all_symbols, load_watchlist, persona_paths


def test_load_watchlist_reads_stocks_and_indices(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "stocks:\n  - PKO.WA\n  - PZU.WA\nindices:\n  - WIG.WA\n", encoding="utf-8"
    )
    w = load_watchlist(path)
    assert w["stocks"] == ["PKO.WA", "PZU.WA"]
    assert w["indices"] == ["WIG.WA"]


def test_load_watchlist_empty_file_raises_yaml_error(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text("", encoding="utf-8")  # safe_load -> None
    with pytest.raises(yaml.YAMLError):
        load_watchlist(path)


def test_all_symbols_flattens_in_section_order():
    w = {"stocks": ["PKO.WA"], "indices": ["WIG20.WA", "WIG.WA"]}
    assert all_symbols(w) == [
        {"symbol": "PKO.WA", "kind": "stock"},
        {"symbol": "WIG20.WA", "kind": "index"},
        {"symbol": "WIG.WA", "kind": "index"},
    ]


def test_persona_paths_sorted_yaml(tmp_path):
    (tmp_path / "bear.yaml").write_text("name: X\n", encoding="utf-8")
    (tmp_path / "value.yaml").write_text("name: Y\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore\n", encoding="utf-8")
    paths = persona_paths(tmp_path)
    assert [p.stem for p in paths] == ["bear", "value"]
