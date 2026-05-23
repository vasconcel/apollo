"""Phase 5A: Domain Lexicon Engine.

Protocol-level semantic lexicons compiled from YAML.
Supports positive/negative evidence with configurable weights.
Stage-specific evidence (EC/IC).
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

from .screening_result import Evidence


@dataclass
class LexiconTerm:
    """A single lexicon term with weight and stage scope."""

    term: str
    weight: float = 0.5
    stages: Set[str] = field(default_factory=lambda: {"ec", "ic"})
    case_sensitive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "weight": self.weight,
            "stages": list(self.stages),
            "case_sensitive": self.case_sensitive,
        }


@dataclass
class LexiconCategory:
    """A category of lexicon terms (positive or negative evidence)."""

    name: str
    terms: List[LexiconTerm] = field(default_factory=list)
    is_positive: bool = True
    default_weight: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "terms": [t.to_dict() for t in self.terms],
            "is_positive": self.is_positive,
            "default_weight": self.default_weight,
        }


class DomainLexiconEngine:
    """Protocol-level semantic lexicon engine.

    Compiles YAML/JSON lexicon definitions into executable matchers.
    Each term produces evidence when matched in article text.

    Example lexicon YAML:
        positive:
          - term: "technical interview"
            weight: 0.6
          - term: "developer recruitment"
            weight: 0.5
          - term: "candidate assessment"
            weight: 0.4
        negative:
          - term: "salary"
            weight: 0.7
          - term: "job opening"
            weight: 0.6
          - term: "vacancy"
            weight: 0.6
          - term: "career path"
            weight: 0.3
    """

    def __init__(self) -> None:
        self._positive_categories: List[LexiconCategory] = []
        self._negative_categories: List[LexiconCategory] = []
        self._compiled_positive: List[Tuple[re.Pattern, LexiconTerm]] = []
        self._compiled_negative: List[Tuple[re.Pattern, LexiconTerm]] = []
        self._initialized = False

    def compile(self, lexicon_config: Dict[str, Any]) -> None:
        """Compile lexicon from config dict."""
        self._positive_categories = []
        self._negative_categories = []
        self._compiled_positive = []
        self._compiled_negative = []

        positive_terms = lexicon_config.get("positive", [])
        negative_terms = lexicon_config.get("negative", [])

        if isinstance(positive_terms, list):
            cat = LexiconCategory(
                name="positive", terms=[], is_positive=True, default_weight=0.5
            )
            for item in positive_terms:
                if isinstance(item, str):
                    term = LexiconTerm(term=item, weight=0.5)
                else:
                    term = LexiconTerm(
                        term=item.get("term", ""),
                        weight=item.get("weight", 0.5),
                        stages=set(item.get("stages", ["ec", "ic"])),
                        case_sensitive=item.get("case_sensitive", False),
                    )
                cat.terms.append(term)
                flags = 0 if term.case_sensitive else re.IGNORECASE
                pat = re.compile(re.escape(term.term), flags)
                self._compiled_positive.append((pat, term))
            self._positive_categories.append(cat)

        if isinstance(negative_terms, list):
            cat = LexiconCategory(
                name="negative", terms=[], is_positive=False, default_weight=0.5
            )
            for item in negative_terms:
                if isinstance(item, str):
                    term = LexiconTerm(term=item, weight=0.6)
                else:
                    term = LexiconTerm(
                        term=item.get("term", ""),
                        weight=item.get("weight", 0.6),
                        stages=set(item.get("stages", ["ec", "ic"])),
                        case_sensitive=item.get("case_sensitive", False),
                    )
                cat.terms.append(term)
                flags = 0 if term.case_sensitive else re.IGNORECASE
                pat = re.compile(re.escape(term.term), flags)
                self._compiled_negative.append((pat, term))
            self._negative_categories.append(cat)

        self._initialized = True

    def compile_yaml(self, yaml_str: str) -> None:
        """Compile lexicon from YAML string."""
        import yaml
        parsed = yaml.safe_load(yaml_str)
        if not isinstance(parsed, dict):
            parsed = {}
        self.compile(parsed)

    def evaluate(
        self,
        title: str = "",
        abstract: str = "",
        full_text: str = "",
        stage: str = "ec",
    ) -> List[Evidence]:
        """Evaluate article text against lexicon terms.

        Returns evidence for all matched terms.
        """
        if not self._initialized:
            return []

        text = f"{title} {abstract} {full_text}"
        evidence_list: List[Evidence] = []

        for pat, term in self._compiled_positive:
            if stage not in term.stages:
                continue
            if pat.search(text):
                evidence_list.append(
                    Evidence(
                        rule_id=f"lex_pos_{term.term}",
                        rule_name=f"Lexicon+: {term.term}",
                        evidence_type="lexicon",
                        match=term.term,
                        context=None,
                        confidence=term.weight,
                    )
                )

        for pat, term in self._compiled_negative:
            if stage not in term.stages:
                continue
            if pat.search(text):
                evidence_list.append(
                    Evidence(
                        rule_id=f"lex_neg_{term.term}",
                        rule_name=f"Lexicon-: {term.term}",
                        evidence_type="lexicon",
                        match=term.term,
                        context=None,
                        confidence=term.weight,
                    )
                )

        return evidence_list

    def compute_lexicon_score(
        self,
        title: str = "",
        abstract: str = "",
        full_text: str = "",
        stage: str = "ec",
    ) -> float:
        """Compute net lexicon contribution to confidence.

        Returns a float in [-1, 1] representing net lexicon evidence.
        Positive values support INCLUDE, negative support EXCLUDE.
        """
        evidence = self.evaluate(title, abstract, full_text, stage)
        if not evidence:
            return 0.0

        pos_score = 0.0
        neg_score = 0.0
        for ev in evidence:
            if ev.rule_id.startswith("lex_pos_"):
                pos_score += ev.confidence
            else:
                neg_score += ev.confidence

        total = pos_score + neg_score
        if total == 0:
            return 0.0
        return (pos_score - neg_score) / total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "positive_categories": [
                c.to_dict() for c in self._positive_categories
            ],
            "negative_categories": [
                c.to_dict() for c in self._negative_categories
            ],
        }
