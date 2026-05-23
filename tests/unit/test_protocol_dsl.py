"""Tests for protocol_dsl.py."""

import pytest
from src.screening.protocol_dsl import ProtocolDefinition, DSLCompiler
from src.screening.deterministic_rules import (
    InclusionPatternRule,
    ExclusionPatternRule,
    KeywordRule,
    RegexRule,
    PublicationYearRule,
    VenueRule,
    LanguageRule,
    DocumentTypeRule,
    MetadataRule,
)


SAMPLE_YAML = """
include:
  - empirical study
  - software engineering

exclude:
  - job advertisement
  - blog post

keywords:
  - recruitment
  - hiring

years:
  min: 2015
  max: 2025

venues:
  allowed:
    - software engineering
  excluded:
    - predatory

languages:
  - en

types:
  - research_article
"""


class TestProtocolDefinition:
    def test_defaults(self):
        p = ProtocolDefinition()
        assert p.include_patterns == []
        assert p.exclude_patterns == []
        assert p.keywords == []
        assert p.min_year is None
        assert p.max_year is None

    def test_custom_values(self):
        p = ProtocolDefinition(
            include_patterns=["a", "b"],
            exclude_patterns=["c"],
            keywords=["kw"],
            min_year=2020,
            max_year=2025,
        )
        assert p.include_patterns == ["a", "b"]
        assert p.min_year == 2020
        assert p.max_year == 2025


class TestDSLCompiler:
    def test_compile_dict(self):
        compiler = DSLCompiler()
        raw = {
            "include": ["empirical study"],
            "exclude": ["blog post"],
            "keywords": ["hiring"],
            "regex": {"email": r"\S+@\S+"},
            "years": {"min": 2020, "max": 2025},
            "venues": {"allowed": ["conference"], "excluded": ["predatory"]},
            "languages": ["en"],
            "types": ["article"],
        }
        protocol = compiler.compile(raw)
        assert protocol.include_patterns == ["empirical study"]
        assert protocol.exclude_patterns == ["blog post"]
        assert protocol.keywords == ["hiring"]
        assert protocol.regex_patterns == {"email": r"\S+@\S+"}
        assert protocol.min_year == 2020
        assert protocol.max_year == 2025
        assert protocol.allowed_venues == ["conference"]
        assert protocol.excluded_venues == ["predatory"]
        assert protocol.allowed_languages == ["en"]
        assert protocol.allowed_document_types == ["article"]

    def test_compile_empty(self):
        compiler = DSLCompiler()
        protocol = compiler.compile({})
        assert protocol.include_patterns == []
        assert protocol.exclude_patterns == []
        assert protocol.min_year is None

    def test_to_rules_all_types(self):
        compiler = DSLCompiler()
        protocol = ProtocolDefinition(
            include_patterns=["empirical study"],
            exclude_patterns=["blog post"],
            keywords=["hiring"],
            regex_patterns={"email": r"\S+@\S+"},
            min_year=2020,
            max_year=2025,
            allowed_venues=["conference"],
            excluded_venues=["predatory"],
            allowed_languages=["en"],
            allowed_document_types=["article"],
            metadata_rules=[{"field": "language", "operator": "eq", "value": "en"}],
        )
        rules = compiler.to_rules(protocol)
        types = [type(r).__name__ for r in rules]
        assert "InclusionPatternRule" in types
        assert "ExclusionPatternRule" in types
        assert "KeywordRule" in types
        assert "RegexRule" in types
        assert "PublicationYearRule" in types
        assert "VenueRule" in types
        assert "LanguageRule" in types
        assert "DocumentTypeRule" in types
        assert "MetadataRule" in types

    def test_to_rules_include_only(self):
        compiler = DSLCompiler()
        protocol = ProtocolDefinition(include_patterns=["test"])
        rules = compiler.to_rules(protocol)
        assert len(rules) == 1
        assert isinstance(rules[0], InclusionPatternRule)

    def test_to_rules_exclude_only(self):
        compiler = DSLCompiler()
        protocol = ProtocolDefinition(exclude_patterns=["test"])
        rules = compiler.to_rules(protocol)
        assert len(rules) == 1
        assert isinstance(rules[0], ExclusionPatternRule)

    def test_to_rules_keywords(self):
        compiler = DSLCompiler()
        protocol = ProtocolDefinition(keywords=["test"])
        rules = compiler.to_rules(protocol)
        assert len(rules) == 1
        assert isinstance(rules[0], KeywordRule)

    def test_parse_yaml(self):
        compiler = DSLCompiler()
        protocol = compiler.parse_yaml(SAMPLE_YAML)
        assert "empirical study" in protocol.include_patterns
        assert "job advertisement" in protocol.exclude_patterns
        assert "recruitment" in protocol.keywords
        assert protocol.min_year == 2015
        assert protocol.max_year == 2025
        assert protocol.allowed_languages == ["en"]
        assert protocol.allowed_document_types == ["research_article"]

    def test_yaml_to_rules(self):
        compiler = DSLCompiler()
        rules = compiler.yaml_to_rules(SAMPLE_YAML)
        assert len(rules) >= 5

    def test_parse_yaml_raises_on_scalar(self):
        compiler = DSLCompiler()
        with pytest.raises(ValueError, match="YAML root must be a mapping"):
            compiler.parse_yaml("just a string")

    def test_compile_invalid_types_handled_gracefully(self):
        compiler = DSLCompiler()
        protocol = compiler.compile({"include": "not a list"})
        assert protocol.include_patterns == []

    def test_yaml_to_rules_deterministic_ids(self):
        compiler = DSLCompiler()
        rules1 = compiler.yaml_to_rules(SAMPLE_YAML)
        rules2 = compiler.yaml_to_rules(SAMPLE_YAML)
        ids1 = [r.rule_id for r in rules1]
        ids2 = [r.rule_id for r in rules2]
        assert ids1 == ids2
