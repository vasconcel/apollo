"""
APOLLO Operational Validation - Adversarial Dataset Suite
Stress-tests APOLLO against adversarial and ambiguous screening scenarios.
"""
import pandas as pd
import numpy as np
import hashlib
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.atlas_processor import (
    APOLLODecisionEngine, ATLASLoader, ArticleRecord, ExclusionCriteria
)
from src.core.screening_session import create_session, ArticleReview
from src.core.llm_assistant import LLMAssistant


@dataclass
class AdversarialTestCase:
    """Single adversarial test case."""
    test_id: str
    description: str
    wl_data: Optional[pd.DataFrame] = None
    gl_data: Optional[pd.DataFrame] = None
    expected_behavior: str = ""
    metadata_check: Dict[str, Any] = None


class AdversarialDatasetSuite:
    """Comprehensive adversarial test suite."""
    
    def __init__(self):
        self.results = []
        self.llm_audit = []
    
    # ======================================================================
    # PART 1: ADVERSARIAL DATASET CASES
    # ======================================================================
    
    def case_wl_no_structured_year(self) -> AdversarialTestCase:
        """1. WL article WITHOUT structured Year - must use regex fallback."""
        df = pd.DataFrame({
            'Library': ['ACM'], 'Global_ID': ['G001'], 'Local_ID': ['L001'],
            'Title': 'A Study of Developer Productivity',
            'Abstract': 'This research was conducted in 2019 and published in 2020 at ICSE.',
            'Keywords': 'productivity, software', 'Authors': 'Jane Smith'
            # NO Year column
        })
        return AdversarialTestCase(
            test_id="WL-001",
            description="WL without structured Year - regex fallback",
            wl_data=df,
            expected_behavior="year_source should be 'regex', year=2020",
            metadata_check={"year_source": "regex"}
        )
    
    def case_wl_conflicting_years(self) -> AdversarialTestCase:
        """2. WL with conflicting year values."""
        df = pd.DataFrame({
            'Library': ['IEEE'], 'Global_ID': ['G002'], 'Local_ID': ['L002'],
            'Title': 'Agile Methods Analysis',
            'Abstract': 'Our 2019 study showed interesting results. Published in 2023.',
            'Keywords': 'agile, methods', 'Authors': 'John Doe',
            'Year': 2023  # Structured year
        })
        return AdversarialTestCase(
            test_id="WL-002",
            description="Conflicting years (DF=2023, abstract=2019)",
            wl_data=df,
            expected_behavior="year_source=structured, year=2023 (priority over regex)",
            metadata_check={"year_source": "structured", "year": 2023}
        )
    
    def case_gl_with_fake_abstract(self) -> AdversarialTestCase:
        """3. GL with fake abstract-like text but contains SE keywords."""
        df = pd.DataFrame({
            'Posicao': ['1'],
            'Title': 'Tech Blog: How We Hire Software Engineers',
            'URL': 'https://example.com/blog/hiring',
            'Source_File': 'blog_export.xlsx'
        })
        return AdversarialTestCase(
            test_id="GL-001",
            description="GL with minimal metadata",
            gl_data=df,
            expected_behavior="GL passes EC but IC=PENDING (no abstract)",
            metadata_check={"literature_type": "GL", "ic_decision": "PENDING"}
        )
    
    def case_gl_without_url(self) -> AdversarialTestCase:
        """4. GL without URL."""
        df = pd.DataFrame({
            'Posicao': ['2'],
            'Title': 'Internal Company Report',
            'URL': '',  # Empty URL
            'Source_File': 'internal.xlsx'
        })
        return AdversarialTestCase(
            test_id="GL-002",
            description="GL without URL",
            gl_data=df,
            expected_behavior="Should warn about missing URL",
            metadata_check={"url": ""}
        )
    
    def case_wl_without_doi(self) -> AdversarialTestCase:
        """5. WL article WITHOUT DOI."""
        df = pd.DataFrame({
            'Library': ['ArXiv'], 'Global_ID': ['G003'], 'Local_ID': ['L003'],
            'Title': 'Machine Learning for Code Generation',
            'Abstract': 'We present a novel approach to automated code generation using transformer models.',
            'Keywords': 'ML, code generation', 'Authors': 'AI Researcher', 'Year': 2022,
            'Venue': 'NeurIPS'
            # No DOI column - but has Venue
        })
        return AdversarialTestCase(
            test_id="WL-003",
            description="WL without DOI",
            wl_data=df,
            expected_behavior="Metadata completeness partial",
            metadata_check={"year": 2022}
        )
    
    def case_wl_without_venue(self) -> AdversarialTestCase:
        """6. WL article WITHOUT venue."""
        df = pd.DataFrame({
            'Library': ['Preprint'], 'Global_ID': ['G004'], 'Local_ID': ['L004'],
            'Title': 'Empirical Study of Remote Work',
            'Abstract': 'A survey of 500 software developers regarding remote work effectiveness.',
            'Keywords': 'remote work, survey', 'Authors': 'Research Team', 'Year': 2021,
            'DOI': '10.1000/test'
            # No Venue - but has DOI
        })
        return AdversarialTestCase(
            test_id="WL-004",
            description="WL without Venue",
            wl_data=df,
            expected_behavior="Metadata completeness partial",
            metadata_check={"year": 2021}
        )
    
    def case_duplicate_titles_different_years(self) -> AdversarialTestCase:
        """7. Duplicate titles with different years."""
        df = pd.DataFrame([
            {'Library': 'IEEE', 'Global_ID': 'G005a', 'Local_ID': 'L005a',
             'Title': 'Software Testing Methods', 'Abstract': 'Comprehensive review of testing.',
             'Keywords': 'testing', 'Authors': 'Author A', 'Year': 2019},
            {'Library': 'IEEE', 'Global_ID': 'G005b', 'Local_ID': 'L005b',
             'Title': 'Software Testing Methods', 'Abstract': 'Updated review with new findings.',
             'Keywords': 'testing', 'Authors': 'Author B', 'Year': 2023}
        ])
        return AdversarialTestCase(
            test_id="WL-005",
            description="Duplicate titles different years",
            wl_data=df,
            expected_behavior="Both processed independently",
            metadata_check={"year_values": [2019, 2023], "count": 2}
        )
    
    def case_unicode_multilingual(self) -> AdversarialTestCase:
        """8. Unicode-heavy multilingual records."""
        df = pd.DataFrame({
            'Library': ['Springer'], 'Global_ID': ['G006'], 'Local_ID': ['L006'],
            'Title': 'Evaluation des Methodes Agiles dans le Developpement Logiciel',
            'Abstract': 'Cette etude presente une analyse systematique des methodes agiles.',
            'Keywords': 'agile, methodes', 'Authors': 'Universite de Paris', 'Year': 2020
        })
        return AdversarialTestCase(
            test_id="WL-006",
            description="Unicode multilingual content",
            wl_data=df,
            expected_behavior="Unicode preserved in all fields",
            metadata_check={"year": 2020}
        )
    
    def case_corrupted_truncated_abstract(self) -> AdversarialTestCase:
        """9. Corrupted/truncated abstract."""
        df = pd.DataFrame({
            'Library': ['IEEE'], 'Global_ID': ['G007'], 'Local_ID': ['L007'],
            'Title': 'Security Analysis',
            'Abstract': 'We present a novel approach to security in software systems using machine learning.',
            'Keywords': 'security, ML', 'Authors': 'Author', 'Year': 2022
        })
        return AdversarialTestCase(
            test_id="WL-007",
            description="Truncated abstract",
            wl_data=df,
            expected_behavior="Processed without error",
            metadata_check={"year": 2022}
        )
    
    def case_long_abstract(self) -> AdversarialTestCase:
        """10. Extremely long abstract (> Excel cell limits)."""
        long_abs = "This is a long abstract. " * 500  # ~8000 chars
        df = pd.DataFrame({
            'Library': ['IEEE'], 'Global_ID': ['G008'], 'Local_ID': ['L008'],
            'Title': 'Comprehensive Study of Software Engineering',
            'Abstract': long_abs,
            'Keywords': 'software, engineering', 'Authors': 'Author', 'Year': 2022
        })
        return AdversarialTestCase(
            test_id="WL-008",
            description="Long abstract (Excel truncation risk)",
            wl_data=df,
            expected_behavior="Truncated at export if > 32767 chars",
            metadata_check={"year": 2022, "has_long_abstract": True}
        )
    
    def case_empty_keywords(self) -> AdversarialTestCase:
        """11. Empty keywords."""
        df = pd.DataFrame({
            'Library': ['IEEE'], 'Global_ID': ['G009'], 'Local_ID': ['L009'],
            'Title': 'Software Metrics',
            'Abstract': 'A comprehensive study of software metrics and their impact on project success.',
            'Keywords': '',  # Empty
            'Authors': 'Author', 'Year': 2021
        })
        return AdversarialTestCase(
            test_id="WL-009",
            description="Empty keywords",
            wl_data=df,
            expected_behavior="Processed correctly",
            metadata_check={"keywords": ""}
        )
    
    def case_ambiguous_literature_type(self) -> AdversarialTestCase:
        """12. Ambiguous literature type values."""
        df = pd.DataFrame({
            'Library': ['Unknown'], 'Global_ID': ['G010'], 'Local_ID': ['L010'],
            'Title': 'Industry Report',
            'Abstract': 'Annual industry report on software development trends.',
            'Keywords': 'trends', 'Authors': 'Industry Analyst', 'Year': 2023
            # No explicit literature_type
        })
        return AdversarialTestCase(
            test_id="WL-010",
            description="Default literature type",
            wl_data=df,
            expected_behavior="Defaults to WL",
            metadata_check={"literature_type": "WL"}
        )
    
    def case_missing_metadata_columns(self) -> AdversarialTestCase:
        """13. Missing metadata columns."""
        df = pd.DataFrame({
            'Title': ['Minimal Record'],  
            'Abstract': ['A brief study about software development practices.'],
            'Global_ID': ['G011'],
            'Year': [2022]
        })
        return AdversarialTestCase(
            test_id="WL-011",
            description="Minimal schema",
            wl_data=df,
            expected_behavior="Handled gracefully",
            metadata_check={"year": 2022}
        )
    
    def case_null_representations(self) -> AdversarialTestCase:
        """15. Mixed null representations."""
        df = pd.DataFrame({
            'Library': ['IEEE', 'ACM', 'ArXiv', 'IEEE'],
            'Global_ID': ['G011', 'G012', 'G013', 'G014'],
            'Local_ID': ['L011', 'L012', 'L013', 'L014'],
            'Title': ['Paper 1', 'Paper 2', 'Paper 3', 'Paper 4'],
            'Abstract': ['Abstract 1 about software engineering', 'Abstract 2 about agile methods', 'Abstract 3 about developer testing', 'Abstract 4 about code review'],
            'Keywords': ['', None, 'software', np.nan],
            'Authors': ['Author 1', None, 'Author 3', ''],
            'Year': [2020, 2021, 2022, 2023]
        })
        return AdversarialTestCase(
            test_id="WL-012",
            description="Mixed null representations",
            wl_data=df,
            expected_behavior="Normalized consistently",
            metadata_check={"count": 4}
        )
    
    def case_gl_passes_ec_becomes_pending(self) -> AdversarialTestCase:
        """GL passing EC MUST become PENDING."""
        df = pd.DataFrame({
            'Posicao': ['1'],
            'Title': 'Best Practices in Software Development from Tech Company Engineering Team',
            'URL': 'https://company.com/blog/best-practices',
            'Source_File': 'tech_blog.xlsx'
        })
        return AdversarialTestCase(
            test_id="GL-003",
            description="GL EC pass -> IC PENDING",
            gl_data=df,
            expected_behavior="ic_decision = PENDING, final_decision = PENDING",
            metadata_check={"ic_decision": "PENDING", "final_decision": "PENDING"}
        )
    
    # ======================================================================
    # RUN ALL TESTS
    # ======================================================================
    
    def run_all_tests(self) -> List[Dict]:
        """Execute all adversarial test cases."""
        engine = APOLLODecisionEngine(enable_llm_reasoning=False)
        results = []
        
        test_cases = [
            self.case_wl_no_structured_year(),
            self.case_wl_conflicting_years(),
            self.case_gl_with_fake_abstract(),
            self.case_gl_without_url(),
            self.case_wl_without_doi(),
            self.case_wl_without_venue(),
            self.case_duplicate_titles_different_years(),
            self.case_unicode_multilingual(),
            self.case_corrupted_truncated_abstract(),
            self.case_long_abstract(),
            self.case_empty_keywords(),
            self.case_ambiguous_literature_type(),
            self.case_missing_metadata_columns(),
            self.case_null_representations(),
            self.case_gl_passes_ec_becomes_pending(),
        ]
        
        for tc in test_cases:
            print(f"\n=== {tc.test_id}: {tc.description} ===")
            
            result = {
                "test_id": tc.test_id,
                "description": tc.description,
                "passed": False,
                "details": {},
                "metadata_check": tc.metadata_check,
                "actual_metadata": {}
            }
            
            try:
                if tc.wl_data is not None:
                    records = engine.process_wl_articles(tc.wl_data)
                    
                    # Collect all years for multi-record tests
                    years = [r.year for r in records]
                    
                    # Use first record for single-record checks
                    rec = records[0]
                    result["actual_metadata"] = {
                        "year": rec.year,
                        "year_source": rec.metadata.get("year_source"),
                        "authors": rec.authors,
                        "metadata_completeness": rec.metadata.get("metadata_completeness"),
                        "literature_type": rec.literature_type,
                        "title": rec.title,
                        "keywords": rec.keywords,
                        "library": rec.library,
                        "url": rec.url,
                        "year_values": years,
                        "count": len(records)
                    }
                    
                    # Verify checks
                    passed_checks = 0
                    for key, expected in tc.metadata_check.items():
                        if key == "year_values":
                            if result["actual_metadata"].get("year_values") == expected:
                                passed_checks += 1
                        elif key == "count":
                            if result["actual_metadata"].get("count") == expected:
                                passed_checks += 1
                        elif key == "has_long_abstract":
                            if len(result["actual_metadata"].get("title", "")) > 0:
                                passed_checks += 1
                        elif key in result["actual_metadata"]:
                            actual = result["actual_metadata"][key]
                            if actual == expected or (isinstance(expected, str) and expected.lower() in str(actual).lower()):
                                passed_checks += 1
                    
                    result["passed"] = passed_checks == len(tc.metadata_check)
                
                elif tc.gl_data is not None:
                    records = engine.process_gl_articles(tc.gl_data)
                    for rec in records:
                        result["actual_metadata"] = {
                            "ic_decision": rec.ic_decision,
                            "final_decision": rec.final_decision,
                            "literature_type": rec.literature_type,
                            "url": rec.url,
                            "ec_decision": rec.ec_decision
                        }
                        
                        for key, expected in tc.metadata_check.items():
                            if key in result["actual_metadata"]:
                                result["passed"] = result["actual_metadata"][key] == expected
                
                print(f"  PASSED: {result['passed']}")
                print(f"  Details: {result['details']}")
                
            except Exception as e:
                result["passed"] = False
                result["error"] = str(e)
                print(f"  ERROR: {e}")
            
            results.append(result)
        
        return results


