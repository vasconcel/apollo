"""
Test protocol layer produces identical results to default behavior.
"""
import pandas as pd
import sys
sys.path.insert(0, 'D:/Projetos/apollo')

from src.core.atlas_processor import APOLLODecisionEngine, ATLASLoader
from src.core.protocol_engine import get_default_protocol, load_protocol

# Load test data
wl_df = pd.read_excel("tests/atlas_sample_input.xlsx", sheet_name="White Literature")
gl_df = pd.read_excel("tests/atlas_sample_input.xlsx", sheet_name="Grey Literature")
wl_df = ATLASLoader.normalize_wl_columns(wl_df)
gl_df = ATLASLoader.normalize_gl_columns(gl_df)

# Run WITHOUT protocol (default behavior)
print("Testing: Default behavior (no protocol)...")
engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
wl_default = engine_default.process_wl_articles(wl_df)
gl_default = engine_default.process_gl_articles(gl_df)

# Run WITH default protocol
print("Testing: Protocol-driven evaluation...")
protocol = get_default_protocol()
engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
wl_protocol = engine_protocol.process_wl_articles(wl_df)
gl_protocol = engine_protocol.process_gl_articles(gl_df)

# Compare results
print("\n=== COMPARISON ===")
differences = 0

for i, (r_default, r_protocol) in enumerate(zip(wl_default, wl_protocol)):
    diffs = []
    if r_default.ec_decision != r_protocol.ec_decision:
        diffs.append(f"EC: {r_default.ec_decision} != {r_protocol.ec_decision}")
    if r_default.ic_decision != r_protocol.ic_decision:
        diffs.append(f"IC: {r_default.ic_decision} != {r_protocol.ic_decision}")
    if r_default.qc_score != r_protocol.qc_score:
        diffs.append(f"QC: {r_default.qc_score} != {r_protocol.qc_score}")
    if r_default.final_decision != r_protocol.final_decision:
        diffs.append(f"Decision: {r_default.final_decision} != {r_protocol.final_decision}")
    
    if diffs:
        print(f"Row {i+1} ({r_default.title[:40]}...): {', '.join(diffs)}")
        differences += 1

for i, (r_default, r_protocol) in enumerate(zip(gl_default, gl_protocol)):
    diffs = []
    if r_default.ec_decision != r_protocol.ec_decision:
        diffs.append(f"EC: {r_default.ec_decision} != {r_protocol.ec_decision}")
    if r_default.ic_decision != r_protocol.ic_decision:
        diffs.append(f"IC: {r_default.ic_decision} != {r_protocol.ic_decision}")
    
    if diffs:
        print(f"GL Row {i+1}: {', '.join(diffs)}")
        differences += 1

if differences == 0:
    print("PASS: Protocol layer produces identical results to default behavior")
    print("\nProtocol integration is working correctly!")
    sys.exit(0)
else:
    print(f"\nFAIL: Found {differences} differences")
    sys.exit(1)