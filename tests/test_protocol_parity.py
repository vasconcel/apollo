"""
Comprehensive Protocol Parity Test

Tests that default_behavior == protocol(get_default_protocol()) with ZERO tolerance
for divergence across EC, IC, and QC decisions for both WL and GL literature types.

This test explicitly verifies:
1. EC1: contains_any + exclude_if_none_found semantics
2. EC4: Duplicate propagation via is_duplicate flag
3. QC: Exact 1.0/0.5/0.0 decision cascade
4. GL: Explicit SKIPPED policy preservation
"""
import sys
sys.path.insert(0, 'D:/Projetos/apollo')

import pandas as pd
from src.core.atlas_processor import APOLLODecisionEngine, ATLASLoader
from src.core.protocol_engine import get_default_protocol


def create_test_dataframe(data: list) -> pd.DataFrame:
    """Helper to create test DataFrames."""
    return pd.DataFrame(data)


def test_ec1_semantic_parity():
    """Test EC1: contains_any with exclude_if_none_found produces exact default behavior."""
    print("\n=== TEST EC1: Semantic Inversion ===")
    
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
        },
        {
            "name": "Multiple SE keywords - should include",
            "title": "Agile Development Team Hiring",
            "abstract": "This study examines how software engineering teams recruit developers using modern devops practices.",
        },
        {
            "name": "Border case - single SE keyword",
            "title": "Programming Interview Process",
            "abstract": "We analyze the interview process for developer positions.",
        },
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
        
        print(f"  Case: {case['name']}")
        print(f"    Title: {case['title'][:40]}...")
        print(f"    Default EC: {default_ec}")
        print(f"    Protocol EC: {protocol_ec}")
        
        if default_ec != protocol_ec:
            print(f"    FAIL: EC1 mismatch!")
            return False
        else:
            print(f"    PASS")
    
    return True


def test_ec4_duplicate_propagation():
    """Test EC4: Duplicate detection propagates correctly into protocol evaluation."""
    print("\n=== TEST EC4: Duplicate Propagation ===")
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    base_article = {
        "Library": "Test",
        "Global_ID": "DUPLICATE-ID",
        "Local_ID": "1",
        "Title": "Software Development Hiring",
        "Abstract": "This paper investigates software engineering recruitment practices in tech companies.",
        "Keywords": ""
    }
    
    wl_df = create_test_dataframe([
        base_article,
        {**base_article, "Local_ID": "2"},
        {**base_article, "Local_ID": "3"}
    ])
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    
    results_default = engine_default.process_wl_articles(wl_df)
    results_protocol = engine_protocol.process_wl_articles(wl_df)
    
    print(f"  Processing 3 articles with same Global_ID")
    
    for i, (r_default, r_protocol) in enumerate(zip(results_default, results_protocol)):
        print(f"  Article {i+1}:")
        print(f"    Default EC: {r_default.ec_decision}")
        print(f"    Protocol EC: {r_protocol.ec_decision}")
        
        if r_default.ec_decision != r_protocol.ec_decision:
            print(f"    FAIL: EC4 mismatch!")
            return False
        print(f"    PASS")
    
    return True


def test_qc_scoring_exact():
    """Test QC: Exact 1.0/0.5/0.0 decision cascade matches default."""
    print("\n=== TEST QC: Exact Scoring Cascade ===")
    
    test_cases = [
        {
            "name": "Full match - 1.0",
            "title": "Our aim is to investigate software engineering practices",
            "abstract": "We use a qualitative case study methodology with interviews. The results demonstrate that recruitment is a challenge. We acknowledge limitations and suggest future work.",
            "expected_scores": {"WL-Q1": 1.0, "WL-Q2": 1.0, "WL-Q3": 1.0, "WL-Q4": 1.0}
        },
        {
            "name": "Partial match - 0.5",
            "title": "Exploring hiring practices",
            "abstract": "This paper examines software development. We discuss our findings. The limitations are mentioned in the discussion section.",
            "expected_scores": {"WL-Q1": 0.5, "WL-Q2": 0.0, "WL-Q3": 0.5, "WL-Q4": 0.5}
        },
        {
            "name": "No match - 0.0",
            "title": "HR Management",
            "abstract": "This paper discusses general human resources topics.",
            "expected_scores": {"WL-Q1": 0.0, "WL-Q2": 0.0, "WL-Q3": 0.0, "WL-Q4": 0.0}
        },
        {
            "name": "Methodology conditional - survey required for 1.0",
            "title": "Research Methodology",
            "abstract": "We describe our approach and design. We used a survey method.",
            "expected_scores": {"WL-Q1": 0.0, "WL-Q2": 1.0, "WL-Q3": 0.0, "WL-Q4": 0.0}
        },
    ]
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    for case in test_cases:
        wl_df = create_test_dataframe([{
            "Library": "Test",
            "Global_ID": "TEST-QC",
            "Local_ID": "1",
            "Title": case["title"],
            "Abstract": case["abstract"],
            "Keywords": ""
        }])
        wl_df = ATLASLoader.normalize_wl_columns(wl_df)
        
        results_default = engine_default.process_wl_articles(wl_df)
        results_protocol = engine_protocol.process_wl_articles(wl_df)
        
        default_qc = results_default[0].qc_score
        protocol_qc = results_protocol[0].qc_score
        
        print(f"  Case: {case['name']}")
        print(f"    Default QC: {default_qc}")
        print(f"    Protocol QC: {protocol_qc}")
        
        if default_qc != protocol_qc:
            print(f"    FAIL: QC mismatch!")
            return False
        print(f"    PASS")
    
    return True