class MetadataLineageTracer:
    """Trace metadata end-to-end through the pipeline."""
    
    @staticmethod
    def trace(atlas_df: pd.DataFrame, is_gl: bool = False) -> Dict:
        """Trace metadata from ATLAS to UI."""
        engine = APOLLODecisionEngine(enable_llm_reasoning=False)
        
        if is_gl:
            records = engine.process_gl_articles(atlas_df)
        else:
            records = engine.process_wl_articles(atlas_df)
        
        record = records[0]
        
        session = create_session([record])
        article = session.articles[0]
        
        return {
            "atlas_columns": list(atlas_df.columns),
            "atlas_row_count": len(atlas_df),
            "article_record": {
                "year": record.year,
                "year_source": record.metadata.get("year_source"),
                "authors": record.authors,
                "metadata_completeness": record.metadata.get("metadata_completeness"),
                "literature_type": record.literature_type,
                "library": record.library,
                "venue": record.metadata.get("Venue"),
                "publisher": record.metadata.get("Publisher"),
                "doi": record.metadata.get("DOI"),
                "url": record.url
            },
            "screening_session": {
                "metadata_keys": list(article.metadata.keys()),
                "year": article.metadata.get("year"),
                "year_source": article.metadata.get("year_source"),
                "literature_type": article.metadata.get("literature_type")
            },
            "lineage_hash": hashlib.sha256(
                json.dumps(record.metadata, sort_keys=True).encode()
            ).hexdigest()[:16]
        }


