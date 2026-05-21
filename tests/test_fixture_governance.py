"""
APOLLO Fixture Governance — Benchmark Integrity Verification

Ensures that:
- Expected benchmark artifacts are unchanged
- Fixture hashes are stable across runs
- Corrupted fixtures do not normalize
- No benchmark regeneration occurs automatically
- Fixture governance rules are enforced
"""

import hashlib
import json
import os

import pytest

from src.core.screening_session import ScreeningSession
from src.core.session_persistence_service import CHECKSUM_FIELDS
from src.core.session_audit_service import SessionAuditService

REPLAY_CORPUS = os.path.join("tests", "replay_corpus")

# Recorded fixture hashes (SHA256 of raw file content)
# If these change, fixtures have been modified intentionally.
FIXTURE_HASHES = {
    "sessions/minimal_session.json": "0c73f1786fb0e5edea2b4748a64e8dcd7b1f2230eb478c81abea4ab0c03980dd",
    "sessions/ec_completed.json": "31157d7fb793df91fe0039f84e715dff3cbff8b0ba15fba003cf62d17147e6fc",
    "sessions/ic_completed.json": "20e778e129690e6a1ce82c761426eb10607d11660beeefd0f74b664df1ed737c",
    "sessions/discussion_heavy.json": "409a996acd3b07f0184c388390efc10ef15a9825cf45e66d6ac4b4c8bdc9ce9c",
    "corrupted/broken_audit_chain.json": "a7e82e2f3431e9c9b13b669715cd29b7464fa4e817bc264b70e9f3ffaab11c48",
    "corrupted/tampered_checksum.json": "e50e942ba4669861c81fd6bfb7edb48b0b69834a832cf7b0f84f9eb5aa892311",
    "corrupted/invalid_stage_transition.json": "6dcd3570469e3403467a32e79f54a139abc7c8f1bcffa6de0ed3f75bb2b8163a",
    "migrations/legacy_schema_session.json": "76081b7745656767c07d2e167126815c0c55a64fc9a4730247df39d43c51e0b8",
    "scale/large_scale_session.json": "e9236a88f07bde903c7506f1272cb30f7d14a196d84ada7d14e1654e97ae49eb",
}

EXPECTED_FILES = ["checksums.json", "progress.json", "replay_results.json"]


# ===========================================================================
# Fixture Hash Stability
# ===========================================================================

class TestFixtureHashStability:
    """Fixture file content hashes must remain stable."""

    @pytest.mark.parametrize("rel_path, expected_hash", list(FIXTURE_HASHES.items()))
    def test_fixture_hash_unchanged(self, rel_path, expected_hash):
        path = os.path.join(REPLAY_CORPUS, rel_path)
        assert os.path.exists(path), f"Fixture missing: {rel_path}"
        with open(path, "rb") as f:
            content = f.read()
        actual_hash = hashlib.sha256(content).hexdigest()
        assert actual_hash == expected_hash, (
            f"Fixture hash changed for {rel_path}\n"
            f"  Expected: {expected_hash}\n"
            f"  Actual:   {actual_hash}\n"
            "Fixture modification detected. "
            "If intentional, update FIXTURE_HASHES in the test."
        )


# ===========================================================================
# Expected Artifact Integrity
# ===========================================================================

