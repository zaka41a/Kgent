from pathlib import Path

import pytest

from kgent.chat_store import ChatStore


@pytest.fixture
def store(tmp_path: Path) -> ChatStore:
    return ChatStore(db_url=f"sqlite:///{tmp_path / 'chat.db'}")


def test_create_and_list_conversations(store: ChatStore):
    conv = store.create_conversation(title="hello", provider="openai", model="gpt-4o-mini")
    listed = store.list_conversations()
    assert len(listed) == 1
    assert listed[0]["id"] == conv["id"]
    assert listed[0]["title"] == "hello"


def test_append_message_orders_by_position(store: ChatStore):
    conv = store.create_conversation()
    store.append_message(conv["id"], "user", "first")
    store.append_message(conv["id"], "assistant", "second")
    full = store.get_conversation(conv["id"])
    positions = [m["position"] for m in full["messages"]]
    assert positions == [0, 1]
    assert full["messages"][0]["content"] == "first"
    assert full["messages"][1]["content"] == "second"


def test_append_message_unknown_conversation(store: ChatStore):
    with pytest.raises(ValueError):
        store.append_message("does-not-exist", "user", "x")


def test_first_user_message_becomes_title(store: ChatStore):
    conv = store.create_conversation()
    store.append_message(conv["id"], "user", "What is kgent?")
    full = store.get_conversation(conv["id"])
    assert full["title"] == "What is kgent?"


def test_delete_conversation(store: ChatStore):
    conv = store.create_conversation()
    assert store.delete_conversation(conv["id"]) is True
    assert store.get_conversation(conv["id"]) is None
    assert store.delete_conversation(conv["id"]) is False


def test_update_conversation_meta(store: ChatStore):
    conv = store.create_conversation()
    assert store.update_conversation_meta(conv["id"], provider="anthropic", model="claude") is True
    listed = store.list_conversations()[0]
    assert listed["provider"] == "anthropic"
    assert listed["model"] == "claude"
