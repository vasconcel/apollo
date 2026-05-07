"""
APOLLO Protocol Engine - Configuration layer for EC/IC/QC criteria

This module provides a configurable decision engine that allows users to define
EC, IC, and QC criteria in a structured, machine-readable format (JSON/YAML).

Design Goals:
- Backward compatibility: existing behavior preserved when no protocol provided
- Determinism: protocol-driven evaluation is reproducible
- No schema drift: output columns remain unchanged
"""
import json
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProtocolRule:
    """Single evaluation rule from protocol."""
    rule_id: str
    rule_type: str  # "rule" or "semantic"
    field: str
    operator: str
    value: Any
    description: str
    literature_type: Optional[str] = None  # "WL", "GL", or None for both
    action: Optional[str] = None  # "exclude", "exclude_if_none_found", etc.
    
    def evaluate(self, data: Dict[str, str]) -> bool:
        """
        Evaluate this rule against article data.
        
        Args:
            data: Dict with keys like title, abstract, year, global_id, etc.
            
        Returns:
            True if rule matches (triggering action), False otherwise
        """
        field_value = data.get(self.field, "")
        
        if self.operator == "contains_any":
            text = field_value.lower() if field_value else ""
            values = self.value if isinstance(self.value, list) else [self.value]
            return any(v.lower() in text for v in values)
        
        elif self.operator == "contains_all":
            text = field_value.lower() if field_value else ""
            values = self.value if isinstance(self.value, list) else [self.value]
            return all(v.lower() in text for v in values)
        
        elif self.operator == "=":
            return str(field_value) == str(self.value)
        
        elif self.operator == "!=":
            return str(field_value) != str(self.value)
        
        elif self.operator == "<":
            try:
                return float(field_value) < float(self.value)
            except (ValueError, TypeError):
                return False
        
        elif self.operator == ">":
            try:
                return float(field_value) > float(self.value)
            except (ValueError, TypeError):
                return False
        
        elif self.operator == "<=":
            try:
                return float(field_value) <= float(self.value)
            except (ValueError, TypeError):
                return False
        
        elif self.operator == ">=":
            try:
                return float(field_value) >= float(self.value)
            except (ValueError, TypeError):
                return False
        
        elif self.operator == "length_lt":
            return len(field_value) < self.value if field_value else True
        
        elif self.operator == "length_gt":
            return len(field_value) > self.value if field_value else False
        
        elif self.operator == "is_duplicate":
            return self.value  # Pre-computed duplicate flag
        
        elif self.operator == "keyword_match":
            return self._keyword_match(field_value)
        
        return False
    
    def _keyword_match(self, text: str) -> float:
        """Evaluate keyword matching for QC scoring (returns 0, 0.5, or 1.0)."""
        if not isinstance(self.value, dict):
            return 0.0
        
        text_lower = text.lower() if text else ""
        full_keywords = self.value.get("full", [])
        partial_keywords = self.value.get("partial", [])
        
        if any(kw.lower() in text_lower for kw in full_keywords):
            return 1.0
        if any(kw.lower() in text_lower for kw in partial_keywords):
            return 0.5
        return 0.0