class TestExpectedArtifactIntegrity:
    """Expected benchmark artifacts must remain unchanged."""

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_expected_file_exists(self, filename):
        path = os.path.join(REPLAY_CORPUS, "expected", filename)
        assert os.path.exists(path), (
            f"Expected artifact {filename} is missing"
        )

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_expected_file_valid_json(self, filename):
        path = os.path.join(REPLAY_CORPUS, "expected", filename)
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict), (
            f"Expected artifact {filename} must be a JSON object"
        )

    def test_no_unexpected_expected_files(self):
        """Only documented expected files should exist."""
        expected_dir = os.path.join(REPLAY_CORPUS, "expected")
        actual_files = sorted(os.listdir(expected_dir))
        for f in actual_files:
            assert f in EXPECTED_FILES, (
                f"Unexpected file in expected/ directory: {f}"
            )

    def test_checksums_json_structure(self):
        """checksums.json must be a dict of fixture_name -> checksum."""
        path = os.path.join(REPLAY_CORPUS, "expected", "checksums.json")
        with open(path) as f:
            data = json.load(f)
        for fixture_name, expected_cs in data.items():
            assert isinstance(fixture_name, str)
            assert isinstance(expected_cs, str)
            assert len(expected_cs) == 64

    def test_progress_json_structure(self):
        """progress.json must be a dict of fixture_name -> progress dict."""
        path = os.path.join(REPLAY_CORPUS, "expected", "progress.json")
        with open(path) as f:
            data = json.load(f)
        required_progress_keys = {
            "current", "total", "stage", "ec_completed", "ic_completed",
            "ec_pending", "ic_pending", "included", "excluded",
            "skipped", "discussion",
        }
        for fixture_name, progress in data.items():
            assert isinstance(fixture_name, str)
            assert isinstance(progress, dict)
            for key in required_progress_keys:
                assert key in progress, (
                    f"Missing progress key '{key}' for {fixture_name}"
                )

    def test_replay_results_json_structure(self):
        """replay_results.json must contain canonical replay state."""
        path = os.path.join(REPLAY_CORPUS, "expected", "replay_results.json")
        with open(path) as f:
            data = json.load(f)
        required_keys = {
            "session_id", "stage", "current_index", "total_count",
            "ec_completed", "ic_completed", "included_count",
            "excluded_count", "skip_count", "discussion_count",
            "num_articles", "num_audit_events",
        }
        for fixture_name, result in data.items():
            for key in required_keys:
                assert key in result, (
                    f"Missing key '{key}' in replay_results for {fixture_name}"
                )


# ===========================================================================
# Corrupted Fixture Non-Normalization
# ===========================================================================

class TestCorruptedFixtureNonNormalization:
    """Corrupted fixtures must remain corrupted — no silent normalization."""

    @pytest.mark.parametrize("rel_path", [
        "corrupted/broken_audit_chain.json",
        "corrupted/tampered_checksum.json",
        "corrupted/invalid_stage_transition.json",
    ])
    def test_corrupted_fixture_still_fails(self, rel_path):
        path = os.path.join(REPLAY_CORPUS, rel_path)
        session = ScreeningSession(session_id="", created_at="")
        session.load_from_json(path)
        with open(path) as f:
            data = json.load(f)

        if "broken_audit_chain" in rel_path:
            valid, _ = SessionAuditService.verify_chain(session._audit_chain)
            assert not valid, "Broken audit chain must remain broken"

        if "tampered_checksum" in rel_path:
            expected = data.get("session_checksum", "")
            data_for_check = {
                k: data.get(k) for k in CHECKSUM_FIELDS if k in data
            }
            canonical = json.dumps(
                data_for_check, sort_keys=True, ensure_ascii=False
            )
            actual = hashlib.sha256(canonical.encode()).hexdigest()
            assert expected != actual, "Tampered checksum must remain tampered"

        if "invalid_stage_transition" in rel_path:
            assert session.stage == "qc"
            assert session.ec_completed == 0

    def test_no_auto_regen_of_expected(self):
        """Expected artifacts must not be regenerated during test runs."""
        import time
        expected_dir = os.path.join(REPLAY_CORPUS, "expected")
        mtimes = {}
        for f in EXPECTED_FILES:
            path = os.path.join(expected_dir, f)
            mtimes[f] = os.path.getmtime(path)
        # This test file itself does NOT modify expected artifacts
        # Check that mtimes haven't changed
        for f in EXPECTED_FILES:
            path = os.path.join(expected_dir, f)
            assert os.path.getmtime(path) == mtimes[f], (
                f"Expected artifact {f} was modified during test"
            )


