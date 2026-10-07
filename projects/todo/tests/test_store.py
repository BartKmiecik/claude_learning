import json

import pytest

from todo_cli.store import StoreError, TaskStore


@pytest.fixture
def store(tmp_path):
    return TaskStore(tmp_path / "tasks.json")


def test_add_creates_file_and_returns_task(store):
    task = store.add("learn claude code")

    assert task.id == 1
    assert task.text == "learn claude code"
    assert task.done is False
    assert task.created_at  # non-empty timestamp
    assert store.path.exists()
    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert data == [
        {
            "id": 1,
            "text": "learn claude code",
            "done": False,
            "created_at": task.created_at,
        }
    ]


def test_list_returns_all_tasks(store):
    store.add("first")
    store.add("second")

    tasks = store.list()

    assert [t.text for t in tasks] == ["first", "second"]


def test_list_with_missing_file_returns_empty_list(store):
    assert store.list() == []


def test_add_assigns_sequential_ids(store):
    first = store.add("one")
    second = store.add("two")

    assert first.id == 1
    assert second.id == 2


def test_persistence_survives_new_store_instance(store):
    store.add("survivor")

    reopened = TaskStore(store.path)

    assert [t.text for t in reopened.list()] == ["survivor"]


@pytest.mark.parametrize(
    "content",
    [
        '[{"id": 1}]',  # missing text
        '[{"text": "no id"}]',  # missing id
        "[null]",  # not a dict
    ],
)
def test_malformed_element_raises_store_error(tmp_path, content):
    bad = tmp_path / "tasks.json"
    bad.write_text(content, encoding="utf-8")
    store = TaskStore(bad)

    with pytest.raises(StoreError, match="corrupted"):
        store.list()

    with pytest.raises(StoreError, match="corrupted"):
        store.add("anything")
