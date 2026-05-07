"""
APOLLO Decision Engine - ATLAS Excel Processor
Processes WL and GL data from ATLAS, applies EC/IC/QC decisions, exports to Excel
"""
import pandas as pd
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class EligibilityDecision:
    """EC/IC decision result."""
    decision: str  # "include" or "exclude"
    criterion: str  # e.g., "EC1", "EC2", "IC1", etc. or "NO"
    reason: str
    
    def to_display(self) -> str:
        return self.criterion if self.decision == "exclude" else "NO"


@dataclass
class QualityDecision:
    """QC scoring result."""
    scores: Dict[str, float]  # e.g., {"WL-Q1": 1.0, "WL-Q2": 0.5, ...}
    total_score: float
    decision: str  # "include" or "exclude"
    literature_type: str  # "WL" or "GL"
    
    def to_display(self) -> str:
        if not self.scores:
            return "NO"
        return f"{self.total_score}/4"
    
    def to_category(self) -> str:
        if not self.scores:
            return "NO"
        if self.total_score >= 2.0:
            return "PASS"
        return "FAIL"


@dataclass
class ArticleRecord:
    """Complete article record with all decisions."""
    # Original ATLAS columns (WL)
    library: str = ""
    global_id: str = ""
    local_id: str = ""
    title: str = ""
    abstract: str = ""
    keywords: str = ""
    
    # Original ATLAS columns (GL)
    posicao: str = ""
    url: str = ""
    source_file: str = ""
    
    # Decision fields
    literature_type: str = ""  # "WL" or "GL"
    ec_decision: str = ""
    ic_decision: str = ""
    qc_score: str = ""
    final_decision: str = ""
    
    # Internal LLM reasoning (NOT exported)
    _llm_reasoning: Optional[Dict] = None


