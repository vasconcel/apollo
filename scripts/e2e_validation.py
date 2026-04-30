#!/usr/bin/env python3
"""
E2E Validation Script for AIMS MLR Pipeline

This script validates the complete workflow:
Ingestion -> Screening -> Consensus -> Quality -> Extraction -> Synthesis

Usage:
    python scripts/e2e_validation.py
"""

import sys
import os

# Add src/core to path directly to avoid __init__.py import chain
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))

from database import Database, DatabaseError
from consensus import ConsensusEngine
from quality import QualityEngine


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_step(step_num, description):
    """Print a step indicator."""
    print(f"\n[STEP {step_num}] {description}")


# Use ASCII symbols for Windows compatibility
CHECK = "[OK]"
CROSS = "[FAIL]"
CHECKMARK = "OK"
CROSSMARK = "FAIL"


def step_1_ingestion(db: Database) -> bool:
    """Step 1: Insert sample articles (WL and GL)."""
    print_step(1, "Ingestion - Inserting sample articles")
    
    try:
        with db.connect() as conn:
            # Article 1: White Literature (WL)
            conn.execute("""
                INSERT INTO articles (title, abstract, source_id, literature_type, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "A Systematic Review of Software Engineering Recruitment Practices",
                "This paper presents a systematic review of recruitment and selection practices in software engineering companies. We analyze 45 primary studies conducted between 2015-2023.",
                "scopus",
                "WL",
                "imported"
            ))
            
            # Article 2: Grey Literature (GL)
            conn.execute("""
                INSERT INTO articles (title, abstract, source_id, literature_type, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "Hiring Trends in Tech: 2024 Industry Report",
                "Industry report on current hiring trends in technology companies. Based on survey data from 200+ companies, we present findings on remote hiring, skill assessments, and candidate experience.",
                "google_scholar",
                "GL",
                "imported"
            ))
            
            # Article 3: White Literature (WL)
            conn.execute("""
                INSERT INTO articles (title, abstract, source_id, literature_type, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "Interview Process Effectiveness: A Multi-Case Study",
                "We investigate the effectiveness of technical interviews across three major tech companies. Our findings suggest structured interviews correlate with higher retention rates.",
                "ieee",
                "WL",
                "imported"
            ))
        
        # Verify insertion
        article_count = db.count_articles()
        assert article_count == 3, f"Expected 3 articles, got {article_count}"
        
        print(f"  [OK] Inserted 3 articles (WL: 2, GL: 1)")
        return True
        
    except Exception as e:
        print(f"  [FAIL] FAILED: {e}")
        return False


def step_2_screening(db: Database) -> bool:
    """Step 2: Add screening decisions from 2 reviewers."""
    print_step(2, "Screening - Adding decisions from 2 reviewers")
    
    try:
        # Reviewer 1 decisions
        db.save_decision(article_id=1, reviewer_id="reviewer_1", decision="include")
        db.save_decision(article_id=2, reviewer_id="reviewer_1", decision="include")
        db.save_decision(article_id=3, reviewer_id="reviewer_1", decision="include")
        
        # Reviewer 2 decisions (with CONFLICT on article 2)
        db.save_decision(article_id=1, reviewer_id="reviewer_2", decision="include")
        db.save_decision(article_id=2, reviewer_id="reviewer_2", decision="exclude")  # CONFLICT
        db.save_decision(article_id=3, reviewer_id="reviewer_2", decision="include")
        
        print(f"  [OK] Added decisions from 2 reviewers")
        print(f"  [OK] Conflict created: Article 2 (reviewer_1=include, reviewer_2=exclude)")
        return True
        
    except Exception as e:
        print(f"  [FAIL] FAILED: {e}")
        return False


def step_3_consensus(db: Database) -> bool:
    """Step 3: Resolve conflict using consensus engine."""
    print_step(3, "Consensus - Resolving conflict")
    
    try:
        consensus = ConsensusEngine(db.db_path)
        
        # Detect conflicts
        conflicts = consensus.detect_conflicts()
        print(f"  [OK] Detected {len(conflicts)} conflict(s)")
        
        # Check for conflict on article 2
        assert not conflicts.empty, "Expected conflicts to be detected"
        
        conflict_article = conflicts[conflicts['article_id'] == 2]
        assert not conflict_article.empty, "Expected conflict on article 2"
        
        # Resolve conflict (include)
        db.save_final_decision(
            article_id=2,
            decision="include",
            reviewer_id="reviewer_1",
            notes="Resolved: More comprehensive methodology"
        )
        
        print(f"  [OK] Conflict resolved: Article 2 -> include")
        
        # Verify final decision exists
        final_decisions = db.get_final_decisions()
        assert len(final_decisions) >= 1, "Expected at least 1 final decision"
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] FAILED: {e}")
        return False


def step_4_quality(db: Database) -> bool:
    """Step 4: Add quality assessment scores."""
    print_step(4, "Quality Assessment - Adding scores")
    
    try:
        quality_engine = QualityEngine()
        
        # Scores for article 2 (WL type)
        scores_wl = {
            "WL-Q1: Are the research aims and the SE R&S context clearly stated?": 1.0,
            "WL-Q2: Is the research methodology adequately described and appropriate?": 1.0,
            "WL-Q3: Are the findings clearly supported by the collected data?": 0.5,
            "WL-Q4: Does the study adequately discuss its limitations or threats to validity?": 1.0
        }
        
        result = quality_engine.evaluate(scores_wl)
        
        assert result['decision'] == "include", f"Expected include, got {result['decision']}"
        assert result['total_score'] == 3.5, f"Expected 3.5, got {result['total_score']}"
        
        # Save assessment
        db.save_quality_assessment(
            article_id=2,
            reviewer_id="reviewer_1",
            scores_dict=scores_wl,
            total_score=result['total_score'],
            decision=result['decision']
        )
        
        print(f"  [OK] QC scores: {result['total_score']} -> {result['decision']}")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] FAILED: {e}")
        return False


def step_5_extraction(db: Database) -> bool:
    """Step 5: Extract fragments, create codes, link to themes."""
    print_step(5, "Extraction - Creating fragments, codes, themes")
    
    try:
        # 5.1: Insert fragments
        frag1_id = db.insert_fragment(
            article_id=2,
            rq_code="RQ3",
            fragment_text="Remote hiring increased by 40% post-pandemic, with 60% of companies reporting coordination challenges in virtual interviews",
            reviewer_id="reviewer_1",
            theme_category="challenge",
            page_or_section="4.2"
        )
        
        frag2_id = db.insert_fragment(
            article_id=2,
            rq_code="RQ4",
            fragment_text="Structured interviews with technical assessments show 25% higher retention rates compared to unstructured HR interviews",
            reviewer_id="reviewer_1",
            theme_category="practice",
            page_or_section="5.1"
        )
        
        frag3_id = db.insert_fragment(
            article_id=1,
            rq_code="RQ3",
            fragment_text="Candidate experience during interview process significantly impacts acceptance rates and employer brand perception",
            reviewer_id="reviewer_1",
            theme_category="challenge",
            page_or_section="3.4"
        )
        
        print(f"  [OK] Inserted {3} fragments")
        
        # 5.2: Create codes
        code1_id = db.create_code(
            code_label="Challenge-Remote",
            rq_code="RQ3",
            reviewer_id="reviewer_1",
            code_description="Challenges related to remote/virtual hiring"
        )
        
        code2_id = db.create_code(
            code_label="Practice-Structured-Interview",
            rq_code="RQ4",
            reviewer_id="reviewer_1",
            code_description="Best practices for structured interview processes"
        )
        
        print(f"  [OK] Created {2} codes")
        
        # 5.3: Link fragments to codes
        db.link_fragment_code(frag1_id, code1_id)
        db.link_fragment_code(frag3_id, code1_id)
        db.link_fragment_code(frag2_id, code2_id)
        
        print(f"  [OK] Linked fragments to codes")
        
        # 5.4: Create themes
        theme1_id = db.create_theme(
            theme_code="TH-CH-01",
            theme_label="Hiring Challenges",
            rq_code="RQ3",
            theme_description="Theme capturing various hiring challenges in SE"
        )
        
        theme2_id = db.create_theme(
            theme_code="TH-PR-01",
            theme_label="Effective Practices",
            rq_code="RQ4",
            theme_description="Theme capturing effective hiring practices"
        )
        
        print(f"  [OK] Created {2} themes")
        
        # 5.5: Link codes to themes
        db.link_code_theme(code1_id, theme1_id)
        db.link_code_theme(code2_id, theme2_id)
        
        print(f"  [OK] Linked codes to themes")
        
        return True
        
    except DatabaseError as e:
        print(f"  [FAIL] FAILED (DatabaseError): {e}")
        return False
    except Exception as e:
        print(f"  [FAIL] FAILED: {e}")
        return False


def step_6_traceability(db: Database) -> bool:
    """Step 6: Validate traceability queries."""
    print_step(6, "Traceability - Validating queries")
    
    try:
        # 6.1: Query all fragments for RQ3
        rq3_fragments = db.get_fragments_by_rq("RQ3")
        
        assert len(rq3_fragments) >= 2, f"Expected at least 2 fragments for RQ3, got {len(rq3_fragments)}"
        
        # Verify fragments are from correct article
        rq3_article_ids = [f[1] for f in rq3_fragments]
        assert 2 in rq3_article_ids, "Expected article 2 in RQ3 fragments"
        
        print(f"  [OK] RQ3 fragments: {len(rq3_fragments)} found")
        
        # 6.2: Query fragments for theme (Hiring Challenges)
        theme_fragments = db.get_theme_fragments_with_sources(theme_id=1)
        
        assert len(theme_fragments) >= 1, f"Expected at least 1 fragment for theme, got {len(theme_fragments)}"
        
        # Verify traceability: fragment -> source
        sample = theme_fragments[0]
        fragment_text, rq_code, source_id, source_title, lit_type, theme_code, theme_label = sample
        
        assert source_id is not None, "Source ID should not be None"
        assert source_title is not None, "Source title should not be None"
        
        print(f"  [OK] Theme fragments: {len(theme_fragments)} found")
        print(f"    Sample: Source={source_title[:30]}..., Type={lit_type}")
        
        # 6.3: WL vs GL comparison
        comparison = db.compare_theme_by_literature_type(theme_id=1)
        
        assert len(comparison) >= 1, "Expected at least 1 literature type in comparison"
        
        # Verify we have WL data
        lit_types = [c[0] for c in comparison]
        assert "WL" in lit_types, "Expected WL in comparison"
        
        print(f"  [OK] WL vs GL comparison: {len(comparison)} types")
        
        # 6.4: Verify get_included_articles_for_extraction hook
        ready_articles = db.get_included_articles_for_extraction()
        
        assert len(ready_articles) >= 1, "Expected at least 1 article ready for extraction"
        
        # Verify article 2 is in the list (passed screening + QC)
        ready_ids = [a[0] for a in ready_articles]
        assert 2 in ready_ids, "Expected article 2 to be ready for extraction"
        
        print(f"  [OK] Articles ready for extraction: {len(ready_articles)}")
        
        return True
        
    except AssertionError as e:
        print(f"  [FAIL] ASSERTION FAILED: {e}")
        return False
    except Exception as e:
        print(f"  [FAIL] FAILED: {e}")
        return False


def run_e2e_validation():
    """Run the complete E2E validation."""
    print("\n" + "="*60)
    print("  AIMS MLR PIPELINE - E2E VALIDATION")
    print("="*60)
    
    # Create a fresh test database
    test_db_path = "test_e2e_validation.db"
    
    # Remove if exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    # Initialize database (creates schema)
    db = Database(db_path=test_db_path)
    print(f"\n[OK] Database initialized: {test_db_path}")
    
    # Track results
    results = {
        "Ingestion": False,
        "Screening": False,
        "Consensus": False,
        "Quality": False,
        "Extraction": False,
        "Traceability": False
    }
    
    # Run all steps
    results["Ingestion"] = step_1_ingestion(db)
    results["Screening"] = step_2_screening(db)
    results["Consensus"] = step_3_consensus(db)
    results["Quality"] = step_4_quality(db)
    results["Extraction"] = step_5_extraction(db)
    results["Traceability"] = step_6_traceability(db)
    
    # Print final report
    print_section("E2E VALIDATION REPORT")
    
    print("\nSteps:")
    for step, status in results.items():
        status_str = "OK" if status else "FAIL"
        symbol = "[OK]" if status else "[FAIL]"
        print(f"  - {step}: {symbol} {status_str}")
    
    print("\nFinal Status:")
    all_passed = all(results.values())
    final_status = "PASS" if all_passed else "FAIL"
    final_symbol = "[OK]" if all_passed else "[FAIL]"
    print(f"  {final_symbol} {final_status}")
    
    # Cleanup
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f"\n[OK] Test database cleaned up: {test_db_path}")
    
    # Return exit code
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = run_e2e_validation()
    sys.exit(exit_code)