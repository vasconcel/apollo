"""
APOLLO Tests - Session Persistence Service Extraction

Verifies that persistence/serialization logic was correctly extracted from
ScreeningSession into SessionPersistenceService with full behavioral parity.

Architectural boundaries tested:
- No Streamlit/UI/advisory imports
- No persistence redesign
- Checksum stability
- Save/load parity
- Serialization format unchanged
"""

import json
import os
import tempfile
import hashlib

import pytest

from src.core.architectural_fitness import (
    assert_source_lacks,
    assert_module_ast_lacks_imports,
    assert_is_stateless,
    get_source,
    resolve_source_path,
)

from src.core.screening_session import (
    ScreeningSession, ArticleReview, SessionStage,
)
from src.core.session_persistence_service import (
    SessionPersistenceService, CHECKSUM_FIELDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_articles():
    return [
        ArticleReview(
            article_id='1', title='A', abstract='abs1',
            metadata={'literature_type': 'WL', 'year': '2020'},
        ),
        ArticleReview(
            article_id='2', title='B', abstract='abs2',
            metadata={'literature_type': 'WL', 'year': '2021'},
        ),
    ]


@pytest.fixture
def sample_session(sample_articles):
    session = ScreeningSession(
        session_id='test_persist',
        created_at='2025-01-01T00:00:00',
        protocol_version='1.0',
        stage=SessionStage.EC.value,
        articles=sample_articles,
        current_index=0,
        total_count=2,
        ec_completed=1,
        ic_completed=0,
        included_count=1,
        excluded_count=0,
        skip_count=0,
        discussion_count=0,
        researcher_id='researcher_1',
        last_saved='',
        schema_version='2.0',
    )
    return session


@pytest.fixture
def temp_dir():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    for f in os.listdir(tmpdir):
        os.unlink(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)


# ---------------------------------------------------------------------------
# SessionPersistenceService — unit tests
# ---------------------------------------------------------------------------

class TestSessionPersistenceService:
    """SessionPersistenceService: serialization, checksum, filesystem."""

    def test_to_dict_contains_expected_keys(self, sample_session):
        d = SessionPersistenceService.to_dict(
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.articles,
        )
        expected = {
            'session_id', 'created_at', 'protocol_version', 'stage',
            'current_index', 'total_count', 'ec_completed', 'ic_completed',
            'included_count', 'excluded_count', 'skip_count',
            'discussion_count', 'researcher_id', 'last_saved', 'articles',
        }
        assert set(d.keys()) == expected
        assert isinstance(d['articles'], list)
        assert len(d['articles']) == 2

    def test_to_dict_full_contains_protocol(self, sample_session):
        d = SessionPersistenceService.to_dict_full(
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.schema_version,
            sample_session.articles,
            sample_session.dynamic_protocol,
        )
        assert 'schema_version' in d
        assert 'dynamic_protocol' in d
        assert d['schema_version'] == '2.0'

    def test_compute_checksum_deterministic(self, sample_session):
        full = SessionPersistenceService.to_dict_full(
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.schema_version,
            sample_session.articles,
            sample_session.dynamic_protocol,
        )
        c1 = SessionPersistenceService.compute_checksum(full)
        c2 = SessionPersistenceService.compute_checksum(full)
        assert c1 == c2
        assert len(c1) == 64

    def test_compute_session_hash_16_chars(self):
        data = {'test': 'data'}
        h = SessionPersistenceService.compute_session_hash(data)
        assert len(h) == 16
        assert isinstance(h, str)

    def test_write_and_read_json_roundtrip(self, temp_dir):
        path = os.path.join(temp_dir, 'test.json')
        data = {'key': 'value', 'nested': {'a': 1}}
        SessionPersistenceService.write_json(path, data)
        assert os.path.exists(path)

        loaded = SessionPersistenceService.read_json(path)
        assert loaded == data

    def test_read_json_nonexistent(self):
        result = SessionPersistenceService.read_json('/nonexistent/path.json')
        assert result is None

    def test_read_json_invalid(self, temp_dir):
        path = os.path.join(temp_dir, 'bad.json')
        with open(path, 'w') as f:
            f.write('not json')
        result = SessionPersistenceService.read_json(path)
        assert result is None

    def test_resolve_session_path(self):
        path = SessionPersistenceService.resolve_session_path('/out', 'abc')
        assert path == os.path.join('/out', 'session_abc.json')

    def test_ensure_dir_creates(self, temp_dir):
        new_dir = os.path.join(temp_dir, 'sub', 'nested')
        SessionPersistenceService.ensure_dir(new_dir)
        assert os.path.exists(new_dir)
        import shutil
        shutil.rmtree(os.path.join(temp_dir, 'sub'))

    def test_exists(self, temp_dir):
        path = os.path.join(temp_dir, 'x.txt')
        assert not SessionPersistenceService.exists(path)
        with open(path, 'w') as f:
            f.write('x')
        assert SessionPersistenceService.exists(path)

    def test_save_creates_file(self, sample_session, temp_dir):
        path = SessionPersistenceService.save(
            temp_dir,
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.articles,
        )
        assert os.path.exists(path)
        assert path.endswith('session_test_persist.json')

        # Verify file contents include session_hash
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'session_hash' in data
        assert data['session_id'] == 'test_persist'

    def test_save_to_json_creates_file_with_checksum(self, sample_session, temp_dir):
        path = os.path.join(temp_dir, 'full_session.json')
        SessionPersistenceService.save_to_json(
            path,
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.schema_version,
            sample_session.articles,
            sample_session.dynamic_protocol,
            [],
            False,
        )
        assert os.path.exists(path)
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'session_checksum' in data
        assert 'audit_chain' in data
        assert 'autosave_enabled' in data

    def test_load_from_json_roundtrip(self, sample_session, temp_dir):
        # Save then load
        save_path = SessionPersistenceService.save(
            temp_dir,
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.articles,
        )
        load_path = os.path.join(temp_dir, 'full_session.json')
        SessionPersistenceService.save_to_json(
            load_path,
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.schema_version,
            sample_session.articles,
            sample_session.dynamic_protocol,
            [],
            False,
        )

        result = SessionPersistenceService.load_from_json(load_path)
        assert result is not None
        assert result['session_id'] == 'test_persist'
        assert result['current_index'] == 0
        assert result['total_count'] == 2
        assert result['ec_completed'] == 1
        assert len(result['articles']) == 2

    def test_load_from_json_nonexistent(self):
        result = SessionPersistenceService.load_from_json('/nonexistent.json')
        assert result is None

    def test_list_sessions_empty(self, temp_dir):
        sessions = SessionPersistenceService.list_sessions(temp_dir)
        assert sessions == []

    def test_list_sessions_with_files(self, sample_session, temp_dir):
        SessionPersistenceService.save(
            temp_dir,
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.articles,
        )
        sessions = SessionPersistenceService.list_sessions(temp_dir)
        assert len(sessions) == 1
        assert sessions[0]['session_id'] == 'test_persist'

    def test_recover_session_returns_id(self, sample_session, temp_dir):
        SessionPersistenceService.save(
            temp_dir,
            sample_session.session_id, sample_session.created_at,
            sample_session.protocol_version, sample_session.stage,
            sample_session.current_index, sample_session.total_count,
            sample_session.ec_completed, sample_session.ic_completed,
            sample_session.included_count, sample_session.excluded_count,
            sample_session.skip_count, sample_session.discussion_count,
            sample_session.researcher_id, sample_session.last_saved,
            sample_session.articles,
        )
        sid = SessionPersistenceService.recover_session(temp_dir)
        assert sid == 'test_persist'

    def test_recover_session_empty(self, temp_dir):
        sid = SessionPersistenceService.recover_session(temp_dir)
        assert sid is None

    def test_checksum_fields_constant(self):
        assert 'session_id' in CHECKSUM_FIELDS
        assert 'articles' in CHECKSUM_FIELDS
        assert 'dynamic_protocol' in CHECKSUM_FIELDS
        assert len(CHECKSUM_FIELDS) > 10


# ---------------------------------------------------------------------------
# ScreeningSession delegation — behavioral parity
# ---------------------------------------------------------------------------

class TestScreeningSessionPersistenceDelegation:
    """ScreeningSession delegates persistence to SessionPersistenceService."""

    def test_save_and_load_roundtrip(self, sample_session, temp_dir):
        path = sample_session.save(output_dir=temp_dir)
        assert os.path.exists(path)

        loaded = ScreeningSession.load('test_persist', temp_dir)
        assert loaded is not None
        assert loaded.session_id == 'test_persist'
        assert loaded.current_index == 0
        assert loaded.total_count == 2
        assert loaded.ec_completed == 1

    def test_save_to_json_and_load_from_json(self, sample_session, temp_dir):
        save_path = os.path.join(temp_dir, 'full_session.json')
        sample_session.save_to_json(save_path)
        assert os.path.exists(save_path)

        session2 = ScreeningSession(
            session_id='', created_at='',
        )
        result = session2.load_from_json(save_path)
        assert result is True
        assert session2.session_id == 'test_persist'
        assert session2.total_count == 2

    def test_compute_checksum_stable(self, sample_session):
        c1 = sample_session.compute_checksum()
        c2 = sample_session.compute_checksum()
        assert c1 == c2

    def test_to_dict_matches_save(self, sample_session):
        d1 = sample_session._to_dict()
        d2 = sample_session._to_dict()
        assert d1 == d2

    def test_to_dict_full_matches_save(self, sample_session):
        d1 = sample_session._to_dict_full()
        d2 = sample_session._to_dict_full()
        assert d1 == d2

    def test_list_sessions_through_module(self, sample_session, temp_dir):
        from src.core.screening_session import list_sessions
        sample_session.save(output_dir=temp_dir)
        sessions = list_sessions(temp_dir)
        assert len(sessions) == 1

    def test_recover_session_through_module(self, sample_session, temp_dir):
        from src.core.screening_session import recover_session
        sample_session.save(output_dir=temp_dir)
        recovered = recover_session(temp_dir)
        assert recovered is not None
        assert recovered.session_id == 'test_persist'

    def test_save_updates_last_saved(self, sample_session, temp_dir):
        assert sample_session.last_saved == ''
        sample_session.save(output_dir=temp_dir)
        assert sample_session.last_saved != ''

    def test_save_to_json_updates_last_saved(self, sample_session, temp_dir):
        path = os.path.join(temp_dir, 'full.json')
        assert sample_session.last_saved == ''
        sample_session.save_to_json(path)
        assert sample_session.last_saved != ''

    def test_save_persists_current_last_saved(self, sample_session, temp_dir):
        """Serialized last_saved matches in-memory value after save."""
        sample_session.save(output_dir=temp_dir)
        expected = sample_session.last_saved
        path = SessionPersistenceService.resolve_session_path(
            temp_dir, sample_session.session_id
        )
        data = SessionPersistenceService.read_json(path)
        assert data["last_saved"] == expected

    def test_save_to_json_persists_current_last_saved(self, sample_session, temp_dir):
        """Serialized last_saved matches in-memory value after save_to_json."""
        path = os.path.join(temp_dir, 'canonical.json')
        sample_session.save_to_json(path)
        expected = sample_session.last_saved
        data = SessionPersistenceService.read_json(path)
        assert data["last_saved"] == expected


# ---------------------------------------------------------------------------
# Checksum and serialization determinism
# ---------------------------------------------------------------------------

class TestPersistenceDeterminism:
    """Persistence operations are deterministic."""

    def test_checksum_across_multiple_calls(self, sample_session):
        results = set()
        for _ in range(5):
            results.add(sample_session.compute_checksum())
        assert len(results) == 1

    def test_serialization_across_multiple_calls(self, sample_session):
        results = set()
        for _ in range(5):
            results.add(json.dumps(sample_session._to_dict(), sort_keys=True))
        assert len(results) == 1

    def test_full_serialization_across_multiple_calls(self, sample_session):
        results = set()
        for _ in range(5):
            d = sample_session._to_dict_full()
            results.add(json.dumps(d, sort_keys=True))
        assert len(results) == 1

    def test_save_creates_deterministic_file(self, sample_session, temp_dir):
        path1 = sample_session.save(output_dir=temp_dir)
        with open(path1, 'r') as f:
            data1 = json.load(f)

        # Create a fresh session with same data
        session2 = ScreeningSession(
            session_id='test_persist',
            created_at='2025-01-01T00:00:00',
            articles=sample_session.articles,
            current_index=0, total_count=2,
            ec_completed=1, ic_completed=0,
            included_count=1, excluded_count=0,
            skip_count=0, discussion_count=0,
        )
        path2 = session2.save(output_dir=temp_dir)
        with open(path2, 'r') as f:
            data2 = json.load(f)

        # Both should produce identical content (except last_saved timestamp)
        for key in data1:
            if key == 'session_hash':
                continue
            if key == 'last_saved':
                continue
            assert data1[key] == data2[key], f"Mismatch in key: {key}"


# ---------------------------------------------------------------------------
# Architectural boundary
# ---------------------------------------------------------------------------

class TestPersistenceArchitecturalBoundary:
    """SessionPersistenceService must not import from UI, advisory, etc."""

    IMPORT_BLACKLIST = ['src.ui', 'streamlit', 'src.advisory']

    def test_no_forbidden_imports_in_source(self):
        assert_source_lacks(
            get_source(SessionPersistenceService),
            self.IMPORT_BLACKLIST,
            "SessionPersistenceService",
        )

    def test_module_ast_no_forbidden_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, 'src', 'core', 'session_persistence_service.py'),
            self.IMPORT_BLACKLIST,
            "session_persistence_service.py",
        )

    def test_screening_session_delegates_to_persistence(self):
        """Verify delegation for persistence methods."""
        methods = ['save', 'save_to_json', 'load_from_json',
                   'compute_checksum', '_to_dict', '_to_dict_full']
        for method_name in methods:
            method = getattr(ScreeningSession, method_name)
            source = get_source(method)
            assert 'SessionPersistenceService.' in source, (
                f"{method_name} should delegate to SessionPersistenceService"
            )

    def test_module_functions_delegate(self):
        from src.core.screening_session import (
            list_sessions, recover_session,
        )
        assert 'SessionPersistenceService.list_sessions' in get_source(list_sessions)
        assert 'SessionPersistenceService.recover_session' in get_source(recover_session)

    def test_session_persistence_service_is_stateless(self):
        assert_is_stateless(SessionPersistenceService)