class ATLASLoader:
    """Load and parse ATLAS Excel exports."""
    
    WL_REQUIRED_COLUMNS = {"Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords"}
    GL_REQUIRED_COLUMNS = {"Posicao", "Title", "URL", "Source_File"}
    
    @staticmethod
    def validate_wl_schema(df: pd.DataFrame) -> None:
        """
        Validate WL DataFrame has required columns.
        Raises exception if missing columns detected.
        
        Args:
            df: White Literature DataFrame
        Raises:
            ValueError: If required columns are missing
        """
        missing = ATLASLoader.WL_REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required WL columns: {sorted(missing)}. "
                f"Required: {sorted(ATLASLoader.WL_REQUIRED_COLUMNS)}"
            )
    
    @staticmethod
    def validate_gl_schema(df: pd.DataFrame) -> None:
        """
        Validate GL DataFrame has required columns.
        Raises exception if missing columns detected.
        
        Args:
            df: Grey Literature DataFrame
        Raises:
            ValueError: If required columns are missing
        """
        missing = ATLASLoader.GL_REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required GL columns: {sorted(missing)}. "
                f"Required: {sorted(ATLASLoader.GL_REQUIRED_COLUMNS)}"
            )
    
    @staticmethod
    def load_atlas_file(file_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load ATLAS Excel file and extract WL and GL sheets.
        Supports both 'WL/GL' and 'White Literature/Grey Literature' naming.
        
        Returns:
            (wl_df, gl_df)
        
        Raises:
            ValueError: If required sheets or columns are missing
        """
        # Try standard names first, then ATLAS names
        try:
            wl_df = pd.read_excel(file_path, sheet_name="WL")
            gl_df = pd.read_excel(file_path, sheet_name="GL")
        except:
            try:
                wl_df = pd.read_excel(file_path, sheet_name="White Literature")
                gl_df = pd.read_excel(file_path, sheet_name="Grey Literature")
            except Exception as e:
                raise ValueError(f"Cannot find WL/GL sheets in {file_path}: {e}")
        
        # Validate schema - fail FAST with clear error messages
        ATLASLoader.validate_wl_schema(wl_df)
        ATLASLoader.validate_gl_schema(gl_df)
        
        return wl_df, gl_df
    
    @staticmethod
    def normalize_wl_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure WL has required columns."""
        required = ["Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords"]
        for col in required:
            if col not in df.columns:
                df[col] = ""
        return df
    
    @staticmethod
    def normalize_gl_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure GL has required columns."""
        required = ["Posicao", "Title", "URL", "Source_File"]
        for col in required:
            if col not in df.columns:
                df[col] = ""
        return df


class ExclusionCriteria:
    """EC evaluation logic."""
    
    CRITERIA = {
        "EC1": "Not empirical software engineering research",
        "EC2": "Published before 2015",
        "EC3": "Not peer-reviewed (for WL)",
        "EC4": "Duplicate publication (by Global_ID)"
    }
    
    @classmethod
    def evaluate(cls, title: str, abstract: str, year: Optional[int] = None, 
                 is_wl: bool = True, is_duplicate: bool = False) -> EligibilityDecision:
        """
        Evaluate exclusion criteria for an article.
        Internal LLM reasoning is generated but not exported.
        
        Args:
            is_duplicate: Boolean flag indicating if this is a duplicate Global_ID
        """
        text = f"{title} {abstract}".lower()
        
        # EC2: Published before 2015
        if year and year < 2015:
            return EligibilityDecision(
                decision="exclude",
                criterion="EC2",
                reason=f"Published in {year}, before 2015 threshold"
            )
        
        # EC1: Not empirical SE research
        se_keywords = ["software", "software engineering", "programming", "development", 
                       "code", "developer", "software engineer", "agile", "devops"]
        if not any(kw in text for kw in se_keywords):
            return EligibilityDecision(
                decision="exclude",
                criterion="EC1",
                reason="No software engineering context detected"
            )
        
        # EC4: Duplicate (by Global_ID - deterministic primary key matching)
        if is_duplicate:
            return EligibilityDecision(
                decision="exclude",
                criterion="EC4",
                reason="Duplicate Global_ID detected"
            )
        
        # EC3: Not peer-reviewed (WL only)
        if is_wl:
            if not abstract or len(abstract.strip()) < 50:
                return EligibilityDecision(
                    decision="exclude",
                    criterion="EC3",
                    reason="No sufficient abstract for peer-review assessment"
                )
        
        # No exclusion criteria triggered
        return EligibilityDecision(
            decision="include",
            criterion="NO",
            reason="Passed all exclusion criteria"
        )
    
    @classmethod
    def get_llm_reasoning(cls, title: str, abstract: str, year: Optional[int] = None,
                          is_wl: bool = True) -> Dict:
        """
        Generate internal LLM reasoning for EC decision.
        NOT exported - used only for debugging/correctness.
        """
        from src.core.llm_reasoning import generate_ec_rationale
        
        result = generate_ec_rationale(
            article_title=title,
            article_abstract=abstract[:1000] if abstract else "",
            year=year,
            literature_type="WL" if is_wl else "GL",
            ec_decision="include",  # Will be determined by evaluate()
            ec_reason=None,
            criteria=cls.CRITERIA
        )
        return result


class InclusionCriteria:
    """IC evaluation logic."""
    
    CRITERIA = {
        "IC1": "Addresses recruitment/selection practices in software organizations",
        "IC2": "Reports empirical findings (qualitative or quantitative)",
        "IC3": "Focuses on software industry context"
    }
    
    @classmethod
    def evaluate(cls, title: str, abstract: str) -> EligibilityDecision:
        """
        Evaluate inclusion criteria for an article.
        """
        text = f"{title} {abstract}".lower()
        
        # IC1: Recruitment/selection in software orgs
        recruitment_keywords = ["recruit", "hire", "hiring", "selection", "talent", 
                                "interview", "hiring process", "recruitment"]
        has_recruitment = any(kw in text for kw in recruitment_keywords)
        
        # IC2: Empirical findings
        empirical_keywords = ["empirical", "study", "research", "survey", "case study",
                              "experiment", "quantitative", "qualitative", "results", "findings"]
        has_empirical = any(kw in text for kw in empirical_keywords)
        
        # IC3: Software industry context
        industry_keywords = ["software", "software industry", "tech company", "IT company",
                             "software development", "software team", "developer", "programming"]
        has_industry = any(kw in text for kw in industry_keywords)
        
        # Decision logic: need at least IC1 + (IC2 OR IC3)
        if has_recruitment:
            if has_empirical or has_industry:
                return EligibilityDecision(
                    decision="include",
                    criterion="NO",
                    reason="Addresses SE R&S with empirical findings or industry context"
                )
            else:
                return EligibilityDecision(
                    decision="exclude",
                    criterion="IC2",
                    reason="Addresses recruitment but lacks empirical context"
                )
        
        # Check partial relevance
        if has_industry and has_empirical:
            return EligibilityDecision(
                decision="include",
                criterion="NO",
                reason="Empirical SE research relevant to scope"
            )
        
        return EligibilityDecision(
            decision="exclude",
            criterion="IC1",
            reason="Does not address recruitment/selection in software context"
        )
    
    @classmethod
    def get_llm_reasoning(cls, title: str, abstract: str, is_wl: bool = True) -> Dict:
        """Generate internal LLM reasoning for IC decision."""
        from src.core.llm_reasoning import generate_ic_rationale
        
        result = generate_ic_rationale(
            article_title=title,
            article_abstract=abstract[:1000] if abstract else "",
            year=None,
            literature_type="WL" if is_wl else "GL",
            ic_decision="include",
            ic_reason=None,
            criteria=cls.CRITERIA,
            ec_passed=True
        )
        return result


class QualityCriteria:
    """QC scoring logic."""
    
    WL_CRITERIA = {
        "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
        "WL-Q2": "Is the research methodology adequately described and appropriate?",
        "WL-Q3": "Are the findings clearly supported by the collected data?",
        "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
    }
    
    GL_CRITERIA = {
        "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
        "GL-Q2": "Is the source of experience transparent (e.g., specific hiring cycle)?",
        "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
        "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
    }
    
    THRESHOLD = 2.0
    
    @classmethod
    def evaluate(cls, title: str, abstract: str, literature_type: str) -> QualityDecision:
        """
        Evaluate quality criteria for an article.
        """
        text = f"{title} {abstract}".lower()
        
        if literature_type == "WL":
            criteria = cls.WL_CRITERIA
        else:
            criteria = cls.GL_CRITERIA
        
        scores = {}
        
        for criterion, description in criteria.items():
            score = cls._evaluate_criterion(criterion, text, description)
            scores[criterion] = score
        
        total = sum(scores.values())
        decision = "include" if total >= cls.THRESHOLD else "exclude"
        
        return QualityDecision(
            scores=scores,
            total_score=total,
            decision=decision,
            literature_type=literature_type
        )
    
    @classmethod
    def _evaluate_criterion(cls, criterion: str, text: str, description: str) -> float:
        """Score a single criterion (0, 0.5, or 1.0)."""
        
        if criterion.startswith("WL"):
            if criterion == "WL-Q1":
                # Aims and context stated
                if any(kw in text for kw in ["aim", "objective", "purpose", "research question", 
                                              "goal", "context", "motivation"]):
                    return 1.0
                elif any(kw in text for kw in ["investigate", "explore", "examine"]):
                    return 0.5
                return 0.0
            
            elif criterion == "WL-Q2":
                # Methodology described
                if any(kw in text for kw in ["methodology", "method", "approach", "design", 
                                              "procedure", "technique"]):
                    if any(kw in text for kw in ["survey", "case study", "experiment", "interview",
                                                  "qualitative", "quantitative"]):
                        return 1.0
                    return 0.5
                return 0.0
            
            elif criterion == "WL-Q3":
                # Findings supported
                if any(kw in text for kw in ["result", "finding", "conclusion", "show", "demonstrate",
                                             "indicate", "reveal"]):
                    return 1.0
                elif "discussion" in text:
                    return 0.5
                return 0.0
            
            elif criterion == "WL-Q4":
                # Limitations discussed
                if any(kw in text for kw in ["limitation", "threat", "validity", "reliability", 
                                              "constraint", "future work"]):
                    return 1.0
                elif "discussion" in text:
                    return 0.5
                return 0.0
        
        else:  # GL criteria
            if criterion == "GL-Q1":
                # Author expertise stated
                if any(kw in text for kw in ["author", "expert", "experience", "years", "background",
                                              "senior", "lead", "manager"]):
                    return 1.0
                elif any(kw in text for kw in ["we", "our", "based on"]):
                    return 0.5
                return 0.0
            
            elif criterion == "GL-Q2":
                # Source transparency
                if any(kw in text for kw in ["company", "organization", "team", "department",
                                              "size", "location", "industry"]):
                    return 1.0
                elif "case" in text or "example" in text:
                    return 0.5
                return 0.0
            
            elif criterion == "GL-Q3":
                # Artifacts support claims
                if any(kw in text for kw in ["data", "metric", "statistic", "figure", "table",
                                              "example", "artifact", "tool", "process"]):
                    return 1.0
                elif any(kw in text for kw in ["show", "result", "experience"]):
                    return 0.5
                return 0.0
            
            elif criterion == "GL-Q4":
                # Beyond marketing
                if any(kw in text for kw in ["challenge", "difficulty", "problem", "issue", 
                                              "lesson", "learn", "recommend"]):
                    return 1.0
                elif any(kw in text for kw in ["benefit", "advantage", "feature"]):
                    return 0.5
                return 0.0
        
        return 0.0
    
    @classmethod
    def get_llm_reasoning(cls, title: str, abstract: str, literature_type: str,
                          scores: Dict[str, float], total: float) -> Dict:
        """Generate internal LLM reasoning for QC decision."""
        from src.core.llm_reasoning import generate_qc_rationale
        
        result = generate_qc_rationale(
            article_title=title,
            article_abstract=abstract[:1000] if abstract else "",
            literature_type=literature_type,
            scores=scores,
            total_score=total,
            decision="include" if total >= cls.THRESHOLD else "exclude",
            threshold=cls.THRESHOLD
        )
        return result


class APOLLODecisionEngine:
    """
    Main decision engine that processes ATLAS data through EC/IC/QC pipeline.
    
    Design: Pure functional behavior - no persistent state for evaluation.
    Duplicate detection is computed at batch level before iteration.
    
    Protocol Support:
    - Optional protocol parameter for configurable EC/IC/QC criteria
    - If protocol=None (default), uses hardcoded default behavior
    - If protocol provided, uses ProtocolEngine for evaluation
    - Maintains full backward compatibility
    """
    
    def __init__(self, enable_llm_reasoning: bool = True, protocol: Dict = None):
        """
        Initialize APOLLO decision engine.
        
        Args:
            enable_llm_reasoning: Whether to generate internal LLM reasoning
            protocol: Optional protocol definition for configurable criteria.
                     If None, uses default APOLLO behavior (backward compatible).
        """
        self.enable_llm_reasoning = enable_llm_reasoning
        self.protocol = protocol
        
        # Protocol engine - lazy loaded only when protocol provided
        self._protocol_engine = None
        if protocol:
            from src.core.protocol_engine import ProtocolEngine
            self._protocol_engine = ProtocolEngine(protocol)
    
    def _precompute_duplicate_global_ids(self, wl_df: pd.DataFrame) -> set:
        """
        Pre-compute set of duplicate Global_IDs at batch level.
        This is deterministic and order-independent.
        
        Returns:
            Set of Global_ID values that appear more than once.
        """
        # Get all non-empty Global_IDs
        global_ids = wl_df['Global_ID'].dropna().astype(str)
        global_ids = global_ids[global_ids != '']
        
        # Find duplicates: IDs that appear more than once
        value_counts = global_ids.value_counts()
        duplicate_ids = set(value_counts[value_counts > 1].index)
        
        return duplicate_ids
    
    def process_wl_articles(self, wl_df: pd.DataFrame) -> List[ArticleRecord]:
        """Process White Literature articles with pure functional behavior."""
        # Pre-compute duplicate Global_IDs at batch level (deterministic, order-independent)
        duplicate_global_ids = self._precompute_duplicate_global_ids(wl_df)
        
        # Track which IDs we've seen DURING iteration (for sequential processing)
        # But this is cleared/reset per run - not persisted across calls
        seen_ids_this_run = set()
        
        results = []
        
        for _, row in wl_df.iterrows():
            record = ArticleRecord()
            record.literature_type = "WL"
            
            # Preserve original ATLAS columns
            record.library = str(row.get("Library", ""))
            record.global_id = str(row.get("Global_ID", ""))
            record.local_id = str(row.get("Local_ID", ""))
            record.title = str(row.get("Title", ""))
            record.abstract = str(row.get("Abstract", ""))
            record.keywords = str(row.get("Keywords", ""))
            
            # Extract year if available
            year = self._extract_year(record.title, record.abstract)
            
            # Check for duplicates: if Global_ID is in duplicate set AND we've seen it before
            # This ensures second occurrence gets flagged as EC4
            is_duplicate = (record.global_id in duplicate_global_ids and 
                           record.global_id in seen_ids_this_run)
            
            # Step 1: EC
            if self._protocol_engine:
                # Protocol-driven evaluation
                data = {
                    "title": record.title,
                    "abstract": record.abstract,
                    "year": year,
                    "global_id": record.global_id,
                    "text_combined": f"{record.title} {record.abstract}".lower()
                }
                decision, criterion, reason = self._protocol_engine.evaluate_ec(
                    data, "WL", is_duplicate
                )
                ec_result = EligibilityDecision(
                    decision=decision,
                    criterion=criterion,
                    reason=reason
                )
            else:
                # Default behavior (backward compatible)
                ec_result = ExclusionCriteria.evaluate(
                    title=record.title,
                    abstract=record.abstract,
                    year=year,
                    is_wl=True,
                    is_duplicate=is_duplicate
                )
            record.ec_decision = ec_result.to_display()
            
            # Mark this Global_ID as seen for this run
            if record.global_id:
                seen_ids_this_run.add(record.global_id)
            
            # Internal LLM reasoning (not exported)
            if self.enable_llm_reasoning:
                record._llm_reasoning = {
                    "EC": ExclusionCriteria.get_llm_reasoning(
                        record.title, record.abstract, year, True
                    )
                }
            
            # Step 2: IC (only if EC passed)
            if ec_result.decision == "include":
                if self._protocol_engine:
                    data = {
                        "title": record.title,
                        "abstract": record.abstract,
                        "text_combined": f"{record.title} {record.abstract}".lower()
                    }
                    decision, criterion, reason = self._protocol_engine.evaluate_ic(data, "WL")
                    ic_result = EligibilityDecision(
                        decision=decision,
                        criterion=criterion,
                        reason=reason
                    )
                else:
                    ic_result = InclusionCriteria.evaluate(
                        title=record.title,
                        abstract=record.abstract
                    )
                record.ic_decision = ic_result.to_display()
                
                if self.enable_llm_reasoning:
                    record._llm_reasoning["IC"] = InclusionCriteria.get_llm_reasoning(
                        record.title, record.abstract, True
                    )
                
                # Step 3: QC (only if IC passed)
                if ic_result.decision == "include":
                    if self._protocol_engine:
                        data = {
                            "title": record.title,
                            "abstract": record.abstract,
                            "text_combined": f"{record.title} {record.abstract}".lower()
                        }
                        decision, scores, total = self._protocol_engine.evaluate_qc(data, "WL")
                        qc_result = QualityDecision(
                            scores=scores,
                            total_score=total,
                            decision=decision,
                            literature_type="WL"
                        )
                    else:
                        qc_result = QualityCriteria.evaluate(
                            title=record.title,
                            abstract=record.abstract,
                            literature_type="WL"
                        )
                    record.qc_score = qc_result.to_display()
                    
                    if self.enable_llm_reasoning:
                        record._llm_reasoning["QC"] = QualityCriteria.get_llm_reasoning(
                            record.title, record.abstract, "WL",
                            qc_result.scores, qc_result.total_score
                        )
                    
                    # Final decision based on QC
                    record.final_decision = "INCLUDE" if qc_result.decision == "include" else "EXCLUDE"
                else:
                    record.qc_score = "N/A"
                    record.final_decision = "EXCLUDE"
            else:
                record.ic_decision = "N/A"
                record.qc_score = "N/A"
                record.final_decision = "EXCLUDE"
            
            results.append(record)
        
        return results
    
    def process_gl_articles(self, gl_df: pd.DataFrame) -> List[ArticleRecord]:
        """
        Process Grey Literature articles.
        
        GL Policy:
        - EC: Applied (using title only - no abstract available)
        - IC: SKIPPED - GL has no abstract in ATLAS format, cannot evaluate relevance
        - QC: SKIPPED - IC must pass first
        
        This is deterministic: any GL that passes EC will show IC="SKIPPED" 
        and Decision="EXCLUDE" because evaluation is not possible without abstract.
        """
        results = []
        
        for _, row in gl_df.iterrows():
            record = ArticleRecord()
            record.literature_type = "GL"
            
            # Preserve original ATLAS columns
            record.posicao = str(row.get("Posicao", ""))
            record.title = str(row.get("Title", ""))
            record.url = str(row.get("URL", ""))
            record.source_file = str(row.get("Source_File", ""))
            
            # For GL, use title only (no abstract in ATLAS format)
            abstract = ""
            title = record.title
            
            # Step 1: EC (simplified for GL - no peer review check)
            if self._protocol_engine:
                data = {
                    "title": title,
                    "abstract": abstract,
                    "year": None,
                    "global_id": "",
                    "text_combined": title.lower()
                }
                decision, criterion, reason = self._protocol_engine.evaluate_ec(
                    data, "GL", False
                )
                ec_result = EligibilityDecision(
                    decision=decision,
                    criterion=criterion,
                    reason=reason
                )
            else:
                ec_result = ExclusionCriteria.evaluate(
                    title=title,
                    abstract=abstract,
                    year=None,
                    is_wl=False,
                    is_duplicate=False
                )
            record.ec_decision = ec_result.to_display()
            
            # Internal LLM reasoning
            if self.enable_llm_reasoning:
                record._llm_reasoning = {
                    "EC": ExclusionCriteria.get_llm_reasoning(title, abstract, None, False)
                }
            
            # Step 2: IC - EXPLICIT POLICY FOR GL
            # GL has no abstract in ATLAS format, so IC cannot be evaluated
            # This is deterministic: SKIPPED means "cannot evaluate due to missing data"
            if ec_result.decision == "include":
                # Cannot evaluate IC without abstract - explicit SKIPPED policy
                record.ic_decision = "SKIPPED"
                
                if self.enable_llm_reasoning:
                    record._llm_reasoning["IC"] = {
                        "decision": "skipped",
                        "reason": "GL has no abstract in ATLAS format - IC evaluation not possible",
                        "model": "policy"
                    }
                
                # Step 3: QC - SKIPPED because IC not evaluated
                record.qc_score = "SKIPPED"
                record.final_decision = "EXCLUDE"  # Explicit: SKIPPED IC → EXCLUDE
            else:
                # EC excluded
                record.ic_decision = "N/A"
                record.qc_score = "N/A"
                record.final_decision = "EXCLUDE"
            
            results.append(record)
        
        return results
    
    @staticmethod
    def _extract_year(title: str, abstract: str) -> Optional[int]:
        """Extract publication year from title or abstract."""
        import re
        text = f"{title} {abstract}"
        years = re.findall(r'\b(20[0-2][0-9]|201[0-5])\b', text)
        if years:
            return int(max(years))
        return None
    
    def export_to_excel(self, output_path: str, wl_results: List[ArticleRecord], 
                        gl_results: List[ArticleRecord], 
                        wl_snowball: List[ArticleRecord] = None):
        """
        Export results to Excel with EXACT column structure.
        
        WL Sheet: Library, Global_ID, Local_ID, Title, Abstract, Keywords, 
                  CIs1, CEs1, Revisor 1, CIs2, CEs2, Revisor 2, Decision
        GL Sheet: Posicao, Title, URL, Source_File, Revisor 1 EC, Revisor 1 IC, Decision
        WL Seeds (HERMES): Same as WL - PREPARATION LAYER ONLY
        
        NOTE: APOLLO does NOT execute snowballing. This sheet exports selected WL
        papers as candidate seeds for future HERMES system to process. APOLLO scope
        ends at EC/IC/QC evaluation and selection/export.
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # WL Sheet - Exactly as specified
            wl_columns = [
                "Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords",
                "CIs1", "CEs1", "Revisor 1", "CIs2", "CEs2", "Revisor 2", "Decision"
            ]
            
            wl_data = []
            for r in wl_results:
                wl_data.append({
                    "Library": r.library,
                    "Global_ID": r.global_id,
                    "Local_ID": r.local_id,
                    "Title": r.title,
                    "Abstract": r.abstract,
                    "Keywords": r.keywords,
                    "CIs1": r.ic_decision,       # IC decision (APOLLO)
                    "CEs1": r.ec_decision,       # EC decision (APOLLO)
                    "Revisor 1": "APOLLO",       # Single reviewer simulation
                    "CIs2": "",                  # Not used - empty
                    "CEs2": "",                  # Not used - empty
                    "Revisor 2": "",             # Not used - empty
                    "Decision": r.final_decision
                })
            wl_df = pd.DataFrame(wl_data, columns=wl_columns)
            wl_df.to_excel(writer, sheet_name="WL", index=False)
            
            # GL Sheet - Exactly as specified
            gl_columns = ["Posicao", "Title", "URL", "Source_File", "Revisor 1 EC", "Revisor 1 IC", "Decision"]
            
            gl_data = []
            for r in gl_results:
                gl_data.append({
                    "Posicao": r.posicao,
                    "Title": r.title,
                    "URL": r.url,
                    "Source_File": r.source_file,
                    "Revisor 1 EC": r.ec_decision,
                    "Revisor 1 IC": r.ic_decision,
                    "Decision": r.final_decision
                })
            gl_df = pd.DataFrame(gl_data, columns=gl_columns)
            gl_df.to_excel(writer, sheet_name="GL", index=False)
            
            # WL Seeds (HERMES Preparation) - Empty placeholder for future HERMES system
            # APOLLO does NOT execute snowballing. Only exports selected WL papers as seeds.
            # This sheet should remain empty in current APOLLO version.
            if wl_snowball:
                sb_data = []
                for r in wl_snowball:
                    sb_data.append({
                        "Library": r.library,
                        "Global_ID": r.global_id,
                        "Local_ID": r.local_id,
                        "Title": r.title,
                        "Abstract": r.abstract,
                        "Keywords": r.keywords,
                        "CIs1": r.ic_decision,
                        "CEs1": r.ec_decision,
                        "Revisor 1": "APOLLO",
                        "CIs2": "",
                        "CEs2": "",
                        "Revisor 2": "",
                        "Decision": r.final_decision
                    })
                sb_df = pd.DataFrame(sb_data, columns=wl_columns)
            else:
                # Empty structure ready for HERMES
                sb_df = pd.DataFrame(columns=wl_columns)
            sb_df.to_excel(writer, sheet_name="WL Seeds for HERMES", index=False)


def process_atlas_file(input_path: str, output_path: str, enable_llm: bool = True):
    """
    Main entry point - process ATLAS Excel file and export decisions.
    
    Args:
        input_path: Path to ATLAS Excel file
        output_path: Path for output Excel file
        enable_llm: Whether to enable LLM reasoning (default True)
    """
    import time
    start_time = time.time()
    
    print(f"Loading ATLAS file: {input_path}")
    
    # Load ATLAS data (includes schema validation)
    wl_df, gl_df = ATLASLoader.load_atlas_file(input_path)
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    print(f"Loaded {len(wl_df)} WL articles, {len(gl_df)} GL articles")
    
    # Process articles
    engine = APOLLODecisionEngine(enable_llm_reasoning=enable_llm)
    
    print("Processing WL articles...")
    wl_results = engine.process_wl_articles(wl_df)
    
    print("Processing GL articles...")
    gl_results = engine.process_gl_articles(gl_df)
    
    # Export
    print(f"Exporting to: {output_path}")
    engine.export_to_excel(output_path, wl_results, gl_results)
    
    # Audit logging
    execution_time_ms = int((time.time() - start_time) * 1000)
    try:
        from src.core.audit_logger import log_apollo_run
        log_path = log_apollo_run(input_path, None, wl_results, gl_results, execution_time_ms)
        print(f"Audit log: {log_path}")
    except ImportError:
        pass  # Audit logging is optional
    
    # Summary
    wl_included = sum(1 for r in wl_results if r.final_decision == "INCLUDE")
    gl_included = sum(1 for r in gl_results if r.final_decision == "INCLUDE")
    
    print(f"\n=== Summary ===")
    print(f"WL: {len(wl_results)} processed, {wl_included} included")
    print(f"GL: {len(gl_results)} processed, {gl_included} included")
    print(f"Output: {output_path}")
    
    return wl_results, gl_results


def export_apollo_selection_criteria(
    input_path: str,
    output_filename: str = "APOLLO_Selection_Criteria.xlsx",
    enable_llm: bool = True
) -> str:
    """
    SINGLE CLEAN EXPORT FUNCTION
    
    This is the ONLY allowed export endpoint for APOLLO.
    
    Generates exactly one Excel file with 3 sheets:
    - WL: Library, Global_ID, Local_ID, Title, Abstract, Keywords, CIs1, CEs1, Revisor 1, CIs2, CEs2, Revisor 2, Decision
    - GL: Posicao, Title, URL, Source_File, Revisor 1 EC, Revisor 1 IC, Decision
    - WL Seeds for HERMES: Empty placeholder for future HERMES system (APOLLO does NOT execute snowballing)
    
    NOTE: APOLLO does NOT execute snowballing. It only prepares export structure.
    Snowballing will be handled by the future HERMES system.
    
    Args:
        input_path: Path to ATLAS Excel file (with WL and GL sheets)
        output_filename: Output filename (default: APOLLO_Selection_Criteria.xlsx)
        enable_llm: Enable LLM reasoning internally (not exported)
    
    Returns:
        Path to the output file
    """
    # Determine output path (same directory as input, or current directory)
    import os
    input_dir = os.path.dirname(input_path)
    if not input_dir:
        input_dir = "."
    output_path = os.path.join(input_dir, output_filename)
    
    print(f"APOLLO: Processing {input_path}")
    print(f"APOLLO: Output will be saved to {output_path}")
    
    # Load ATLAS data (handle different sheet names)
    wl_df = pd.read_excel(input_path, sheet_name="White Literature")
    gl_df = pd.read_excel(input_path, sheet_name="Grey Literature")
    
    # Normalize columns
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    # Drop extra columns if present
    if '#' in gl_df.columns:
        gl_df = gl_df.drop(columns=['#'])
    
    print(f"APOLLO: Loaded {len(wl_df)} WL, {len(gl_df)} GL articles")
    
    # Process through EC -> IC -> QC pipeline
    import time
    start_time = time.time()
    engine = APOLLODecisionEngine(enable_llm_reasoning=enable_llm)
    
    print("APOLLO: Running EC/IC/QC pipeline...")
    wl_results = engine.process_wl_articles(wl_df)
    gl_results = engine.process_gl_articles(gl_df)
    
    # Export to single clean Excel file
    print(f"APOLLO: Exporting to {output_path}")
    engine.export_to_excel(output_path, wl_results, gl_results)
    
    # Audit logging
    execution_time_ms = int((time.time() - start_time) * 1000)
    try:
        from src.core.audit_logger import log_apollo_run
        log_path = log_apollo_run(input_path, None, wl_results, gl_results, execution_time_ms)
        print(f"APOLLO: Audit log saved to {log_path}")
    except ImportError:
        pass  # Audit logging is optional
    
    # Summary stats
    wl_inc = sum(1 for r in wl_results if r.final_decision == "INCLUDE")
    gl_inc = sum(1 for r in gl_results if r.final_decision == "INCLUDE")
    
    print(f"\n{'='*50}")
    print(f"APOLLO: Processing Complete")
    print(f"{'='*50}")
    print(f"  WL: {len(wl_results)} processed -> {wl_inc} included")
    print(f"  GL: {len(gl_results)} processed -> {gl_inc} included")
    print(f"  Output: {output_path}")
    print(f"{'='*50}")
    
    return output_path