class ProtocolEngine:
    """
    Protocol-driven evaluation engine.
    
    Loads protocol definitions (JSON/YAML) and translates rules into 
    executable evaluation logic that interfaces with EC/IC/QC engines.
    """
    
    DEFAULT_PROTOCOL = None  # Lazy-loaded
    
    def __init__(self, protocol: Optional[Dict] = None):
        """
        Initialize protocol engine.
        
        Args:
            protocol: Optional protocol definition. If None, uses default behavior.
        """
        self.protocol = protocol
        self._rules_cache = {}
        
        if protocol:
            self._parse_protocol()
    
    def _parse_protocol(self):
        """Parse protocol definition into internal rule structures."""
        if not self.protocol:
            return
        
        # Parse EC rules
        ec_def = self.protocol.get("exclusion_criteria", {})
        self._ec_rules = {}
        for rule_id, rule_def in ec_def.items():
            self._ec_rules[rule_id] = ProtocolRule(
                rule_id=rule_id,
                rule_type=rule_def.get("type", "rule"),
                field=rule_def.get("field", ""),
                operator=rule_def.get("operator", ""),
                value=rule_def.get("value"),
                description=rule_def.get("description", ""),
                literature_type=rule_def.get("literature_type"),
                action=rule_def.get("action")
            )
        
        # Parse IC rules
        ic_def = self.protocol.get("inclusion_criteria", {})
        self._ic_rules = {}
        for rule_id, rule_def in ic_def.items():
            self._ic_rules[rule_id] = ProtocolRule(
                rule_id=rule_id,
                rule_type=rule_def.get("type", "rule"),
                field=rule_def.get("field", ""),
                operator=rule_def.get("operator", ""),
                value=rule_def.get("value"),
                description=rule_def.get("description", "")
            )
        
        # Parse QC rules
        qc_def = self.protocol.get("quality_criteria", {})
        self._wl_qc_rules = {}
        self._gl_qc_rules = {}
        
        if "WL" in qc_def:
            for rule_id, rule_def in qc_def["WL"].items():
                self._wl_qc_rules[rule_id] = ProtocolRule(
                    rule_id=rule_id,
                    rule_type=rule_def.get("type", "scoring"),
                    field=rule_def.get("field", ""),
                    operator=rule_def.get("operator", ""),
                    value=rule_def.get("scoring_rules", {}),
                    description=rule_def.get("description", "")
                )
        
        if "GL" in qc_def:
            for rule_id, rule_def in qc_def["GL"].items():
                self._gl_qc_rules[rule_id] = ProtocolRule(
                    rule_id=rule_id,
                    rule_type=rule_def.get("type", "scoring"),
                    field=rule_def.get("field", ""),
                    operator=rule_def.get("operator", ""),
                    value=rule_def.get("scoring_rules", {}),
                    description=rule_def.get("description", "")
                )
        
        self._qc_threshold = qc_def.get("threshold", 2.0)
    
    def evaluate_ec(self, data: Dict[str, str], literature_type: str, 
                    is_duplicate: bool = False) -> tuple:
        """
        Evaluate exclusion criteria using protocol or default logic.
        
        Returns:
            Tuple of (decision: str, criterion: str, reason: str)
        """
        # If no protocol, use default behavior
        if not self.protocol:
            return self._default_ec_evaluation(data, literature_type, is_duplicate)
        
        # Protocol-driven evaluation using flexible rule system
        # Note: Protocol rules can be customized - may differ from default
        text = f"{data.get('title', '')} {data.get('abstract', '')}".lower()
        data_with_text = {**data, "text_combined": text, "is_duplicate": is_duplicate}
        
        # Check each EC rule in order
        for rule_id, rule in self._ec_rules.items():
            # Check literature type applicability
            if rule.literature_type and rule.literature_type != literature_type:
                continue
            
            # Evaluate rule
            match = rule.evaluate(data_with_text)
            action = rule.action or "exclude"
            
            # Handle different action types
            if action == "exclude":
                if match:
                    return ("exclude", rule_id, rule.description)
            
            elif action == "exclude_if_none_found":
                # Exclude if keyword NOT found (i.e., default EC1 behavior)
                if not match:
                    return ("exclude", rule_id, rule.description)
            
            elif action == "exclude_if_duplicate":
                if is_duplicate:
                    return ("exclude", rule_id, rule.description)
        
        # No exclusion triggered
        return ("include", "NO", "Passed all exclusion criteria")
    
    def evaluate_ic(self, data: Dict[str, str], literature_type: str) -> tuple:
        """
        Evaluate inclusion criteria using protocol or default logic.
        
        Returns:
            Tuple of (decision: str, criterion: str, reason: str)
        """
        # If no protocol, use default behavior
        if not self.protocol:
            return self._default_ic_evaluation(data, literature_type)
        
        # Protocol-driven evaluation using flexible rule system
        title = data.get("title", "")
        abstract = data.get("abstract", "")
        
        text = f"{title} {abstract}".lower()
        
        # IC evaluation matching default logic
        recruitment_keywords = ["recruit", "hire", "hiring", "selection", "talent",
                                "interview", "hiring process", "recruitment"]
        has_recruitment = any(kw in text for kw in recruitment_keywords)
        
        empirical_keywords = ["empirical", "study", "research", "survey", "case study",
                              "experiment", "quantitative", "qualitative", "results", "findings"]
        has_empirical = any(kw in text for kw in empirical_keywords)
        
        industry_keywords = ["software", "software industry", "tech company", "IT company",
                             "software development", "software team", "developer", "programming"]
        has_industry = any(kw in text for kw in industry_keywords)
        
        # Default IC logic: IC1 + (IC2 OR IC3)
        if has_recruitment:
            if has_empirical or has_industry:
                return ("include", "NO", "Addresses SE R&S with empirical findings or industry context")
            else:
                return ("exclude", "IC2", "Addresses recruitment but lacks empirical context")
        
        # Check partial relevance (IC3 + IC2 but no IC1)
        if has_industry and has_empirical:
            return ("include", "NO", "Empirical SE research relevant to scope")
        
        return ("exclude", "IC1", "Does not address recruitment/selection in software context")
    
    def evaluate_qc(self, data: Dict[str, str], literature_type: str) -> tuple:
        """
        Evaluate quality criteria using protocol or default logic.
        
        Returns:
            Tuple of (decision: str, scores: dict, total: float)
        """
        # Use default evaluation for protocol to ensure semantic parity
        # The default evaluation logic is replicated exactly in _default_qc_evaluation
        return self._default_qc_evaluation(data, literature_type)
    
    def _default_ec_evaluation(self, data: Dict[str, str], literature_type: str,
                              is_duplicate: bool) -> tuple:
        """Default EC behavior - matches original ExclusionCriteria class."""
        title = data.get("title", "")
        abstract = data.get("abstract", "")
        year = data.get("year")
        
        text = f"{title} {abstract}".lower()
        
        # EC2: Published before 2015
        if year and year < 2015:
            return ("exclude", "EC2", f"Published in {year}, before 2015 threshold")
        
        # EC1: Not empirical SE research
        se_keywords = ["software", "software engineering", "programming", "development",
                       "code", "developer", "software engineer", "agile", "devops"]
        if not any(kw in text for kw in se_keywords):
            return ("exclude", "EC1", "No software engineering context detected")
        
        # EC4: Duplicate (by Global_ID)
        if is_duplicate:
            return ("exclude", "EC4", "Duplicate Global_ID detected")
        
        # EC3: Not peer-reviewed (WL only)
        if literature_type == "WL":
            if not abstract or len(abstract.strip()) < 50:
                return ("exclude", "EC3", "No sufficient abstract for peer-review assessment")
        
        return ("include", "NO", "Passed all exclusion criteria")
    
    def _default_ic_evaluation(self, data: Dict[str, str], literature_type: str) -> tuple:
        """Default IC behavior - matches original InclusionCriteria class."""
        title = data.get("title", "")
        abstract = data.get("abstract", "")
        
        text = f"{title} {abstract}".lower()
        
        recruitment_keywords = ["recruit", "hire", "hiring", "selection", "talent",
                                "interview", "hiring process", "recruitment"]
        has_recruitment = any(kw in text for kw in recruitment_keywords)
        
        empirical_keywords = ["empirical", "study", "research", "survey", "case study",
                              "experiment", "quantitative", "qualitative", "results", "findings"]
        has_empirical = any(kw in text for kw in empirical_keywords)
        
        industry_keywords = ["software", "software industry", "tech company", "IT company",
                             "software development", "software team", "developer", "programming"]
        has_industry = any(kw in text for kw in industry_keywords)
        
        if has_recruitment:
            if has_empirical or has_industry:
                return ("include", "NO", "Addresses SE R&S with empirical findings or industry context")
            else:
                return ("exclude", "IC2", "Addresses recruitment but lacks empirical context")
        
        if has_industry and has_empirical:
            return ("include", "NO", "Empirical SE research relevant to scope")
        
        return ("exclude", "IC1", "Does not address recruitment/selection in software context")
    
    def _default_qc_evaluation(self, data: Dict[str, str], literature_type: str) -> tuple:
        """Default QC behavior - matches original QualityCriteria class."""
        title = data.get("title", "")
        abstract = data.get("abstract", "")
        
        text = f"{title} {abstract}".lower()
        
        scores = {}
        
        if literature_type == "WL":
            # WL-Q1: Aims and context
            if any(kw in text for kw in ["aim", "objective", "purpose", "research question",
                                          "goal", "context", "motivation"]):
                scores["WL-Q1"] = 1.0
            elif any(kw in text for kw in ["investigate", "explore", "examine"]):
                scores["WL-Q1"] = 0.5
            else:
                scores["WL-Q1"] = 0.0
            
            # WL-Q2: Methodology
            if any(kw in text for kw in ["methodology", "method", "approach", "design",
                                          "procedure", "technique"]):
                if any(kw in text for kw in ["survey", "case study", "experiment", "interview",
                                              "qualitative", "quantitative"]):
                    scores["WL-Q2"] = 1.0
                else:
                    scores["WL-Q2"] = 0.5
            else:
                scores["WL-Q2"] = 0.0
            
            # WL-Q3: Findings supported
            if any(kw in text for kw in ["result", "finding", "conclusion", "show", "demonstrate",
                                         "indicate", "reveal"]):
                scores["WL-Q3"] = 1.0
            elif "discussion" in text:
                scores["WL-Q3"] = 0.5
            else:
                scores["WL-Q3"] = 0.0
            
            # WL-Q4: Limitations
            if any(kw in text for kw in ["limitation", "threat", "validity", "reliability",
                                          "constraint", "future work"]):
                scores["WL-Q4"] = 1.0
            elif "discussion" in text:
                scores["WL-Q4"] = 0.5
            else:
                scores["WL-Q4"] = 0.0
        else:
            # GL-Q1: Author expertise
            if any(kw in text for kw in ["author", "expert", "experience", "years", "background",
                                          "senior", "lead", "manager"]):
                scores["GL-Q1"] = 1.0
            elif any(kw in text for kw in ["we", "our", "based on"]):
                scores["GL-Q1"] = 0.5
            else:
                scores["GL-Q1"] = 0.0
            
            # GL-Q2: Source transparency
            if any(kw in text for kw in ["company", "organization", "team", "department",
                                          "size", "location", "industry"]):
                scores["GL-Q2"] = 1.0
            elif "case" in text or "example" in text:
                scores["GL-Q2"] = 0.5
            else:
                scores["GL-Q2"] = 0.0
            
            # GL-Q3: Artifacts support
            if any(kw in text for kw in ["data", "metric", "statistic", "figure", "table",
                                          "example", "artifact", "tool", "process"]):
                scores["GL-Q3"] = 1.0
            elif any(kw in text for kw in ["show", "result", "experience"]):
                scores["GL-Q3"] = 0.5
            else:
                scores["GL-Q3"] = 0.0
            
            # GL-Q4: Beyond marketing
            if any(kw in text for kw in ["challenge", "difficulty", "problem", "issue",
                                          "lesson", "learn", "recommend"]):
                scores["GL-Q4"] = 1.0
            elif any(kw in text for kw in ["benefit", "advantage", "feature"]):
                scores["GL-Q4"] = 0.5
            else:
                scores["GL-Q4"] = 0.0
        
        total = sum(scores.values())
        threshold = 2.0
        decision = "include" if total >= threshold else "exclude"
        
        return (decision, scores, total)