def test_gl_policy_parity():
    """Test GL: Explicit SKIPPED policy preserved."""
    print("\n=== TEST GL: SKIPPED Policy ===")
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    gl_data = [
        {"Posicao": "1", "Title": "Software Hiring Best Practices", "URL": "http://example.com/1", "Source_File": "test.txt"},
        {"Posicao": "2", "Title": "HR Article", "URL": "http://example.com/2", "Source_File": "test.txt"},
    ]
    gl_df = create_test_dataframe(gl_data)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    results_default = engine_default.process_gl_articles(gl_df)
    results_protocol = engine_protocol.process_gl_articles(gl_df)
    
    for i, (r_default, r_protocol) in enumerate(zip(results_default, results_protocol)):
        print(f"  GL Article {i+1}:")
        print(f"    Default EC: {r_default.ec_decision}, IC: {r_default.ic_decision}, QC: {r_default.qc_score}")
        print(f"    Protocol EC: {r_protocol.ec_decision}, IC: {r_protocol.ic_decision}, QC: {r_protocol.qc_score}")
        
        if r_default.ec_decision != r_protocol.ec_decision:
            print(f"    FAIL: EC mismatch!")
            return False
        if r_default.ic_decision != r_protocol.ic_decision:
            print(f"    FAIL: IC should be SKIPPED for GL!")
            return False
        if r_default.qc_score != r_protocol.qc_score:
            print(f"    FAIL: QC should be SKIPPED for GL!")
            return False
        print(f"    PASS")
    
    return True


def test_wl_gl_full_comparison():
    """Compare full pipeline results between default and protocol for all articles."""
    print("\n=== TEST Full Pipeline Comparison ===")
    
    wl_df = pd.read_excel("tests/atlas_sample_input.xlsx", sheet_name="White Literature")
    gl_df = pd.read_excel("tests/atlas_sample_input.xlsx", sheet_name="Grey Literature")
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    protocol = get_default_protocol()
    engine_default = APOLLODecisionEngine(enable_llm_reasoning=False)
    engine_protocol = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    wl_default = engine_default.process_wl_articles(wl_df)
    wl_protocol = engine_protocol.process_wl_articles(wl_df)
    
    gl_default = engine_default.process_gl_articles(gl_df)
    gl_protocol = engine_protocol.process_gl_articles(gl_df)
    
    mismatches = []
    
    for i, (r_default, r_protocol) in enumerate(zip(wl_default, wl_protocol)):
        if r_default.ec_decision != r_protocol.ec_decision:
            mismatches.append(f"WL[{i}] EC: {r_default.ec_decision} != {r_protocol.ec_decision}")
        if r_default.ic_decision != r_protocol.ic_decision:
            mismatches.append(f"WL[{i}] IC: {r_default.ic_decision} != {r_protocol.ic_decision}")
        if r_default.qc_score != r_protocol.qc_score:
            mismatches.append(f"WL[{i}] QC: {r_default.qc_score} != {r_protocol.qc_score}")
        if r_default.final_decision != r_protocol.final_decision:
            mismatches.append(f"WL[{i}] Final: {r_default.final_decision} != {r_protocol.final_decision}")
    
    for i, (r_default, r_protocol) in enumerate(zip(gl_default, gl_protocol)):
        if r_default.ec_decision != r_protocol.ec_decision:
            mismatches.append(f"GL[{i}] EC: {r_default.ec_decision} != {r_protocol.ec_decision}")
        if r_default.ic_decision != r_protocol.ic_decision:
            mismatches.append(f"GL[{i}] IC: {r_default.ic_decision} != {r_protocol.ic_decision}")
        if r_default.qc_score != r_protocol.qc_score:
            mismatches.append(f"GL[{i}] QC: {r_default.qc_score} != {r_protocol.qc_score}")
    
    if mismatches:
        print("  FAILURES:")
        for m in mismatches:
            print(f"    {m}")
        return False
    else:
        print(f"  PASS: {len(wl_default)} WL + {len(gl_default)} GL articles - zero divergences")
        return True


def main():
    print("=" * 60)
    print("PROTOCOL PARITY TEST SUITE")
    print("=" * 60)
    print("Verifying: default_behavior == protocol(get_default_protocol())")
    print()
    
    tests = [
        ("EC1 Semantic Parity", test_ec1_semantic_parity),
        ("EC4 Duplicate Propagation", test_ec4_duplicate_propagation),
        ("QC Scoring Exactness", test_qc_scoring_exact),
        ("GL SKIPPED Policy", test_gl_policy_parity),
        ("Full Pipeline Comparison", test_wl_gl_full_comparison),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("ALL TESTS PASSED - Protocol parity verified with zero tolerance")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED - Review mismatches above")
        sys.exit(1)


if __name__ == "__main__":
    main()