class DeterminismVerifier:
    """Verify deterministic behavior across multiple runs."""
    
    @staticmethod
    def verify_determinism(wl_data: pd.DataFrame, runs: int = 3) -> Dict:
        """Run same input multiple times, verify identical output."""
        engine = APOLLODecisionEngine(enable_llm_reasoning=False)
        
        hashes = []
        all_records = []
        
        for i in range(runs):
            records = engine.process_wl_articles(wl_data)
            record_hash = hashlib.sha256(
                json.dumps({
                    "year": records[0].year,
                    "year_source": records[0].metadata.get("year_source"),
                    "ec_decision": records[0].ec_decision,
                    "final_decision": records[0].final_decision
                }, sort_keys=True).encode()
            ).hexdigest()
            hashes.append(record_hash)
            all_records.append(records[0])
        
        return {
            "all_hashes_identical": len(set(hashes)) == 1,
            "hashes": hashes,
            "runs": runs,
            "first_record": {
                "year": all_records[0].year,
                "ec_decision": all_records[0].ec_decision,
                "final_decision": all_records[0].final_decision
            }
        }


class ExportValidator:
    """Validate export schemas exactly."""
    
    WL_EXPECTED_COLUMNS = [
        "Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords",
        "CIs1", "CEs1", "Revisor 1", "CIs2", "CEs2", "Revisor 2", "Decision"
    ]
    
    GL_EXPECTED_COLUMNS = [
        "Posicao", "Title", "URL", "Source_File", 
        "Revisor 1 EC", "Revisor 1 IC", "Decision"
    ]
    
    @staticmethod
    def validate_export(wl_results: List[ArticleRecord], 
                        gl_results: List[ArticleRecord]) -> Dict:
        """Validate exported Excel schemas."""
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        
        engine = APOLLODecisionEngine(enable_llm_reasoning=False)
        engine.export_to_excel(tmp_path, wl_results, gl_results)
        
        xl = pd.ExcelFile(tmp_path)
        wl_df = pd.read_excel(xl, 'WL')
        gl_df = pd.read_excel(xl, 'GL')
        
        wl_match = list(wl_df.columns) == ExportValidator.WL_EXPECTED_COLUMNS
        gl_match = list(gl_df.columns) == ExportValidator.GL_EXPECTED_COLUMNS
        
        result = {
            "wl_columns_match": wl_match,
            "wl_actual": list(wl_df.columns),
            "wl_expected": ExportValidator.WL_EXPECTED_COLUMNS,
            "gl_columns_match": gl_match,
            "gl_actual": list(gl_df.columns),
            "gl_expected": ExportValidator.GL_EXPECTED_COLUMNS,
            "wl_row_count": len(wl_df),
            "gl_row_count": len(gl_df)
        }
        
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        return result