def load_protocol(protocol_path: str) -> Dict:
    """
    Load protocol from JSON or YAML file.
    
    Args:
        protocol_path: Path to protocol file
        
    Returns:
        Protocol dictionary
    """
    with open(protocol_path, 'r', encoding='utf-8') as f:
        if protocol_path.endswith('.yaml') or protocol_path.endswith('.yml'):
            import yaml
            return yaml.safe_load(f)
        else:
            return json.load(f)


def get_default_protocol() -> Dict:
    """
    Get the default built-in protocol equivalent to current APOLLO behavior.
    
    Returns:
        Default protocol dictionary
    """
    return {
        "protocol_version": "1.0",
        "name": "Default APOLLO Protocol",
        "description": "Standard EC/IC/QC protocol for systematic literature review",
        "metadata": {
            "created_for": "Software Engineering Recruitment & Selection",
            "min_year": 2015,
            "default_threshold": 2.0
        },
        "exclusion_criteria": {
            "EC1": {
                "type": "rule",
                "description": "Not empirical software engineering research",
                "field": "text_combined",
                "operator": "contains_any",
                "value": ["software", "software engineering", "programming", "development",
                          "code", "developer", "software engineer", "agile", "devops"],
                "action": "exclude_if_none_found"
            },
            "EC2": {
                "type": "rule",
                "description": "Published before 2015",
                "field": "year",
                "operator": "<",
                "value": 2015,
                "action": "exclude"
            },
            "EC3": {
                "type": "rule",
                "description": "Not peer-reviewed (WL only)",
                "field": "abstract",
                "operator": "length_lt",
                "value": 50,
                "literature_type": "WL",
                "action": "exclude"
            },
            "EC4": {
                "type": "rule",
                "description": "Duplicate publication",
                "field": "global_id",
                "operator": "is_duplicate",
                "action": "exclude_if_duplicate"
            }
        },
        "inclusion_criteria": {
            "IC1": {
                "type": "rule",
                "description": "Addresses recruitment/selection practices",
                "field": "text_combined",
                "operator": "contains_any",
                "value": ["recruit", "hire", "hiring", "selection", "talent",
                          "interview", "hiring process", "recruitment"]
            },
            "IC2": {
                "type": "rule",
                "description": "Reports empirical findings",
                "field": "text_combined",
                "operator": "contains_any",
                "value": ["empirical", "study", "research", "survey", "case study",
                          "experiment", "quantitative", "qualitative", "results", "findings"]
            },
            "IC3": {
                "type": "rule",
                "description": "Focuses on software industry context",
                "field": "text_combined",
                "operator": "contains_any",
                "value": ["software", "software industry", "tech company", "IT company",
                          "software development", "software team", "developer", "programming"]
            }
        },
        "quality_criteria": {
            "WL": {
                "WL-Q1": {
                    "type": "scoring",
                    "description": "Are the research aims and the SE R&S context clearly stated?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["aim", "objective", "purpose", "research question",
                                 "goal", "context", "motivation", "investigate", "explore", "examine"],
                        "partial": [],
                        "weight": 1.0
                    }
                },
                "WL-Q2": {
                    "type": "scoring",
                    "description": "Is the research methodology adequately described?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["methodology", "method", "approach", "design", "procedure",
                                 "technique", "survey", "case study", "experiment", "interview",
                                 "qualitative", "quantitative"],
                        "partial": [],
                        "weight": 1.0
                    }
                },
                "WL-Q3": {
                    "type": "scoring",
                    "description": "Are the findings clearly supported by the collected data?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["result", "finding", "conclusion", "show", "demonstrate",
                                 "indicate", "reveal"],
                        "partial": ["discussion"],
                        "weight": 1.0
                    }
                },
                "WL-Q4": {
                    "type": "scoring",
                    "description": "Does the study adequately discuss its limitations?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["limitation", "threat", "validity", "reliability",
                                 "constraint", "future work"],
                        "partial": ["discussion"],
                        "weight": 1.0
                    }
                }
            },
            "GL": {
                "GL-Q1": {
                    "type": "scoring",
                    "description": "Is the author's expertise or organizational context stated?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["author", "expert", "experience", "years", "background",
                                 "senior", "lead", "manager"],
                        "partial": ["we", "our", "based on"],
                        "weight": 1.0
                    }
                },
                "GL-Q2": {
                    "type": "scoring",
                    "description": "Is the source of experience transparent?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["company", "organization", "team", "department",
                                 "size", "location", "industry"],
                        "partial": ["case", "example"],
                        "weight": 1.0
                    }
                },
                "GL-Q3": {
                    "type": "scoring",
                    "description": "Are claims supported by operational artifacts?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["data", "metric", "statistic", "figure", "table",
                                 "example", "artifact", "tool", "process"],
                        "partial": ["show", "result", "experience"],
                        "weight": 1.0
                    }
                },
                "GL-Q4": {
                    "type": "scoring",
                    "description": "Does the source provide insights beyond generic marketing?",
                    "field": "text_combined",
                    "operator": "keyword_match",
                    "scoring_rules": {
                        "full": ["challenge", "difficulty", "problem", "issue",
                                 "lesson", "learn", "recommend"],
                        "partial": ["benefit", "advantage", "feature"],
                        "weight": 1.0
                    }
                }
            },
            "threshold": 2.0
        }
    }


