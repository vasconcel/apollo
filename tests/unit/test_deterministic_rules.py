"""Tests for deterministic_rules.py."""

import pytest
from src.screening.deterministic_rules import (
    Rule,
    KeywordRule,
    RegexRule,
    InclusionPatternRule,
    ExclusionPatternRule,
    MetadataRule,
    PublicationYearRule,
    VenueRule,
    LanguageRule,
    DocumentTypeRule,
    RuleEngine,
)


ARTICLE = {
    "title": "An Empirical Study on Software Engineering Hiring Practices",
    "abstract": "This study examines technical recruitment in the software industry.",
    "year": 2023,
    "venue": "Journal of Software Engineering",
    "language": "en",
    "document_type": "research_article",
    "type": "research_article",
    "author": "Alice Smith",
}


class TestKeywordRule:
    def test_matches_title(self):
        rule = KeywordRule("kw1", "Hiring keyword", keyword="Hiring")
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "keyword"
        assert "hiring" in ev.match.lower()

    def test_matches_abstract(self):
        rule = KeywordRule("kw1", "Recruitment keyword", keyword="recruitment")
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert "recruitment" in ev.match.lower()

    def test_no_match(self):
        rule = KeywordRule("kw1", "No match", keyword="quantum")
        ev = rule.evaluate(ARTICLE)
        assert ev is None

    def test_case_sensitive(self):
        rule = KeywordRule("kw1", "Case sensitive", keyword="empirical", case_sensitive=True)
        assert rule.evaluate({"title": "Empirical Study"}) is None
        rule2 = KeywordRule("kw2", "Case sensitive match", keyword="Empirical", case_sensitive=True)
        assert rule2.evaluate({"title": "Empirical Study"}) is not None

    def test_custom_fields(self):
        rule = KeywordRule("kw1", "Author match", keyword="Alice", fields=["author"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None

    def test_skips_non_string_fields(self):
        rule = KeywordRule("kw1", "Year field", keyword="2023", fields=["year"])
        assert rule.evaluate(ARTICLE) is None


class TestRegexRule:
    def test_matches_pattern(self):
        rule = RegexRule("re1", "Study pattern", pattern=r"[Ee]mpirical")
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "regex"

    def test_no_match(self):
        rule = RegexRule("re1", "No match", pattern=r"\d{5}")
        ev = rule.evaluate(ARTICLE)
        assert ev is None

    def test_custom_fields(self):
        rule = RegexRule("re1", "Venue pattern", pattern=r"Software", fields=["venue"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None


class TestInclusionPatternRule:
    def test_matches_single(self):
        rule = InclusionPatternRule("inc1", "Empirical", patterns=["empirical study"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "inclusion_pattern"

    def test_matches_multi(self):
        rule = InclusionPatternRule("inc1", "Multiple", patterns=["technical recruitment", "nonexistent"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None

    def test_no_match(self):
        rule = InclusionPatternRule("inc1", "No match", patterns=["systematic review"])
        ev = rule.evaluate(ARTICLE)
        assert ev is None


class TestExclusionPatternRule:
    def test_matches_exclusion(self):
        article = {"title": "Job Advertisement for Senior Developer"}
        rule = ExclusionPatternRule("exc1", "Job ad", patterns=["job advertisement"])
        ev = rule.evaluate(article)
        assert ev is not None
        assert ev.evidence_type == "exclusion_pattern"

    def test_no_exclusion(self):
        rule = ExclusionPatternRule("exc1", "No match", patterns=["blog post"])
        ev = rule.evaluate(ARTICLE)
        assert ev is None


class TestMetadataRule:
    def test_eq_match(self):
        rule = MetadataRule("m1", "Author match", field="author", operator="eq", value="Alice Smith")
        assert rule.evaluate(ARTICLE) is not None

    def test_eq_no_match(self):
        rule = MetadataRule("m1", "No match", field="author", operator="eq", value="Bob")
        assert rule.evaluate(ARTICLE) is None

    def test_ne_match(self):
        rule = MetadataRule("m1", "Not equal", field="author", operator="ne", value="Bob")
        assert rule.evaluate(ARTICLE) is not None

    def test_contains_match(self):
        rule = MetadataRule("m1", "Contains", field="venue", operator="contains", value="Software")
        assert rule.evaluate(ARTICLE) is not None

    def test_contains_no_match(self):
        rule = MetadataRule("m1", "No contains", field="venue", operator="contains", value="Medicine")
        assert rule.evaluate(ARTICLE) is None

    def test_in_match(self):
        rule = MetadataRule("m1", "In list", field="language", operator="in", value=["en", "fr"])
        assert rule.evaluate(ARTICLE) is not None

    def test_in_no_match(self):
        rule = MetadataRule("m1", "Not in list", field="language", operator="in", value=["fr", "de"])
        assert rule.evaluate(ARTICLE) is None

    def test_missing_field(self):
        rule = MetadataRule("m1", "Missing", field="nonexistent", operator="eq", value="x")
        assert rule.evaluate(ARTICLE) is None


class TestPublicationYearRule:
    def test_below_min(self):
        rule = PublicationYearRule("y1", "Min 2024", min_year=2024)
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "publication_year"

    def test_above_max(self):
        rule = PublicationYearRule("y1", "Max 2020", max_year=2020)
        ev = rule.evaluate(ARTICLE)
        assert ev is not None

    def test_within_range(self):
        rule = PublicationYearRule("y1", "Range 2020-2025", min_year=2020, max_year=2025)
        ev = rule.evaluate(ARTICLE)
        assert ev is None

    def test_missing_year(self):
        rule = PublicationYearRule("y1", "Missing year", min_year=2020)
        ev = rule.evaluate({"title": "No year"})
        assert ev is None

    def test_invalid_year_type(self):
        rule = PublicationYearRule("y1", "Invalid", min_year=2020)
        ev = rule.evaluate({"year": "unknown"})
        assert ev is None


class TestVenueRule:
    def test_allowed_venue(self):
        rule = VenueRule("v1", "Venue check", allowed_venues=["software engineering"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "venue"

    def test_excluded_venue(self):
        rule = VenueRule("v1", "Exclude venue", excluded_venues=["software"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert "excluded" in (ev.context or "")

    def test_no_match(self):
        rule = VenueRule("v1", "No match", allowed_venues=["medical"])
        ev = rule.evaluate(ARTICLE)
        assert ev is None

    def test_missing_venue(self):
        rule = VenueRule("v1", "Missing", allowed_venues=["anything"])
        ev = rule.evaluate({"title": "test"})
        assert ev is None


class TestLanguageRule:
    def test_allowed(self):
        rule = LanguageRule("l1", "English OK", allowed_languages=["en"])
        ev = rule.evaluate(ARTICLE)
        assert ev is None

    def test_not_allowed(self):
        rule = LanguageRule("l1", "Only French", allowed_languages=["fr"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "language"

    def test_missing_language(self):
        rule = LanguageRule("l1", "Missing", allowed_languages=["en"])
        ev = rule.evaluate({"title": "test"})
        assert ev is not None


class TestDocumentTypeRule:
    def test_allowed(self):
        rule = DocumentTypeRule("d1", "Type check", allowed_types=["research_article"])
        ev = rule.evaluate(ARTICLE)
        assert ev is None

    def test_not_allowed(self):
        rule = DocumentTypeRule("d1", "Only books", allowed_types=["book"])
        ev = rule.evaluate(ARTICLE)
        assert ev is not None
        assert ev.evidence_type == "document_type"

    def test_uses_type_field_fallback(self):
        article = {"type": "research_article"}
        rule = DocumentTypeRule("d1", "Type fallback", allowed_types=["research_article"])
        ev = rule.evaluate(article)
        assert ev is None


class TestRuleEngine:
    def test_add_and_evaluate(self):
        engine = RuleEngine()
        rule = KeywordRule("kw1", "Hiring", keyword="Hiring")
        engine.add_rule(rule)
        evidence, triggered = engine.evaluate_all(ARTICLE)
        assert len(evidence) == 1
        assert triggered == ["kw1"]

    def test_add_rules(self):
        engine = RuleEngine()
        rules = [
            KeywordRule("kw1", "Hiring", keyword="Hiring"),
            KeywordRule("kw2", "Quantum", keyword="quantum"),
        ]
        engine.add_rules(rules)
        evidence, triggered = engine.evaluate_all(ARTICLE)
        assert len(evidence) == 1
        assert triggered == ["kw1"]

    def test_no_match(self):
        engine = RuleEngine()
        rule = KeywordRule("kw1", "No match", keyword="nonexistent")
        engine.add_rule(rule)
        evidence, triggered = engine.evaluate_all(ARTICLE)
        assert evidence == []
        assert triggered == []

    def test_disabled_rule(self):
        engine = RuleEngine()
        rule = KeywordRule("kw1", "Hiring", keyword="Hiring", enabled=False)
        engine.add_rule(rule)
        evidence, triggered = engine.evaluate_all(ARTICLE)
        assert evidence == []

    def test_rules_property(self):
        engine = RuleEngine()
        rule = KeywordRule("kw1", "Test", keyword="test")
        engine.add_rule(rule)
        assert len(engine.rules) == 1
        assert engine.rules[0] is rule

    def test_multiple_rules_all_match(self):
        engine = RuleEngine()
        engine.add_rule(KeywordRule("kw1", "Empirical", keyword="Empirical"))
        engine.add_rule(KeywordRule("kw2", "Study", keyword="Study"))
        evidence, triggered = engine.evaluate_all(ARTICLE)
        assert len(evidence) == 2

    def test_mixed_match(self):
        engine = RuleEngine()
        engine.add_rule(KeywordRule("kw1", "Hiring", keyword="Hiring"))
        engine.add_rule(ExclusionPatternRule("exc1", "Blog", patterns=["blog post"]))
        evidence, triggered = engine.evaluate_all(ARTICLE)
        assert len(evidence) == 1
