"""
Comprehensive Protocol Parity Test - v1.0.0
Validates: default_behavior == protocol(get_default_protocol())

Strictly verifies that the dynamic protocol engine produces identical 
results to the hardcoded fallbacks across EC, IC, and QC.

V1.0.0 UPDATES:
- GL Policy: Updated to expect 'PENDING' instead of 'SKIPPED' (HITL compliance).
- Path Independence: Removed absolute paths for portability.
- Zero Tolerance: Maintained for both WL and GL literature types.
"""
import sys
import os
import pandas as pd
from pathlib import Path

# Setup path independently
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.atlas_processor import APOLLODecisionEngine, ATLASLoader
from src.core.protocol_engine import get_default_protocol


def create_test_dataframe(data: list) -> pd.DataFrame:
    """Helper to create test DataFrames."""
    return pd.DataFrame(data)


def test_ec1_semantic_parity():
    """Test EC1: contains_any semantics produces exact default behavior."""
    print("\n=== TEST EC1: Semantic Parity ===")
    
    test_cases = [
        {
            "name": "No SE keywords - should exclude",
            "title": "A Study of Human Resources",
            "abstract": "This paper examines hiring practices in manufacturing companies.",
        },
        {
            "name": "Has SE keyword - should include",
            "title": "Software Developer Recruitment",
            "abstract": "We investigate hiring practices in software companies.",
        }
    ]
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    for i, case in enumerate(test_cases):
        wl_df = create_test_dataframe([{
            "Library": "Test",
            "Global_ID": f"TEST-{i}",
            "Local_ID": f"TEST-{i}",
            "Title": case["title"],
            "Abstract": case["abstract"],
            "Keywords": ""
        }])
        wl_df = ATLASLoader.normalize_wl_columns(wl_df)
        
        results_default = engine_default.process_wl_articles(wl_df)
        results_protocol = engine_protocol.process_wl_articles(wl_df)
        
        default_ec = results_default[0].ec_decision
        protocol_ec = results_protocol[0].ec_decision
        
        print(f"  Case: {case['name']} -> Default: {default_ec} | Protocol: {protocol_ec}")
        
        if default_ec != protocol_ec:
            print(f"    FAIL: EC1 mismatch!")
            return False
    return True


def test_ec4_duplicate_propagation():
    """Test EC4: Duplicate detection propagates correctly into protocol."""
    print("\n=== TEST EC4: Duplicate Propagation ===")
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    base_article = {
        "Library": "Test",
        "Global_ID": "DUPLICATE-ID",
        "Title": "Software Development Hiring",
        "Abstract": "Engineering recruitment practices.",
        "Keywords": ""
    }
    
    wl_df = create_test_dataframe([base_article, base_article]) # Two identical Global_IDs
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    
    # We must enable duplicate check in ExclusionCriteria for this test
    from src.core.atlas_processor import ExclusionCriteria
    ExclusionCriteria.ENABLE_DUPLICATE_CHECK = True
    
    results_default = engine_default.process_wl_articles(wl_df)
    results_protocol = engine_protocol.process_wl_articles(wl_df)
    
    # Second article should be EC4 in both
    d2 = results_default[1].ec_decision
    p2 = results_protocol[1].ec_decision
    
    print(f"  Duplicate Article -> Default: {d2} | Protocol: {p2}")
    return d2 == p2


def test_qc_scoring_exact():
    """Test QC: Exact scoring matches default."""
    print("\n=== TEST QC: Scoring Cascade ===")
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    wl_df = create_test_dataframe([{
        "Title": "Research aim methodology",
        "Abstract": "We demonstrate findings and limitations.",
        "Global_ID": "QC-TEST"
    }])
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    
    r_default = engine_default.process_wl_articles(wl_df)[0]
    r_protocol = engine_protocol.process_wl_articles(wl_df)[0]
    
    print(f"  Scores -> Default: {r_default.qc_score} | Protocol: {r_protocol.qc_score}")
    return r_default.qc_score == r_protocol.qc_score


def test_gl_hitl_policy_parity():
    """
    Test GL: PENDING policy preservation.
    Crucial for HITL (Human-in-the-Loop) methodology.
    """
    print("\n=== TEST GL: PENDING Policy Parity ===")
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    gl_df = create_test_dataframe([
        {"Title": "Software Hiring Guide", "URL": "http://x.com", "Source_File": "test.txt"}
    ])
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    r_def = engine_default.process_gl_articles(gl_df)[0]
    r_pro = engine_protocol.process_gl_articles(gl_df)[0]
    
    print(f"  GL Policy -> Default IC: {r_def.ic_decision} | Protocol IC: {r_pro.ic_decision}")
    
    # Both must be PENDING, and they must be equal
    if r_def.ic_decision != "PENDING" or r_pro.ic_decision != "PENDING":
        print("    FAIL: GL Policy is not PENDING")
        return False
        
    return r_def.ic_decision == r_pro.ic_decision


def test_full_pipeline_comparison():
    """Full comparison using sample input file."""
    print("\n=== TEST Full Pipeline Comparison ===")
    
    input_file = "tests/atlas_sample_input.xlsx"
    if not os.path.exists(input_file):
        print(f"  SKIP: Sample file {input_file} not found.")
        return True

    wl_df, gl_df = ATLASLoader.load_atlas_file(input_file)
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    wl_def = engine_default.process_wl_articles(wl_df)
    wl_pro = engine_protocol.process_wl_articles(wl_df)
    gl_def = engine_default.process_gl_articles(gl_df)
    gl_pro = engine_protocol.process_gl_articles(gl_df)
    
    # Check WL Parity
    for i in range(len(wl_def)):
        if wl_def[i].final_decision != wl_pro[i].final_decision:
            print(f"  FAIL: WL Parity Mismatch at index {i}")
            return False
            
    # Check GL Parity
    for i in range(len(gl_def)):
        if gl_def[i].ic_decision != gl_pro[i].ic_decision:
            print(f"  FAIL: GL Parity Mismatch at index {i}")
            return False
            
    print(f"  PASS: Zero divergence across {len(wl_def) + len(gl_def)} articles.")
    return True


def main():
    print("=" * 60)
    print("APOLLO PROTOCOL PARITY TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("EC1 Semantic", test_ec1_semantic_parity),
        ("EC4 Duplicates", test_ec4_duplicate_propagation),
        ("QC Scoring", test_qc_scoring_exact),
        ("GL HITL Policy", test_gl_hitl_policy_parity),
        ("Full Comparison", test_full_pipeline_comparison),
    ]
    
    success = True
    for name, func in tests:
        if not func():
            print(f"\n>>> TEST FAILED: {name}")
            success = False
            break
            
    print("\n" + "=" * 60)
    if success:
        print("OVERALL RESULT: PASS")
        sys.exit(0)
    else:
        print("OVERALL RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()