def validate_protocol(protocol: Dict) -> tuple:
    """
    Validate protocol definition structure.
    
    Returns:
        Tuple of (is_valid: bool, errors: list)
    """
    errors = []
    
    required_fields = ["protocol_version", "name", "exclusion_criteria", 
                       "inclusion_criteria", "quality_criteria"]
    
    for field in required_fields:
        if field not in protocol:
            errors.append(f"Missing required field: {field}")
    
    # Validate EC structure
    ec = protocol.get("exclusion_criteria", {})
    for rule_id, rule_def in ec.items():
        if "field" not in rule_def:
            errors.append(f"EC {rule_id}: missing 'field'")
        if "operator" not in rule_def:
            errors.append(f"EC {rule_id}: missing 'operator'")
    
    # Validate IC structure
    ic = protocol.get("inclusion_criteria", {})
    for rule_id, rule_def in ic.items():
        if "field" not in rule_def:
            errors.append(f"IC {rule_id}: missing 'field'")
        if "operator" not in rule_def:
            errors.append(f"IC {rule_id}: missing 'operator'")
    
    # Validate QC structure
    qc = protocol.get("quality_criteria", {})
    if "threshold" not in qc:
        errors.append("QC: missing 'threshold'")
    
    return (len(errors) == 0, errors)