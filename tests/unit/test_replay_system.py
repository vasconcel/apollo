"""Tests for replay_system.py."""
import json
import pytest

from src.advisory.replay_system import (
    ReplaySnapshot, ReplayStore, freeze_replay_snapshot,
    compute_replay_session_id, get_replay_store, reset_replay_store,
)


class TestReplaySnapshot:
    def test_to_dict_roundtrip(self):
        snapshot = ReplaySnapshot(
            session_id="test123",
            articles=[{"cache_key": "abc", "title": "Test"}],
            protocol_version="1.0",
            config={"sample_size": 10},
        )
        data = snapshot.to_dict()
        assert data["session_id"] == "test123"
        assert data["article_count"] == 1

        restored = ReplaySnapshot.from_dict(data)
        assert restored.session_id == "test123"
        assert len(restored.articles) == 1

    def test_articles_sorted_deterministically(self):
        articles = [
            {"cache_key": "z_article"},
            {"cache_key": "a_article"},
            {"cache_key": "m_article"},
        ]
        snapshot = ReplaySnapshot(
            session_id="sort_test",
            articles=articles,
            protocol_version="1.0",
            config={},
        )
        keys = [a["cache_key"] for a in snapshot.articles]
        assert keys == sorted(keys)


class TestComputeSessionId:
    def test_deterministic_id(self):
        articles = [{"cache_key": "art1"}, {"cache_key": "art2"}]
        id1 = compute_replay_session_id(articles, "1.0")
        id2 = compute_replay_session_id(articles, "1.0")
        assert id1 == id2
        assert len(id1) == 16

    def test_different_articles_different_id(self):
        articles1 = [{"cache_key": "art1"}]
        articles2 = [{"cache_key": "art2"}]
        id1 = compute_replay_session_id(articles1, "1.0")
        id2 = compute_replay_session_id(articles2, "1.0")
        assert id1 != id2

    def test_different_versions_different_id(self):
        articles = [{"cache_key": "art1"}]
        id1 = compute_replay_session_id(articles, "1.0")
        id2 = compute_replay_session_id(articles, "2.0")
        assert id1 != id2


class TestFreezeReplaySnapshot:
    def test_freeze_from_dicts(self):
        articles = [{"cache_key": "art1", "title": "Test", "abstract": "Abstract"}]
        snapshot = freeze_replay_snapshot(articles, "1.0")
        assert snapshot.article_count == 1
        assert snapshot.protocol_version == "1.0"
        assert len(snapshot.session_id) == 16

    def test_freeze_deterministic_session_id(self):
        articles = [{"cache_key": "art1", "title": "Test", "abstract": "Abstract"}]
        s1 = freeze_replay_snapshot(articles, "1.0")
        s2 = freeze_replay_snapshot(articles, "1.0")
        assert s1.session_id == s2.session_id

    def test_freeze_with_metadata(self):
        articles = [{
            "cache_key": "art1",
            "title": "Test",
            "abstract": "Abstract",
            "metadata": {"year": "2024", "authors": "Smith"},
        }]
        snapshot = freeze_replay_snapshot(articles, "1.0")
        assert snapshot.articles[0]["metadata"]["year"] == "2024"
        assert snapshot.articles[0]["metadata"]["authors"] == "Smith"


class TestReplayStore:
    def setup_method(self):
        reset_replay_store()

    def test_save_and_load(self, tmp_path):
        store = ReplayStore(base_dir=str(tmp_path / "replay"))
        snapshot = ReplaySnapshot(
            session_id="save_test",
            articles=[{"cache_key": "art1", "title": "Saved"}],
            protocol_version="1.0",
            config={},
        )
        path = store.save(snapshot)
        assert path.endswith("save_test.json")

        loaded = store.load("save_test")
        assert loaded is not None
        assert loaded.session_id == "save_test"
        assert len(loaded.articles) == 1

    def test_load_nonexistent(self, tmp_path):
        store = ReplayStore(base_dir=str(tmp_path / "replay"))
        assert store.load("nonexistent") is None

    def test_list_sessions(self, tmp_path):
        store = ReplayStore(base_dir=str(tmp_path / "replay"))
        s1 = ReplaySnapshot("session1", [{"cache_key": "a"}], "1.0", {})
        s2 = ReplaySnapshot("session2", [{"cache_key": "b"}], "1.0", {})
        store.save(s1)
        store.save(s2)

        sessions = store.list_sessions()
        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session1"
        assert sessions[1]["session_id"] == "session2"

    def test_delete(self, tmp_path):
        store = ReplayStore(base_dir=str(tmp_path / "replay"))
        s = ReplaySnapshot("delete_me", [], "1.0", {})
        store.save(s)
        assert store.load("delete_me") is not None
        assert store.delete("delete_me") is True
        assert store.load("delete_me") is None

    def test_global_singleton(self):
        reset_replay_store()
        s1 = get_replay_store()
        s2 = get_replay_store()
        assert s1 is s2
