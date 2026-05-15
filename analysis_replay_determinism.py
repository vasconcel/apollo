import os
import json
import tempfile
import hashlib
from datetime import datetime

os.chdir(r'D:\Projetos\apollo')

from src.core.screening_session import ScreeningSession, ArticleReview
from src.core.reproducibility_engine import (
    create_reproducibility_bundle,
    ReplayEngine
)

def deep_diff(obj1, obj2, path=""):
    """Recursively compare two objects and return differences."""
    diffs = []
    
    if type(obj1) != type(obj2):
        diffs.append({
            "path": path,
            "type_mismatch": True,
            "type1": type(obj1).__name__,
            "type2": type(obj2).__name__,
            "value1": repr(obj1),
            "value2": repr(obj2)
        })
        return diffs
    
    if isinstance(obj1, dict):
        all_keys = set(obj1.keys()) | set(obj2.keys())
        for key in sorted(all_keys):
            new_path = f"{path}.{key}" if path else key
            if key not in obj1:
                diffs.append({
                    "path": new_path,
                    "missing_in_original": True,
                    "value2": obj2[key]
                })
            elif key not in obj2:
                diffs.append({
                    "path": new_path,
                    "missing_in_replay": True,
                    "value1": obj1[key]
                })
            else:
                diffs.extend(deep_diff(obj1[key], obj2[key], new_path))
    elif isinstance(obj1, list):
        if len(obj1) != len(obj2):
            diffs.append({
                "path": path,
                "length_mismatch": True,
                "len1": len(obj1),
                "len2": len(obj2)
            })
        else:
            for i in range(len(obj1)):
                diffs.extend(deep_diff(obj1[i], obj2[i], f"{path}[{i}]"))
    else:
        if obj1 != obj2:
            diffs.append({
                "path": path,
                "value1": obj1,
                "value2": obj2
            })
    
    return diffs

def serialize_session_full(session):
    """Serialize session for analysis."""
    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "protocol_version": session.protocol_version,
        "stage": session.stage,
        "current_index": session.current_index,
        "total_count": session.total_count,
        "ec_completed": session.ec_completed,
        "ic_completed": session.ic_completed,
        "included_count": session.included_count,
        "excluded_count": session.excluded_count,
        "skip_count": session.skip_count,
        "discussion_count": session.discussion_count,
        "researcher_id": session.researcher_id,
        "last_saved": session.last_saved,
        "schema_version": session.schema_version,
        "articles": [a.to_dict() for a in session.articles],
        "dynamic_protocol": session.dynamic_protocol,
        "audit_chain": session._audit_chain
    }

original_session = ScreeningSession(
    session_id='replay-test',
    created_at='2026-05-14T10:00:00',
    protocol_version='1.0'
)

original_session.articles.append(
    ArticleReview(
        'A-1',
        'T',
        'A',
        {'literature_type': 'WL'}
    )
)

original_session.record_decision('include', notes='Test')

original_data = serialize_session_full(original_session)
original_checksum = original_session.compute_checksum()

print("=" * 80)
print("ORIGINAL SESSION")
print("=" * 80)
print(f"Checksum: {original_checksum}")
print(f"last_saved: {original_session.last_saved}")
print(f"Audit chain events: {len(original_session._audit_chain)}")
if original_session._audit_chain:
    print(f"Audit event 0 timestamp: {original_session._audit_chain[0].get('timestamp')}")
    print(f"Audit event 0 event_id: {original_session._audit_chain[0].get('event_id')}")
    print(f"Audit event 0 current_hash: {original_session._audit_chain[0].get('current_hash')}")
print(f"Article ec_timestamp: {original_session.articles[0].ec_timestamp if original_session.articles else 'N/A'}")

replay_sessions = []

for run in range(3):
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = create_reproducibility_bundle(original_session, tmpdir)
        
        replayed, _ = ReplayEngine.replay_session(bundle.bundle_path)
        
        replay_data = serialize_session_full(replayed)
        replay_checksum = replayed.compute_checksum()
        
        replay_sessions.append({
            "run": run + 1,
            "checksum": replay_checksum,
            "session": replayed,
            "data": replay_data,
            "bundle_path": bundle.bundle_path
        })
        
        print(f"\n{'=' * 80}")
        print(f"REPLAY RUN #{run + 1}")
        print(f"{'=' * 80}")
        print(f"Checksum: {replay_checksum}")
        print(f"last_saved: {replayed.last_saved}")
        print(f"Audit chain events: {len(replayed._audit_chain)}")
        if replayed._audit_chain:
            print(f"Audit event 0 timestamp: {replayed._audit_chain[0].get('timestamp')}")
            print(f"Audit event 0 event_id: {replayed._audit_chain[0].get('event_id')}")
            print(f"Audit event 0 current_hash: {replayed._audit_chain[0].get('current_hash')}")
        print(f"Article ec_timestamp: {replayed.articles[0].ec_timestamp if replayed.articles else 'N/A'}")