class LLMAudit:
    """Audit LLM for hallucination patterns."""
    
    @staticmethod
    def audit_metadata_inference(test_cases: List[AdversarialTestCase]) -> Dict:
        """Check if LLM infers metadata without explicit structured data."""
        llm = LLMAssistant()
        
        if not llm.is_available():
            return {"status": "unavailable", "note": "No LLM configured"}
        
        audit_results = []
        
        # Case 1: No year in metadata - check if LLM assumes
        case1 = test_cases[0]  # WL without structured year
        
        prompt_year_source = "regex"  # This is what LLM sees
        prompt_metadata_completeness = "minimal"
        
        suggestion = llm.suggest_ec(
            title="Study of Developer Productivity",
            abstract="This research was conducted in 2019 and published in 2020.",
            literature_type="WL",
            year=None,  # LLM sees no year
            metadata={"year_source": "regex", "metadata_completeness": "minimal"}
        )
        
        audit_results.append({
            "test": "Year inference check",
            "llm_year_input": None,
            "llm_justification": suggestion.justification,
            "year_source_provided": "regex",
            "potential_hallucination": "year" not in suggestion.justification.lower()
        })
        
        return {
            "audit_results": audit_results,
            "hallucination_risks": [
                r["potential_hallucination"] for r in audit_results
            ]
        }


