import stat
from pathlib import Path

from kgent.keystore import keys_path_for, load_keys, merge_request_keys, save_keys


def test_save_filters_to_known_keys_and_drops_empty_values(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_keys(
        store_path,
        {
            "GROQ_API_KEY": "gsk_abc",
            "OPENAI_API_KEY": "",
            "RANDOM_OTHER_KEY": "should-be-dropped",
        },
    )
    loaded = load_keys(store_path)
    assert loaded == {"GROQ_API_KEY": "gsk_abc"}


def test_save_creates_file_with_owner_only_permissions(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_keys(store_path, {"GROQ_API_KEY": "gsk_abc"})
    target = keys_path_for(store_path)
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_load_returns_empty_dict_when_no_file(tmp_path: Path):
    assert load_keys(tmp_path / "index.json") == {}


def test_load_ignores_a_corrupted_file(tmp_path: Path):
    store_path = tmp_path / "index.json"
    target = keys_path_for(store_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not json", encoding="utf-8")
    assert load_keys(store_path) == {}


def test_merge_keeps_browser_keys_and_only_writes_when_persist_is_true(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_keys(store_path, {"GROQ_API_KEY": "old"})

    merged = merge_request_keys(store_path, {"GROQ_API_KEY": "new"}, persist=False)
    assert merged["GROQ_API_KEY"] == "new"
    # persist=False must not overwrite the on-disk copy
    assert load_keys(store_path)["GROQ_API_KEY"] == "old"

    merged = merge_request_keys(store_path, {"GROQ_API_KEY": "newer"}, persist=True)
    assert merged["GROQ_API_KEY"] == "newer"
    assert load_keys(store_path)["GROQ_API_KEY"] == "newer"


def test_merge_does_not_write_when_request_is_empty(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_keys(store_path, {"GROQ_API_KEY": "stored"})

    merged = merge_request_keys(store_path, {}, persist=True)
    assert merged == {"GROQ_API_KEY": "stored"}