print(f"\n{'=' * 80}")
print("COMPARISON: Original vs Replay Run #1")
print(f"{'=' * 80}")

diffs = deep_diff(original_data, replay_sessions[0]["data"])

print(f"\nTotal differences found: {len(diffs)}")
print("\n--- DETAILED DIFFERENCES ---")
for d in diffs:
    print(f"\nPath: {d.get('path', 'N/A')}")
    if 'value1' in d:
        print(f"  Original: {d['value1']}")
    if 'value2' in d:
        print(f"  Replay:   {d['value2']}")
    if d.get('missing_in_original'):
        print(f"  MISSING IN ORIGINAL")
    if d.get('missing_in_replay'):
        print(f"  MISSING IN REPLAY")

print(f"\n{'=' * 80}")
print("CHECKSUM COMPARISON")
print(f"{'=' * 80}")
print(f"Original checksum: {original_checksum}")
for rs in replay_sessions:
    print(f"Replay run {rs['run']} checksum: {rs['checksum']}")

all_checksums = [original_checksum] + [rs["checksum"] for rs in replay_sessions]
print(f"\nAll identical: {len(set(all_checksums)) == 1}")

print(f"\n{'=' * 80}")
print("REPLAY RUN COMPARISON (Run #1 vs Run #2 vs Run #3)")
print(f"{'=' * 80}")

for i in range(len(replay_sessions) - 1):
    diffs_replay = deep_diff(replay_sessions[i]["data"], replay_sessions[i+1]["data"])
    print(f"\nRun #{replay_sessions[i]['run']} vs Run #{replay_sessions[i+1]['run']}: {len(diffs_replay)} differences")
    for d in diffs_replay[:5]:
        print(f"  {d.get('path')}: {d.get('value1')} vs {d.get('value2')}")

print(f"\n{'=' * 80}")
print("FIELD-LEVEL ANALYSIS")
print(f"{'=' * 80}")

transient_fields = []
timestamp_drift_fields = []
audit_chain_fields = []
uuid_fields = []

for d in diffs:
    path = d.get('path', '')
    if 'timestamp' in path.lower() or 'last_saved' in path.lower():
        timestamp_drift_fields.append(path)
    elif 'audit_chain' in path.lower():
        audit_chain_fields.append(path)
    elif 'uuid' in path.lower() or 'event_id' in path.lower():
        uuid_fields.append(path)
    else:
        transient_fields.append(path)

print(f"\nTimestamp drift fields: {timestamp_drift_fields}")
print(f"Audit chain fields: {audit_chain_fields}")
print(f"UUID fields: {uuid_fields}")
print(f"Other transient fields: {transient_fields}")

print(f"\n{'=' * 80}")
print("ROOT CAUSE SUMMARY")
print(f"{'=' * 80}")

print("""
1. BUNDLE CREATION (ReproducibilityEngine.create_bundle):
   - Uses datetime.now().isoformat() for multiple timestamps:
     * bundle_id generation (line 86-88)
     * created_at in ReproducibilityBundle (line 111)
     * bundle_export_timestamp in protocol (line 135)
     * bundle_export_timestamp in session (line 147)
     * exported_at in audit_log (line 159)
     * export_timestamp in environment (line 177)
     * timestamp in export filenames (line 195)
     * created_at in manifest (line 229)
     * export_timestamp in manifest (line 245)

2. SESSION RECORD_DECISION (screening_session.py line 404):
   - Sets ec_timestamp/ic_timestamp to datetime.now().isoformat()
   - These timestamps become part of article data

3. AUDIT CHAIN EVENTS (screening_session.py _append_audit_event):
   - Line 444: event_id = str(uuid.uuid4()) - NEW UUID each run
   - Line 445: timestamp = datetime.now().isoformat() - DIFFERENT each run
   - Line 454-456: current_hash depends on timestamp, so changes each run

4. REPLAY LOADING (ReplayEngine.replay_session):
   - Reconstructs session from bundle JSON
   - last_saved field comes from bundle, but may differ if bundle has export timestamp
   - audit_chain is restored but contains event_id/timestamp from ORIGINAL session
   - The checksum computation includes last_saved which differs from original

5. CHECKSUM COMPUTATION (compute_checksum in screening_session.py):
   - Uses fields including 'last_saved' (line 884)
   - last_saved differs between original and replay because:
     * Original: set to timestamp when record_decision was called
     * Replay: restored from bundle which may have bundle_export_timestamp
""")

with open("replay_analysis_output.json", "w") as f:
    analysis = {
        "original": {
            "checksum": original_checksum,
            "data": original_data
        },
        "replays": [
            {
                "run": rs["run"],
                "checksum": rs["checksum"],
                "data": rs["data"]
            }
            for rs in replay_sessions
        ],
        "diffs": diffs,
        "timestamp_drift_fields": timestamp_drift_fields,
        "audit_chain_fields": audit_chain_fields,
        "uuid_fields": uuid_fields,
        "other_transient": transient_fields
    }
    json.dump(analysis, f, indent=2)

print("\nAnalysis saved to replay_analysis_output.json")