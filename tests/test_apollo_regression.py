"""
APOLLO Regression Test Suite - v1.0.0
Validates deterministic behavior and prevents regressions.

UPDATED FOR HITL POLICY:
- Validates that GL articles now go to PENDING instead of SKIPPED.
- Ensures Global_ID based deduplication remains consistent.
"""
import os
import sys
import pandas as pd
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.atlas_processor import export_apollo_selection_criteria


class APOLLORegressionTester:
    """Regression testing for APOLLO decision engine (HITL-compliant)."""
    
    def __init__(self):
        # Use absolute paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_path = os.path.join(self.base_dir, 'atlas_sample_input.xlsx')
        self.expected_path = os.path.join(self.base_dir, 'apollo_expected_output.xlsx')
        self.actual_path = os.path.join(self.base_dir, 'apollo_actual_output.xlsx')
        self.run1_path = os.path.join(self.base_dir, 'apollo_run1_output.xlsx')
        self.run2_path = os.path.join(self.base_dir, 'apollo_run2_output.xlsx')
        
    def run_pipeline(self, output_path):
        """Run APOLLO pipeline and save output."""
        temp_input = 'temp_atlas_input.xlsx'
        shutil.copy(self.input_path, temp_input)
        
        try:
            # Note: enable_llm=False for deterministic regression testing
            export_apollo_selection_criteria(
                input_path=temp_input,
                output_filename=output_path,
                enable_llm=False
            )
        finally:
            if os.path.exists(temp_input):
                os.remove(temp_input)
    
    def load_sheets(self, filepath):
        """Load all sheets from Excel file."""
        xlsx = pd.ExcelFile(filepath)
        return {
            'WL': pd.read_excel(xlsx, sheet_name='WL'),
            'GL': pd.read_excel(xlsx, sheet_name='GL'),
            'WL_Seeds_HERMES': pd.read_excel(xlsx, sheet_name='WL Seeds for HERMES')
        }
    
    def compare_schemas(self, expected, actual):
        """Compare schemas between expected and actual outputs."""
        issues = []
        for sheet_name in ['WL', 'GL', 'WL_Seeds_HERMES']:
            exp_cols = set(expected[sheet_name].columns)
            act_cols = set(actual[sheet_name].columns)
            
            missing = exp_cols - act_cols
            extra = act_cols - exp_cols
            
            if missing: issues.append(f"{sheet_name}: Missing columns: {missing}")
            if extra: issues.append(f"{sheet_name}: Extra columns: {extra}")
        return issues
    
    def compare_row_counts(self, expected, actual):
        """Compare row counts."""
        issues = []
        for sheet_name in ['WL', 'GL', 'WL_Seeds_HERMES']:
            exp_count = len(expected[sheet_name])
            act_count = len(actual[sheet_name])
            if exp_count != act_count:
                issues.append(f"{sheet_name}: Row count mismatch - Expected {exp_count}, Got {act_count}")
        return issues
    
    def compare_cells(self, expected, actual):
        """Compare cell values (excluding specific reviewer fields)."""
        issues = []
        allowed_empty = {'Revisor 1', 'CIs2', 'CEs2', 'Revisor 2'}
        
        for sheet_name in ['WL', 'GL']:
            exp_df = expected[sheet_name]
            act_df = actual[sheet_name]
            
            for col in exp_df.columns:
                if col in allowed_empty: continue
                    
                for idx in exp_df.index:
                    if idx >= len(act_df):
                        issues.append(f"{sheet_name}[{idx}]: Row missing in actual")
                        continue
                    
                    exp_val = str(exp_df.loc[idx, col])
                    act_val = str(act_df.loc[idx, col])
                    
                    # Special Case: If golden file still has 'SKIPPED', we allow 'PENDING'
                    if sheet_name == 'GL' and col == 'Revisor 1 IC' and exp_val == 'SKIPPED' and act_val == 'PENDING':
                        continue

                    if exp_val != act_val:
                        issues.append(f"{sheet_name}[{idx}] '{col}': Expected '{exp_val}', Got '{act_val}'")
        return issues
    
    def check_ec4_consistency(self, actual):
        """Verify EC4 uses Global_ID based deduplication."""
        wl = actual['WL']
        ec4_rows = wl[wl['CEs1'] == 'EC4']
        
        if len(ec4_rows) > 0:
            global_ids = wl['Global_ID'].value_counts()
            duplicates = set(global_ids[global_ids > 1].index)
            ec4_ids = set(ec4_rows['Global_ID'].values)
            if not ec4_ids.issubset(duplicates):
                return [f"EC4 Error: Non-duplicate Global_IDs flagged as EC4: {ec4_ids - duplicates}"]
        return []
    
    def check_gl_hitl_policy(self, actual):
        """
        Verify GL HITL Policy: 
        Articles passing EC must NOT be skipped. They must be PENDING for human review.
        """
        gl = actual['GL']
        issues = []
        ec_passed = gl[gl['Revisor 1 EC'] == 'NO']
        ic_pending = ec_passed[ec_passed['Revisor 1 IC'] == 'PENDING']
        
        if len(ec_passed) != len(ic_pending):
            issues.append(f"GL Policy Failure: Expected IC='PENDING' for HITL funnel, but found {len(ec_passed)-len(ic_pending)} records with different status.")
        
        return issues
    
    def run_regression_test(self):
        """Run full regression test suite."""
        print("\n" + "="*60)
        print("APOLLO REGRESSION TEST - V1.0.0 (HITL COMPLIANT)")
        print("="*60)
        
        results = {'schema': 'PASS', 'ec4': 'PASS', 'gl_policy': 'PASS', 'determinism': 'PASS'}
        
        print(f"\n[1] Running APOLLO pipeline...")
        self.run_pipeline(self.actual_path)
        
        print("\n[2] Comparing against golden output...")
        expected = self.load_sheets(self.expected_path)
        actual = self.load_sheets(self.actual_path)
        
        schema_issues = self.compare_schemas(expected, actual)
        cell_issues = self.compare_cells(expected, actual)
        
        if schema_issues or cell_issues:
            results['schema'] = 'FAIL'
            print(f"    Validation: FAIL ({len(schema_issues) + len(cell_issues)} issues found)")
        else:
            print("    Validation: PASS")
        
        print("\n[3] Checking EC4 duplicate detection...")
        ec4_issues = self.check_ec4_consistency(actual)
        if ec4_issues:
            results['ec4'] = 'FAIL'
            for issue in ec4_issues: print(f"      - {issue}")
        else:
            print("    EC4: PASS (Global_ID based)")
        
        print("\n[4] Checking GL HITL policy handling...")
        gl_issues = self.check_gl_hitl_policy(actual)
        if gl_issues:
            results['gl_policy'] = 'FAIL'
            print("    GL Policy: FAIL (Old 'SKIPPED' policy detected or corrupted funnel)")
        else:
            print("    GL Policy: PASS (PENDING for manual review)")
        
        print("\n[5] Checking reproducibility (determinism)...")
        self.run_pipeline(self.run1_path)
        self.run_pipeline(self.run2_path)
        
        run1 = self.load_sheets(self.run1_path)
        run2 = self.load_sheets(self.run2_path)
        
        if run1['WL'].equals(run2['WL']) and run1['GL'].equals(run2['GL']):
            print("    Determinism: PASS")
        else:
            results['determinism'] = 'FAIL'
            print("    Determinism: FAIL (Outputs differ between identical runs)")
        
        # Cleanup
        for f in [self.run1_path, self.run2_path, self.actual_path]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass
        
        print("\n" + "="*60)
        print("APOLLO REGRESSION REPORT")
        print("="*60)
        for k, v in results.items():
            print(f"- {k.upper()}: {v}")
        
        overall = 'PASS' if all(v == 'PASS' for v in results.values()) else 'FAIL'
        print(f"\nOVERALL RESULT: {overall}")
        print("="*60)
        
        return results


if __name__ == '__main__':
    tester = APOLLORegressionTester()
    tester.run_regression_test()