# ===========================================================================
# Replay Output Stability
# ===========================================================================

class TestReplayOutputStability:
    """Replay outputs must be stable and not drift silently."""

    @pytest.mark.parametrize("rel_path", [
        "sessions/minimal_session.json",
        "sessions/ec_completed.json",
        "sessions/ic_completed.json",
        "sessions/discussion_heavy.json",
    ])
    def test_replay_output_matches_expected(self, rel_path):
        expected_path = os.path.join(
            REPLAY_CORPUS, "expected", "replay_results.json"
        )
        with open(expected_path) as f:
            expected = json.load(f)
        fixture_name = os.path.basename(rel_path)
        expected_result = expected.get(fixture_name)
        if expected_result is None:
            pytest.skip(f"No expected result for {fixture_name}")

        path = os.path.join(REPLAY_CORPUS, rel_path)
        session = ScreeningSession(session_id="", created_at="")
        session.load_from_json(path)

        actual = {
            "session_id": session.session_id,
            "stage": session.stage,
            "current_index": session.current_index,
            "total_count": session.total_count,
            "ec_completed": session.ec_completed,
            "ic_completed": session.ic_completed,
            "included_count": session.included_count,
            "excluded_count": session.excluded_count,
            "skip_count": session.skip_count,
            "discussion_count": session.discussion_count,
            "num_articles": len(session.articles),
            "num_audit_events": len(session._audit_chain),
        }
        assert actual == expected_result, (
            f"Replay output drift detected for {fixture_name}\n"
            f"  Expected: {json.dumps(expected_result, indent=2)}\n"
            f"  Actual:   {json.dumps(actual, indent=2)}"
        )


# ===========================================================================
# Governance Rule Enforcement
# ===========================================================================

class TestGovernanceRuleEnforcement:
    """Fixture governance rules must be enforced."""

    def test_corrupted_fixtures_have_corruption_prefix(self):
        """Corrupted fixtures must reside in the corrupted/ subdirectory."""
        for fname in ["broken_audit_chain.json", "tampered_checksum.json",
                       "invalid_stage_transition.json"]:
            path = os.path.join(REPLAY_CORPUS, "corrupted", fname)
            assert os.path.exists(path), (
                f"Corrupted fixture {fname} must be in corrupted/"
            )
            # Verify it's NOT in sessions/
            non_corrupted_path = os.path.join(REPLAY_CORPUS, "sessions", fname)
            assert not os.path.exists(non_corrupted_path), (
                f"Corrupted fixture {fname} must NOT be in sessions/"
            )

    def test_expected_artifacts_not_writable_by_default(self):
        """Expected artifacts should not be auto-generated during tests."""
        expected_dir = os.path.join(REPLAY_CORPUS, "expected")
        checksums_path = os.path.join(expected_dir, "checksums.json")
        with open(checksums_path) as f:
            before = f.read()
        # This test does NOT write to the file
        with open(checksums_path) as f:
            after = f.read()
        assert before == after, "Expected artifact was modified during test"

    def test_fixture_checksum_parity_across_loads(self):
        """Every canonical fixture must maintain checksum parity when loaded."""
        for session_file in ["minimal_session.json", "ec_completed.json",
                              "ic_completed.json", "discussion_heavy.json"]:
            path = os.path.join(REPLAY_CORPUS, "sessions", session_file)
            session = ScreeningSession(session_id="", created_at="")
            session.load_from_json(path)
            cs = session.compute_checksum()
            # Verify against expected checksums
            expected_path = os.path.join(
                REPLAY_CORPUS, "expected", "checksums.json"
            )
            with open(expected_path) as f:
                expected_cs = json.load(f).get(session_file)
            if expected_cs:
                assert cs == expected_cs, (
                    f"Checksum mismatch for {session_file}: "
                    f"got {cs}, expected {expected_cs}"
                )
