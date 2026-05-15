import os
import json
import tempfile

os.chdir(r'D:\Projetos\apollo')

from src.core.screening_session import ScreeningSession, ArticleReview
from src.core.reproducibility_engine import (
    create_reproducibility_bundle,
    ReplayEngine
)

def serialize_session_checksum_fields(session):
    """Serialize only fields used in checksum computation."""
    data = session._to_dict_full()
    fields_for_checksum = [
        "session_id", "created_at", "protocol_version", "stage",
        "current_index", "total_count", "ec_completed", "ic_completed",
        "included_count", "excluded_count", "skip_count",
        "discussion_count", "researcher_id", "last_saved", "schema_version",
        "articles", "dynamic_protocol"
    ]
    return {k: data.get(k) for k in fields_for_checksum if k in data}

def print_session_state(label, session):
    print(f"\n{label}")
    print("-" * 40)
    data = serialize_session_checksum_fields(session)
    print(f"  session_id: {data.get('session_id')}")
    print(f"  created_at: {data.get('created_at')}")
    print(f"  last_saved: {data.get('last_saved')}")
    print(f"  stage: {data.get('stage')}")
    print(f"  current_index: {data.get('current_index')}")
    print(f"  total_count: {data.get('total_count')}")
    print(f"  ec_completed: {data.get('ec_completed')}")
    print(f"  ic_completed: {data.get('ic_completed')}")
    print(f"  included_count: {data.get('included_count')}")
    print(f"  excluded_count: {data.get('excluded_count')}")
    print(f"  skip_count: {data.get('skip_count')}")
    print(f"  discussion_count: {data.get('discussion_count')}")
    print(f"  researcher_id: {data.get('researcher_id')}")
    print(f"  schema_version: {data.get('schema_version')}")
    print(f"  articles count: {len(data.get('articles', []))}")
    print(f"  dynamic_protocol: {data.get('dynamic_protocol')}")
    
    full_data = session._to_dict_full()
    print(f"  audit_chain count: {len(full_data.get('audit_chain', []))}")

print("=" * 80)
print("TESTING WITH FRESH SESSIONS (like replay_check.py)")
print("=" * 80)

replay_checksums = []
bundle_paths = []

for run in range(3):
    print(f"\n{'='*60}")
    print(f"RUN #{run + 1}: Creating fresh session")
    print(f"{'='*60}")
    
    session = ScreeningSession(
        session_id='replay-test',
        created_at='2026-05-14T10:00:00',
        protocol_version='1.0'
    )
    
    session.articles.append(
        ArticleReview(
            'A-1',
            'T',
            'A',
            {'literature_type': 'WL'}
        )
    )
    
    print(f"Before record_decision - last_saved: '{session.last_saved}'")
    
    session.record_decision('include', notes='Test')
    
    print(f"After record_decision - last_saved: '{session.last_saved}'")
    
    original_checksum = session.compute_checksum()
    print(f"Original session checksum: {original_checksum}")
    print_session_state(f"Original Session State (Run {run+1})", session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = create_reproducibility_bundle(session, tmpdir)
        bundle_paths.append(bundle.bundle_path)
        
        print(f"\nBundle created at: {bundle.bundle_path}")
        
        session_json_path = os.path.join(bundle.bundle_path, "session.json")
        with open(session_json_path, 'r') as f:
            bundle_session_data = json.load(f)
        
        print(f"\nBundle session.json keys: {list(bundle_session_data.keys())}")
        print(f"  bundle_export_timestamp: {bundle_session_data.get('bundle_export_timestamp', 'NOT PRESENT')}")
        print(f"  last_saved: {bundle_session_data.get('last_saved', 'NOT PRESENT')}")
        
        replayed, _ = ReplayEngine.replay_session(bundle.bundle_path)
        
        print(f"\nReplayed session - last_saved: '{replayed.last_saved}'")
        
        replay_checksum = replayed.compute_checksum()
        replay_checksums.append(replay_checksum)
        
        print(f"Replayed session checksum: {replay_checksum}")
        print_session_state(f"Replayed Session State (Run {run+1})", replayed)

print(f"\n{'='*80}")
print("RESULTS")
print(f"{'='*80}")
print(f"\nReplay checksums:")
for i, c in enumerate(replay_checksums):
    print(f"  Run #{i+1}: {c}")

print(f"\nAll identical: {len(set(replay_checksums)) == 1}")

print(f"\n{'='*80}")
print("COMPARING bundle_export_timestamp vs last_saved")
print(f"{'='*80}")

for i, bp in enumerate(bundle_paths):
    sj = os.path.join(bp, "session.json")
    with open(sj, 'r') as f:
        d = json.load(f)
    print(f"Run #{i+1}:")
    print(f"  bundle_export_timestamp: {d.get('bundle_export_timestamp', 'MISSING')}")
    print(f"  last_saved: {d.get('last_saved', 'MISSING')}")