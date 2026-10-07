from pathlib import Path

import pytest

from todo_cli.cli import main


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "tasks.json"


def run_cli(argv, store_path, capsys):
    code = main(argv, store_path=store_path)
    captured = capsys.readouterr()
    return code, captured


def test_add_prints_confirmation(store_path, capsys):
    code, out = run_cli(["add", "learn claude code"], store_path, capsys)

    assert code == 0
    assert out.out == "#1 added: learn claude code\n"
    assert out.err == ""


def test_add_rejects_empty_text(store_path, capsys):
    code, out = run_cli(["add", "   "], store_path, capsys)

    assert code == 1
    assert out.err == "Task text cannot be empty\n"


def test_list_prints_markers(store_path, capsys):
    main(["add", "first"], store_path=store_path)
    main(["add", "second"], store_path=store_path)
    main(["done", "1"], store_path=store_path)
    # drain setup output so the assertions below see only the call under
    # test (capsys accumulates across calls; it doesn't reset)
    capsys.readouterr()

    code, out = run_cli(["list"], store_path, capsys)

    assert code == 0
    assert out.out == "1. [x] first\n2. [ ] second\n"


def test_done_and_remove_print_confirmations(store_path, capsys):
    main(["add", "task"], store_path=store_path)
    # drain setup output so the assertions below see only the call under
    # test (capsys accumulates across calls; it doesn't reset)
    capsys.readouterr()

    code, out = run_cli(["done", "1"], store_path, capsys)
    assert code == 0
    assert out.out == "#1 completed\n"

    code, out = run_cli(["remove", "1"], store_path, capsys)
    assert code == 0
    assert out.out == "#1 removed\n"


def test_unknown_id_prints_error(store_path, capsys):
    code, out = run_cli(["done", "99"], store_path, capsys)

    assert code == 1
    assert out.err == "No task #99\n"


def test_corrupt_file_prints_error(store_path, capsys):
    store_path.write_text("{broken", encoding="utf-8")

    code, out = run_cli(["list"], store_path, capsys)

    assert code == 1
    assert f"corrupted: {store_path}" in out.err


def test_remove_unknown_id_prints_error(store_path, capsys):
    code, out = run_cli(["remove", "99"], store_path, capsys)

    assert code == 1
    assert out.err == "No task #99\n"


def test_default_store_path_is_in_home_dir():
    from todo_cli.cli import default_store_path

    assert default_store_path() == Path.home() / ".todo" / "tasks.json"


def test_unreadable_store_prints_clean_error(tmp_path, capsys):
    # A directory as the store path makes reads fail with an OSError
    code, out = run_cli(["list"], tmp_path, capsys)

    assert code == 1
    assert "Could not access the task file" in out.err