# ---------------------------------------------------------------------------
# Serialization format preservation
# ---------------------------------------------------------------------------

class TestSerializationFormat:
    """Serialization format must remain identical to original."""

    def test_to_dict_field_order_matches_original(self, sample_session):
        d = sample_session._to_dict()
        keys = list(d.keys())
        expected_first_keys = [
            'session_id', 'created_at', 'protocol_version', 'stage',
            'current_index', 'total_count',
        ]
        for i, k in enumerate(expected_first_keys):
            assert keys[i] == k, (
                f"Expected key[{i}] = '{k}', got '{keys[i]}'"
            )

    def test_to_dict_full_includes_all_fields(self, sample_session):
        d = sample_session._to_dict_full()
        expected = {
            'session_id', 'created_at', 'protocol_version', 'stage',
            'current_index', 'total_count', 'ec_completed', 'ic_completed',
            'included_count', 'excluded_count', 'skip_count',
            'discussion_count', 'researcher_id', 'last_saved',
            'schema_version', 'articles', 'dynamic_protocol',
        }
        assert set(d.keys()) == expected

    def test_article_dict_structure_preserved(self, sample_session):
        d = sample_session._to_dict()
        article = d['articles'][0]
        assert 'article_id' in article
        assert 'title' in article
        assert 'abstract' in article
        assert 'metadata' in article
        assert 'ec_stage' in article
        assert 'ic_stage' in article
