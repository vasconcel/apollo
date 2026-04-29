# src/core/config_manager.py
import json
import os
from typing import Any, Dict

DEFAULT_CONFIG = {
    "project_name": "AIMS Project",
    "description": "Multivocal Literature Review using AIMS pipeline",
    "research_questions": [
        "RQ1: What is the distribution, nature, and temporal evolution of academic and industry sources?",
        "RQ2: How is SE R&S conceptualized, and which stages are most frequently addressed?",
        "RQ3: What challenges and friction points emerge across the SE R&S pipeline?",
        "RQ4: What practices, mechanisms, or design principles are reported?",
        "RQ5: How do academic and practitioner perspectives align or diverge?"
    ],
    "extraction_fields": [
        "Challenges and Frictions (RQ3)",
        "Practices and Design Principles (RQ4)",
        "Alignment of Perspectives (RQ5)"
    ],
    "inclusion_criteria": {
        "IC1": "Sources explicitly addressing R&S processes for SE roles.",
        "IC2": "Sources describing stages, pipelines, structures, or procedures.",
        "IC3": "Sources reporting challenges, frictions, or perceptions.",
        "IC4": "Sources describing practices, assessment methods, or mechanisms.",
        "IC5": "Sources providing empirical findings or practitioner-reported experiences."
    },
    "exclusion_criteria": {
        "EC1": "Sources not written in English.",
        "EC2": "Full text unavailable.",
        "EC3": "Short publications lacking sufficient evidence.",
        "EC4": "Published before 2015.",
        "EC5": "Unrelated to SE R&S.",
        "EC6": "Duplicate studies."
    },
    "quality_criteria": {
        "WL": [
            "WL-Q1: Are the research aims and the SE R&S context clearly stated?",
            "WL-Q2: Is the research methodology adequately described and appropriate?",
            "WL-Q3: Are the findings clearly supported by the collected data?",
            "WL-Q4: Does the study adequately discuss its limitations or threats to validity?"
        ],
        "GL": [
            "GL-Q1: Is the author's expertise or organizational context explicitly stated?",
            "GL-Q2: Is the source of experience transparent (e.g., specific hiring cycle, personal narrative)?",
            "GL-Q3: Are the claims supported by operational artifacts rather than mere opinion?",
            "GL-Q4: Does the source provide insights beyond generic employer marketing?"
        ]
    },
    "column_aliases": {"Original": "canonical"},
    "source_columns": ["title", "year", "abstract", "doi", "authors", "url"]
}

class ConfigManager:
    """Manages project configuration from JSON file."""
    def __init__(self, config_path: str = "project_config.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    self._config = {**DEFAULT_CONFIG, **file_config}
            except Exception as e:
                print(f"Warning: Failed to load config: {e}. Using defaults.")
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, DEFAULT_CONFIG.get(key, default))

    @property
    def column_aliases(self) -> dict: return self.get("column_aliases", {})
    
    @property
    def source_columns(self) -> list: return self.get("source_columns", [])

def load_config(config_path: str = "project_config.json") -> ConfigManager:
    return ConfigManager(config_path)