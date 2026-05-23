from abc import ABC, abstractmethod
import re
from typing import Dict, List, Optional, Any

from .screening_result import Evidence


class Rule(ABC):
    def __init__(self, rule_id: str, name: str, enabled: bool = True) -> None:
        self._rule_id = rule_id
        self._name = name
        self._enabled = enabled

    @property
    def rule_id(self) -> str:
        return self._rule_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @abstractmethod
    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        ...


class KeywordRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        keyword: str,
        fields: Optional[List[str]] = None,
        case_sensitive: bool = False,
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._keyword = keyword
        self._fields = fields or ["title", "abstract"]
        self._case_sensitive = case_sensitive

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        keyword = self._keyword if self._case_sensitive else self._keyword.lower()
        for field in self._fields:
            value = article.get(field, "")
            if not isinstance(value, str):
                continue
            text = value if self._case_sensitive else value.lower()
            if keyword in text:
                return Evidence(
                    rule_id=self._rule_id,
                    rule_name=self._name,
                    evidence_type="keyword",
                    match=self._keyword,
                    context=f"matched in {field}",
                )
        return None


class RegexRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        pattern: str,
        fields: Optional[List[str]] = None,
        enabled: bool = True,
        evidence_type: str = "regex",
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._pattern = re.compile(pattern, re.IGNORECASE)
        self._fields = fields or ["title", "abstract"]
        self._evidence_type = evidence_type

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        for field in self._fields:
            value = article.get(field, "")
            if not isinstance(value, str):
                continue
            match = self._pattern.search(value)
            if match:
                return Evidence(
                    rule_id=self._rule_id,
                    rule_name=self._name,
                    evidence_type=self._evidence_type,
                    match=match.group(),
                    context=f"pattern matched in {field}",
                )
        return None


class InclusionPatternRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        patterns: List[str],
        fields: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._patterns = [p.lower() for p in patterns]
        self._fields = fields or ["title", "abstract"]

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        for field in self._fields:
            value = article.get(field, "")
            if not isinstance(value, str):
                continue
            text = value.lower()
            for pattern in self._patterns:
                if pattern in text:
                    return Evidence(
                        rule_id=self._rule_id,
                        rule_name=self._name,
                        evidence_type="inclusion_pattern",
                        match=pattern,
                        context=f"inclusion pattern matched in {field}",
                    )
        return None


class ExclusionPatternRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        patterns: List[str],
        fields: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._patterns = [p.lower() for p in patterns]
        self._fields = fields or ["title", "abstract"]

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        for field in self._fields:
            value = article.get(field, "")
            if not isinstance(value, str):
                continue
            text = value.lower()
            for pattern in self._patterns:
                if pattern in text:
                    return Evidence(
                        rule_id=self._rule_id,
                        rule_name=self._name,
                        evidence_type="exclusion_pattern",
                        match=pattern,
                        context=f"exclusion pattern matched in {field}",
                    )
        return None


class MetadataRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        field: str,
        operator: str,
        value: Any,
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._field = field
        self._operator = operator
        self._value = value

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        actual = article.get(self._field)
        if actual is None:
            return None
        matched = False
        if self._operator == "eq":
            matched = actual == self._value
        elif self._operator == "ne":
            matched = actual != self._value
        elif self._operator == "contains":
            if isinstance(actual, str) and isinstance(self._value, str):
                matched = self._value.lower() in actual.lower()
        elif self._operator == "in":
            if isinstance(self._value, (list, set, tuple)):
                matched = actual in self._value
        if matched:
            return Evidence(
                rule_id=self._rule_id,
                rule_name=self._name,
                evidence_type="metadata",
                match=str(actual),
                context=f"{self._field} {self._operator} {self._value}",
            )
        return None


class PublicationYearRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._min_year = min_year
        self._max_year = max_year

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        year = article.get("year") or article.get("publication_year") or article.get("date")
        if year is None:
            return None
        try:
            year_int = int(year)
        except (ValueError, TypeError):
            return None
        if self._min_year is not None and year_int < self._min_year:
            return Evidence(
                rule_id=self._rule_id,
                rule_name=self._name,
                evidence_type="publication_year",
                match=str(year_int),
                context=f"year {year_int} < minimum {self._min_year}",
            )
        if self._max_year is not None and year_int > self._max_year:
            return Evidence(
                rule_id=self._rule_id,
                rule_name=self._name,
                evidence_type="publication_year",
                match=str(year_int),
                context=f"year {year_int} > maximum {self._max_year}",
            )
        return None


class VenueRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        allowed_venues: Optional[List[str]] = None,
        excluded_venues: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._allowed = [v.lower() for v in (allowed_venues or [])]
        self._excluded = [v.lower() for v in (excluded_venues or [])]

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        venue = (
            article.get("venue")
            or article.get("journal")
            or article.get("conference")
            or ""
        )
        if not isinstance(venue, str):
            return None
        venue_lower = venue.lower()
        if self._excluded:
            for v in self._excluded:
                if v in venue_lower:
                    return Evidence(
                        rule_id=self._rule_id,
                        rule_name=self._name,
                        evidence_type="venue",
                        match=venue,
                        context=f"excluded by pattern '{v}'",
                    )
        if self._allowed:
            for v in self._allowed:
                if v in venue_lower:
                    return Evidence(
                        rule_id=self._rule_id,
                        rule_name=self._name,
                        evidence_type="venue",
                        match=venue,
                        context=f"allowed by pattern '{v}'",
                    )
        return None


class LanguageRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        allowed_languages: List[str],
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._allowed = [lang.lower() for lang in allowed_languages]

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        lang = article.get("language") or ""
        if not isinstance(lang, str):
            return None
        if lang.lower() not in self._allowed:
            return Evidence(
                rule_id=self._rule_id,
                rule_name=self._name,
                evidence_type="language",
                match=lang,
                context=f"language '{lang}' not in allowed set",
            )
        return None


class DocumentTypeRule(Rule):
    def __init__(
        self,
        rule_id: str,
        name: str,
        allowed_types: List[str],
        enabled: bool = True,
    ) -> None:
        super().__init__(rule_id, name, enabled=enabled)
        self._allowed = [t.lower() for t in allowed_types]

    def evaluate(self, article: Dict[str, Any]) -> Optional[Evidence]:
        doc_type = article.get("document_type") or article.get("type") or ""
        if not isinstance(doc_type, str):
            return None
        if doc_type.lower() not in self._allowed:
            return Evidence(
                rule_id=self._rule_id,
                rule_name=self._name,
                evidence_type="document_type",
                match=doc_type,
                context=f"type '{doc_type}' not in allowed set",
            )
        return None


class RuleEngine:
    def __init__(self) -> None:
        self._rules: List[Rule] = []

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def add_rules(self, rules: List[Rule]) -> None:
        self._rules.extend(rules)

    @property
    def rules(self) -> List[Rule]:
        return list(self._rules)

    def evaluate_all(
        self, article: Dict[str, Any]
    ) -> tuple[List[Evidence], List[str]]:
        evidence: List[Evidence] = []
        triggered: List[str] = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            result = rule.evaluate(article)
            if result is not None:
                evidence.append(result)
                triggered.append(rule.rule_id)
        return evidence, triggered
