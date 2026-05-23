from typing import Dict, List, Optional, Any

from .deterministic_rules import (
    Rule,
    InclusionPatternRule,
    ExclusionPatternRule,
    MetadataRule,
    PublicationYearRule,
    VenueRule,
    LanguageRule,
    DocumentTypeRule,
    KeywordRule,
    RegexRule,
)


class ProtocolDefinition:
    def __init__(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[Dict[str, str]] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        allowed_venues: Optional[List[str]] = None,
        excluded_venues: Optional[List[str]] = None,
        allowed_languages: Optional[List[str]] = None,
        allowed_document_types: Optional[List[str]] = None,
        metadata_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.keywords = keywords or []
        self.regex_patterns = regex_patterns or {}
        self.min_year = min_year
        self.max_year = max_year
        self.allowed_venues = allowed_venues
        self.excluded_venues = excluded_venues
        self.allowed_languages = allowed_languages
        self.allowed_document_types = allowed_document_types
        self.metadata_rules = metadata_rules or []


class DSLCompiler:
    def compile(self, raw: Dict[str, Any]) -> ProtocolDefinition:
        include = raw.get("include", [])
        exclude = raw.get("exclude", [])
        keywords = raw.get("keywords", [])
        regex = raw.get("regex", {})
        years = raw.get("years", {})
        venues = raw.get("venues", {})
        languages = raw.get("languages")
        document_types = raw.get("document_types") or raw.get("types")
        metadata = raw.get("metadata", [])

        return ProtocolDefinition(
            include_patterns=include if isinstance(include, list) else [],
            exclude_patterns=exclude if isinstance(exclude, list) else [],
            keywords=keywords if isinstance(keywords, list) else [],
            regex_patterns=regex if isinstance(regex, dict) else {},
            min_year=years.get("min") if isinstance(years, dict) else None,
            max_year=years.get("max") if isinstance(years, dict) else None,
            allowed_venues=(
                venues.get("allowed") if isinstance(venues, dict) else None
            ),
            excluded_venues=(
                venues.get("excluded") if isinstance(venues, dict) else None
            ),
            allowed_languages=(
                languages if isinstance(languages, list) else None
            ),
            allowed_document_types=(
                document_types if isinstance(document_types, list) else None
            ),
            metadata_rules=metadata if isinstance(metadata, list) else [],
        )

    def to_rules(self, protocol: ProtocolDefinition) -> List[Rule]:
        rules: List[Rule] = []
        idx = 0

        for pattern in protocol.include_patterns:
            rules.append(
                InclusionPatternRule(
                    rule_id=f"include_{idx}",
                    name=f"Include pattern: {pattern}",
                    patterns=[pattern],
                )
            )
            idx += 1

        for pattern in protocol.exclude_patterns:
            rules.append(
                ExclusionPatternRule(
                    rule_id=f"exclude_{idx}",
                    name=f"Exclude pattern: {pattern}",
                    patterns=[pattern],
                )
            )
            idx += 1

        for kw in protocol.keywords:
            rules.append(
                KeywordRule(
                    rule_id=f"keyword_{idx}",
                    name=f"Keyword: {kw}",
                    keyword=kw,
                )
            )
            idx += 1

        for name, pattern_str in protocol.regex_patterns.items():
            rules.append(
                RegexRule(
                    rule_id=f"regex_{idx}",
                    name=f"Regex: {name}",
                    pattern=pattern_str,
                )
            )
            idx += 1

        if protocol.min_year is not None or protocol.max_year is not None:
            rules.append(
                PublicationYearRule(
                    rule_id=f"year_{idx}",
                    name="Publication year range",
                    min_year=protocol.min_year,
                    max_year=protocol.max_year,
                )
            )
            idx += 1

        if protocol.allowed_venues or protocol.excluded_venues:
            rules.append(
                VenueRule(
                    rule_id=f"venue_{idx}",
                    name="Venue filter",
                    allowed_venues=protocol.allowed_venues,
                    excluded_venues=protocol.excluded_venues,
                )
            )
            idx += 1

        if protocol.allowed_languages is not None:
            rules.append(
                LanguageRule(
                    rule_id=f"lang_{idx}",
                    name="Language filter",
                    allowed_languages=protocol.allowed_languages,
                )
            )
            idx += 1

        if protocol.allowed_document_types is not None:
            rules.append(
                DocumentTypeRule(
                    rule_id=f"doctype_{idx}",
                    name="Document type filter",
                    allowed_types=protocol.allowed_document_types,
                )
            )
            idx += 1

        for mr in protocol.metadata_rules:
            rules.append(
                MetadataRule(
                    rule_id=f"meta_{idx}",
                    name=f"Metadata: {mr.get('field', 'unknown')}",
                    field=mr["field"],
                    operator=mr.get("operator", "eq"),
                    value=mr["value"],
                )
            )
            idx += 1

        return rules

    def parse_yaml(self, yaml_str: str) -> ProtocolDefinition:
        import yaml

        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            raise ValueError("YAML root must be a mapping")
        return self.compile(data)

    def yaml_to_rules(self, yaml_str: str) -> List[Rule]:
        protocol = self.parse_yaml(yaml_str)
        return self.to_rules(protocol)
