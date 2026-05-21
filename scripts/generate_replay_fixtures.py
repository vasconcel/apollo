"""
APOLLO Replay Corpus Fixture Generator

Generates deterministic replay corpus fixtures with valid checksums.
Must be run from project root: python scripts/generate_replay_fixtures.py

Produces fixtures under tests/replay_corpus/
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.screening_session import ArticleReview, SessionStage
from src.core.session_persistence_service import CHECKSUM_FIELDS

REPLAY_CORPUS_DIR = os.path.join("tests", "replay_corpus")
SESSIONS_DIR = os.path.join(REPLAY_CORPUS_DIR, "sessions")
CORRUPTED_DIR = os.path.join(REPLAY_CORPUS_DIR, "corrupted")
MIGRATIONS_DIR = os.path.join(REPLAY_CORPUS_DIR, "migrations")
SCALE_DIR = os.path.join(REPLAY_CORPUS_DIR, "scale")
COMPATIBILITY_DIR = os.path.join(REPLAY_CORPUS_DIR, "compatibility")
EXPECTED_DIR = os.path.join(REPLAY_CORPUS_DIR, "expected")

FIXED_TIMESTAMP = "2025-01-15T10:00:00"
FIXED_LAST_SAVED = "2025-01-15T10:30:00"


def compute_checksum(data):
    data_for_check = {k: data.get(k) for k in CHECKSUM_FIELDS if k in data}
    canonical_json = json.dumps(data_for_check, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode()).hexdigest()


def make_article_dict(
    article_id, title, abstract, metadata,
    ec_stage="", ec_notes="", ec_timestamp="",
    ec_llm_suggestion=None,
    ic_stage="", ic_notes="", ic_timestamp="",
    ic_llm_suggestion=None,
    qc_stage="", qc_notes="", qc_timestamp="", qc_score="",
    qc_llm_suggestion=None,
    final_decision="",
):
    return {
        "article_id": article_id,
        "title": title,
        "abstract": abstract,
        "metadata": metadata,
        "ec_stage": ec_stage,
        "ec_notes": ec_notes,
        "ec_timestamp": ec_timestamp,
        "ec_llm_suggestion": ec_llm_suggestion or {},
        "ic_stage": ic_stage,
        "ic_notes": ic_notes,
        "ic_timestamp": ic_timestamp,
        "ic_llm_suggestion": ic_llm_suggestion or {},
        "qc_stage": qc_stage,
        "qc_notes": qc_notes,
        "qc_timestamp": qc_timestamp,
        "qc_score": qc_score,
        "qc_llm_suggestion": qc_llm_suggestion or {},
        "final_decision": final_decision,
    }


def make_audit_event(event_id, timestamp, article_id, reviewer_id, stage, decision, notes, previous_hash):
    event_payload = {
        "event_id": event_id,
        "timestamp": timestamp,
        "article_id": article_id,
        "reviewer_id": reviewer_id,
        "stage": stage,
        "decision": decision,
        "notes": notes,
    }
    payload_json = json.dumps(event_payload, sort_keys=True, ensure_ascii=False)
    current_hash = hashlib.sha256((payload_json + previous_hash).encode()).hexdigest()
    return {
        **event_payload,
        "previous_hash": previous_hash,
        "current_hash": current_hash,
    }


def generate_fixture(base_data, filename, subdir):
    """Generate a fixture file with checksum."""
    data = dict(base_data)
    data["session_checksum"] = compute_checksum(data)
    path = os.path.join(subdir, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Created: {path}")
    return path


def make_default_protocol_dict():
    return {
        "protocol_version": "1.0",
        "created_at": FIXED_TIMESTAMP,
        "state": "draft",
        "locked_at": None,
        "protocol_hash": "",
        "template_name": None,
        "template_version": None,
        "ec": {
            "criteria": {
                "EC1": {"id": "EC1", "description": "Sources not written in English.", "enabled": True, "keywords": [], "weight": 1.0},
                "EC2": {"id": "EC2", "description": "Sources whose full text was unavailable.", "enabled": True, "keywords": [], "weight": 1.0},
                "EC3": {"id": "EC3", "description": "Short publications lacking sufficient evidence.", "enabled": True, "keywords": [], "weight": 1.0},
                "EC4": {"id": "EC4", "description": "Sources published before 2015.", "enabled": True, "keywords": [], "weight": 1.0},
                "EC5": {"id": "EC5", "description": "Sources unrelated to SE R&S.", "enabled": True, "keywords": [], "weight": 1.0},
                "EC6": {"id": "EC6", "description": "Duplicate studies.", "enabled": True, "keywords": [], "weight": 1.0},
            },
            "min_year": 2015,
        },
        "ic": {
            "criteria": {
                "IC1": {"id": "IC1", "description": "Sources addressing R&S for SE roles.", "enabled": True, "keywords": [], "weight": 1.0},
                "IC2": {"id": "IC2", "description": "Sources describing SE R&S pipelines.", "enabled": True, "keywords": [], "weight": 1.0},
                "IC3": {"id": "IC3", "description": "Sources reporting challenges in SE R&S.", "enabled": True, "keywords": [], "weight": 1.0},
                "IC4": {"id": "IC4", "description": "Sources describing assessment methods in SE R&S.", "enabled": True, "keywords": [], "weight": 1.0},
                "IC5": {"id": "IC5", "description": "Sources with empirical findings on SE R&S.", "enabled": True, "keywords": [], "weight": 1.0},
            },
        },
    }


# ---------------------------------------------------------------------------
# Fixture generation
# ---------------------------------------------------------------------------

def generate_minimal_session():
    """minimal_session.json — canonical deterministic fixture, simplest valid session."""
    articles = [
        make_article_dict("ART001", "Test Paper A", "Abstract for paper A", {"literature_type": "WL", "year": "2020"}),
        make_article_dict("ART002", "Test Paper B", "Abstract for paper B", {"literature_type": "WL", "year": "2021"}),
    ]
    data = {
        "session_id": "minimal_session",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ec",
        "current_index": 0,
        "total_count": 2,
        "ec_completed": 0,
        "ic_completed": 0,
        "included_count": 0,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 0,
        "researcher_id": "researcher_1",
        "last_saved": "",
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": None,
        "audit_chain": [],
        "autosave_enabled": False,
    }
    generate_fixture(data, "minimal_session.json", SESSIONS_DIR)


def generate_ec_completed():
    """ec_completed.json — all EC decisions made, ready for IC."""
    articles = [
        make_article_dict(
            "ART001", "Included Paper", "Abstract included",
            {"literature_type": "WL", "year": "2020"},
            ec_stage="include", ec_notes="Passes EC1-EC6", ec_timestamp=FIXED_TIMESTAMP,
        ),
        make_article_dict(
            "ART002", "Excluded Paper", "Abstract excluded",
            {"literature_type": "WL", "year": "2014"},
            ec_stage="exclude", ec_notes="EC4: Published before 2015", ec_timestamp=FIXED_TIMESTAMP,
        ),
        make_article_dict(
            "ART003", "Discussion Paper", "Abstract discussion",
            {"literature_type": "GL", "year": "2022"},
            ec_stage="needs_discussion", ec_notes="Unclear year source", ec_timestamp=FIXED_TIMESTAMP,
        ),
    ]
    audit_chain = [
        make_audit_event(
            "evt-ec-001", FIXED_TIMESTAMP, "ART001", "researcher_1",
            "ec", "include", "Passes EC1-EC6", "GENESIS",
        ),
    ]
    evt1_hash = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event(
        "evt-ec-002", FIXED_TIMESTAMP, "ART002", "researcher_1",
        "ec", "exclude", "EC4: Published before 2015", evt1_hash,
    ))
    evt2_hash = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event(
        "evt-ec-003", FIXED_TIMESTAMP, "ART003", "researcher_1",
        "ec", "needs_discussion", "Unclear year source", evt2_hash,
    ))
    dp = make_default_protocol_dict()
    data = {
        "session_id": "ec_completed",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ec",
        "current_index": 3,
        "total_count": 3,
        "ec_completed": 3,
        "ic_completed": 0,
        "included_count": 1,
        "excluded_count": 1,
        "skip_count": 0,
        "discussion_count": 1,
        "researcher_id": "researcher_1",
        "last_saved": FIXED_LAST_SAVED,
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": dp,
        "audit_chain": audit_chain,
        "autosave_enabled": True,
    }
    generate_fixture(data, "ec_completed.json", SESSIONS_DIR)


def generate_ic_completed():
    """ic_completed.json — EC and IC fully completed, ready for QC."""
    articles = [
        make_article_dict(
            "ART001", "Fully Included", "Included at all stages",
            {"literature_type": "WL", "year": "2021"},
            ec_stage="include", ec_notes="Passes EC", ec_timestamp=FIXED_TIMESTAMP,
            ic_stage="include", ic_notes="Passes IC", ic_timestamp=FIXED_TIMESTAMP,
        ),
        make_article_dict(
            "ART002", "EC Excluded", "Excluded at EC",
            {"literature_type": "WL", "year": "2013"},
            ec_stage="exclude", ec_notes="EC4", ec_timestamp=FIXED_TIMESTAMP,
            ic_stage="", ic_notes="", ic_timestamp="",
        ),
        make_article_dict(
            "ART003", "IC Excluded", "Excluded at IC",
            {"literature_type": "WL", "year": "2022"},
            ec_stage="include", ec_notes="Passes EC", ec_timestamp=FIXED_TIMESTAMP,
            ic_stage="exclude", ic_notes="IC5: No empirical findings", ic_timestamp=FIXED_TIMESTAMP,
        ),
        make_article_dict(
            "ART004", "Discussion at IC", "Discussion at IC stage",
            {"literature_type": "GL", "year": "2023"},
            ec_stage="include", ec_notes="Passes EC", ec_timestamp=FIXED_TIMESTAMP,
            ic_stage="needs_discussion", ic_notes="Team review needed", ic_timestamp=FIXED_TIMESTAMP,
        ),
    ]
    audit_chain = [
        make_audit_event("evt-001", FIXED_TIMESTAMP, "ART001", "researcher_1", "ec", "include", "Passes EC", "GENESIS"),
    ]
    h1 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-002", FIXED_TIMESTAMP, "ART002", "researcher_1", "ec", "exclude", "EC4", h1))
    h2 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-003", FIXED_TIMESTAMP, "ART003", "researcher_1", "ec", "include", "Passes EC", h2))
    h3 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-004", FIXED_TIMESTAMP, "ART004", "researcher_1", "ec", "include", "Passes EC", h3))
    h4 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-005", FIXED_TIMESTAMP, "ART001", "researcher_1", "ic", "include", "Passes IC", h4))
    h5 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-006", FIXED_TIMESTAMP, "ART003", "researcher_1", "ic", "exclude", "IC5", h5))
    h6 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-007", FIXED_TIMESTAMP, "ART004", "researcher_1", "ic", "needs_discussion", "Team review needed", h6))

    dp = make_default_protocol_dict()
    data = {
        "session_id": "ic_completed",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ic",
        "current_index": 3,
        "total_count": 4,
        "ec_completed": 4,
        "ic_completed": 3,
        "included_count": 2,
        "excluded_count": 1,
        "skip_count": 0,
        "discussion_count": 1,
        "researcher_id": "researcher_1",
        "last_saved": FIXED_LAST_SAVED,
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": dp,
        "audit_chain": audit_chain,
        "autosave_enabled": True,
    }
    generate_fixture(data, "ic_completed.json", SESSIONS_DIR)


def generate_discussion_heavy():
    """discussion_heavy.json — many needs_discussion decisions."""
    articles = []
    audit_chain = []
    prev_hash = "GENESIS"
    for i in range(1, 9):
        aid = f"ART{i:03d}"
        is_discussion = i <= 6
        decision = "needs_discussion" if is_discussion else "include"
        notes = f"Discussion needed: unclear criteria match for {aid}" if is_discussion else "Clearly passes"
        articles.append(make_article_dict(
            aid, f"Discussion Paper {i}", f"Abstract for paper {i}",
            {"literature_type": "WL" if i % 2 == 1 else "GL", "year": str(2020 + i)},
            ec_stage=decision, ec_notes=notes, ec_timestamp=FIXED_TIMESTAMP,
        ))
        evt = make_audit_event(f"evt-disc-{i:03d}", FIXED_TIMESTAMP, aid, "researcher_1", "ec", decision, notes, prev_hash)
        audit_chain.append(evt)
        prev_hash = evt["current_hash"]

    dp = make_default_protocol_dict()
    data = {
        "session_id": "discussion_heavy",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ec",
        "current_index": 8,
        "total_count": 8,
        "ec_completed": 8,
        "ic_completed": 0,
        "included_count": 2,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 6,
        "researcher_id": "researcher_1",
        "last_saved": FIXED_LAST_SAVED,
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": dp,
        "audit_chain": audit_chain,
        "autosave_enabled": True,
    }
    generate_fixture(data, "discussion_heavy.json", SESSIONS_DIR)


def generate_broken_audit_chain():
    """broken_audit_chain.json — corrupted fixture with broken audit chain."""
    articles = [
        make_article_dict("ART001", "Paper A", "Abstract A", {"literature_type": "WL", "year": "2020"},
                          ec_stage="include", ec_notes="OK", ec_timestamp=FIXED_TIMESTAMP),
        make_article_dict("ART002", "Paper B", "Abstract B", {"literature_type": "WL", "year": "2021"},
                          ec_stage="include", ec_notes="OK", ec_timestamp=FIXED_TIMESTAMP),
    ]
    audit_chain = [
        make_audit_event("evt-001", FIXED_TIMESTAMP, "ART001", "researcher_1", "ec", "include", "OK", "GENESIS"),
    ]
    h1 = audit_chain[-1]["current_hash"]
    audit_chain.append(make_audit_event("evt-002", FIXED_TIMESTAMP, "ART002", "researcher_1", "ec", "include", "OK", h1))
    # Corrupt the second event's current_hash
    audit_chain[1]["current_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"

    data = {
        "session_id": "broken_audit_chain",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ec",
        "current_index": 2,
        "total_count": 2,
        "ec_completed": 2,
        "ic_completed": 0,
        "included_count": 2,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 0,
        "researcher_id": "researcher_1",
        "last_saved": FIXED_LAST_SAVED,
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": None,
        "audit_chain": audit_chain,
        "autosave_enabled": False,
    }
    generate_fixture(data, "broken_audit_chain.json", CORRUPTED_DIR)


def generate_tampered_checksum():
    """tampered_checksum.json — corrupted fixture with wrong checksum."""
    articles = [
        make_article_dict("ART001", "Paper A", "Abstract A", {"literature_type": "WL", "year": "2020"}),
    ]
    data = {
        "session_id": "tampered_checksum",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ec",
        "current_index": 0,
        "total_count": 1,
        "ec_completed": 0,
        "ic_completed": 0,
        "included_count": 0,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 0,
        "researcher_id": "researcher_1",
        "last_saved": "",
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": None,
        "audit_chain": [],
        "autosave_enabled": False,
    }
    # Set intentionally wrong checksum
    data["session_checksum"] = "00" * 32
    path = os.path.join(CORRUPTED_DIR, "tampered_checksum.json")
    os.makedirs(CORRUPTED_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Created: {path}")


def generate_invalid_stage_transition():
    """invalid_stage_transition.json — corrupted fixture with invalid stage."""
    articles = [
        make_article_dict("ART001", "Paper A", "Abstract A", {"literature_type": "WL", "year": "2020"}),
    ]
    data = {
        "session_id": "invalid_stage_transition",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "qc",
        "current_index": 0,
        "total_count": 1,
        "ec_completed": 0,
        "ic_completed": 0,
        "included_count": 0,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 0,
        "researcher_id": "researcher_1",
        "last_saved": "",
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": None,
        "audit_chain": [],
        "autosave_enabled": False,
    }
    generate_fixture(data, "invalid_stage_transition.json", CORRUPTED_DIR)


def generate_legacy_schema_session():
    """legacy_schema_session.json — migration fixture with old schema_version."""
    articles = [
        make_article_dict("LEGACY001", "Legacy Paper", "Legacy abstract",
                          {"literature_type": "WL", "year": "2019"}),
    ]
    data = {
        "session_id": "legacy_schema_session",
        "created_at": "2024-06-01T08:00:00",
        "protocol_version": "0.9",
        "stage": "ec",
        "current_index": 0,
        "total_count": 1,
        "ec_completed": 0,
        "ic_completed": 0,
        "included_count": 0,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 0,
        "researcher_id": "researcher_legacy",
        "last_saved": "",
        "schema_version": "1.0",
        "articles": articles,
        "dynamic_protocol": None,
        "audit_chain": [],
        "autosave_enabled": False,
    }
    generate_fixture(data, "legacy_schema_session.json", MIGRATIONS_DIR)


def generate_large_scale_session():
    """large_scale_session.json — 1000+ articles for scale benchmarking."""
    articles = []
    audit_chain = []
    prev_hash = "GENESIS"
    for i in range(1, 1001):
        aid = f"SCALE{i:04d}"
        lit_type = "WL" if i <= 500 else "GL"
        articles.append(make_article_dict(
            aid, f"Scale Paper {i}", f"Abstract for scale paper {i}",
            {"literature_type": lit_type, "year": str(2015 + (i % 10))},
        ))
    data = {
        "session_id": "large_scale_session",
        "created_at": FIXED_TIMESTAMP,
        "protocol_version": "1.0",
        "stage": "ec",
        "current_index": 0,
        "total_count": 1000,
        "ec_completed": 0,
        "ic_completed": 0,
        "included_count": 0,
        "excluded_count": 0,
        "skip_count": 0,
        "discussion_count": 0,
        "researcher_id": "researcher_1",
        "last_saved": "",
        "schema_version": "2.0",
        "articles": articles,
        "dynamic_protocol": None,
        "audit_chain": audit_chain,
        "autosave_enabled": False,
    }
    generate_fixture(data, "large_scale_session.json", SCALE_DIR)


def main():
    print("Generating replay corpus fixtures...")
    os.makedirs(REPLAY_CORPUS_DIR, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(CORRUPTED_DIR, exist_ok=True)
    os.makedirs(MIGRATIONS_DIR, exist_ok=True)
    os.makedirs(SCALE_DIR, exist_ok=True)
    os.makedirs(COMPATIBILITY_DIR, exist_ok=True)

    print("\n--- Canonical Deterministic Fixtures ---")
    generate_minimal_session()
    generate_ec_completed()
    generate_ic_completed()
    generate_discussion_heavy()

    print("\n--- Corrupted Fixtures ---")
    generate_broken_audit_chain()
    generate_tampered_checksum()
    generate_invalid_stage_transition()

    print("\n--- Migration Fixtures ---")
    generate_legacy_schema_session()

    print("\n--- Scale Fixtures ---")
    generate_large_scale_session()

    print("\nFixture generation complete.")


if __name__ == "__main__":
    main()