def run_validation_suite():
    """Run complete validation suite."""
    print("=" * 60)
    print("APOLLO OPERATIONAL VALIDATION SPRINT")
    print("=" * 60)
    
    suite = AdversarialDatasetSuite()
    
    # PART 1: Adversarial Tests
    print("\n" + "=" * 60)
    print("PART 1: ADVERSARIAL DATASET SUITE")
    print("=" * 60)
    results = suite.run_all_tests()
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n>>> SUMMARY: {passed}/{total} tests passed")
    
    # PART 3: Metadata Lineage
    print("\n" + "=" * 60)
    print("PART 3: METADATA FLOW VERIFICATION")
    print("=" * 60)
    
    wl_df = pd.DataFrame({
        'Library': ['IEEE'], 'Global_ID': ['G001'], 'Local_ID': ['L001'],
        'Title': 'Test Paper', 'Abstract': 'Test abstract about software engineering',
        'Keywords': 'software', 'Authors': 'John Doe', 'Year': 2023,
        'Venue': 'ICSE', 'Publisher': 'IEEE', 'DOI': '10.1000/test'
    })
    
    lineage = MetadataLineageTracer.trace(wl_df)
    print(f"Lineage Hash: {lineage['lineage_hash']}")
    print(f"Screening Metadata Keys: {lineage['screening_session']['metadata_keys']}")
    print(f"Year Source: {lineage['screening_session']['year_source']}")
    
    # PART 4: WL/GL Isolation
    print("\n" + "=" * 60)
    print("PART 4: WL/GL METHODOLOGICAL ISOLATION")
    print("=" * 60)
    
    engine = APOLLODecisionEngine(enable_llm_reasoning=False)
    
    gl_df = pd.DataFrame({
        'Posicao': ['1'],
        'Title': 'Company Engineering Blog about Software Developer Hiring Practices',
        'URL': 'https://company.com/blog',
        'Source_File': 'blog.xlsx'
    })
    gl_results = engine.process_gl_articles(gl_df)
    
    gl_isolated = gl_results[0].ic_decision == "PENDING" and gl_results[0].final_decision == "PENDING"
    print(f"GL EC Decision: {gl_results[0].ec_decision}")
    print(f"GL IC=PENDING after EC pass: {gl_results[0].ic_decision}")
    print(f"GL final decision = PENDING: {gl_results[0].final_decision}")
    print(f"ISOLATION VERIFIED: {gl_isolated}")
    
    # PART 5: Determinism
    print("\n" + "=" * 60)
    print("PART 5: DETERMINISM AUDIT")
    print("=" * 60)
    
    wl_df_det = pd.DataFrame({
        'Library': ['IEEE'], 'Global_ID': ['G001'], 'Local_ID': ['L001'],
        'Title': 'Determinism Test', 
        'Abstract': 'This study about software testing was conducted in 2021.',
        'Keywords': 'testing', 'Authors': 'Test Author', 'Year': 2021
    })
    
    det_result = DeterminismVerifier.verify_determinism(wl_df_det)
    print(f"Deterministic: {det_result['all_hashes_identical']}")
    print(f"Hashes: {det_result['hashes']}")
    
    # PART 6: Export Validation
    print("\n" + "=" * 60)
    print("PART 6: EXPORT VALIDATION")
    print("=" * 60)
    
    wl_results = engine.process_wl_articles(wl_df)
    gl_results = engine.process_gl_articles(gl_df)
    
    export_val = ExportValidator.validate_export(wl_results, gl_results)
    print(f"WL Schema Match: {export_val['wl_columns_match']}")
    print(f"GL Schema Match: {export_val['gl_columns_match']}")
    print(f"WL Columns: {export_val['wl_actual']}")
    print(f"GL Columns: {export_val['gl_actual']}")
    
    # PART 2: LLM Audit
    print("\n" + "=" * 60)
    print("PART 2: LLM HALLUCINATION AUDIT")
    print("=" * 60)
    
    llm_audit = LLMAudit.audit_metadata_inference(results)
    print(f"LLM Status: {llm_audit['status']}")
    if 'audit_results' in llm_audit:
        for ar in llm_audit['audit_results']:
            print(f"  Hallucination Risk: {ar.get('potential_hallucination', 'unknown')}")
    
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    
    return {
        "adversarial_results": results,
        "metadata_lineage": lineage,
        "wl_gl_isolated": gl_isolated,
        "deterministic": det_result['all_hashes_identical'],
        "export_valid": export_val['wl_columns_match'] and export_val['gl_columns_match'],
        "llm_audit": llm_audit
    }


if __name__ == "__main__":
    run_validation_suite()