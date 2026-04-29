# src/core/config_manager.py
import json
import os
from typing import Any, Dict

DEFAULT_CONFIG = {
    "project_name": "SE R&S Multivocal Literature Review",
    "description": "MLR on Software Engineering Recruitment and Selection based on Garousi et al. methodology.",
    
    # Alinhado com a Subseção 3.1.1 (Goals and Research Questions Definition)
    "research_questions": [
        "RQ1: What is the distribution, nature, and temporal evolution of academic and industry sources addressing SE R&S?",
        "RQ2: How is SE R&S conceptualized, and which stages of the hiring pipeline are most frequently addressed?",
        "RQ3: What challenges and friction points emerge across the SE R&S pipeline?",
        "RQ4: What practices, mechanisms, or design principles are reported as contributing to effective SE R&S?",
        "RQ5: How do academic (WL) and practitioner (GL) perspectives align or diverge?"
    ],
    
    # Alinhado com a Subseção 3.2.2 (Data Extraction Phase) e o GQM
    "extraction_fields": [
        "Extracted Context (Organizational scale, Geography, etc.)",
        "Pipeline Stages Addressed (RQ2)",
        "Identified Challenges & Frictions (RQ3)",
        "Practices & Design Principles (RQ4)",
        "Notes on WL/GL Divergence (RQ5)"
    ],
    
    # Alinhado com a Tabela 2 (Exclusion and Inclusion Criteria)
    "inclusion_criteria": {
        "IC1": "Sources explicitly addressing R&S processes for SE roles.",
        "IC2": "Sources describing stages, pipelines, structures, or procedures of SE R&S pipelines.",
        "IC3": "Sources reporting challenges, frictions, or perceptions related to SE R&S.",
        "IC4": "Sources describing practices, assessment methods, or evaluation mechanisms used in SE R&S.",
        "IC5": "Sources providing empirical findings or practitioner-reported experiences related to SE R&S practices."
    },
    "exclusion_criteria": {
        "EC1": "Sources not written in English.",
        "EC2": "Sources whose full text was unavailable after reasonable access attempts.",
        "EC3": "Short publications lacking sufficient methodological or experiential evidence (e.g., editorials, posters).",
        "EC4": "Sources published before 2015.",
        "EC5": "Sources unrelated to SE R&S.",
        "EC6": "Duplicate studies."
    },
    
    # Alinhado com a Tabela 3 (Quality Assessment Criteria for WL and GL)
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
            "GL-Q3: Are the claims supported by operational artifacts (e.g., process steps, rubrics, or data) rather than mere opinion?",
            "GL-Q4: Does the source provide insights beyond generic employer marketing (e.g., discussing trade-offs)?"
        ]
    },
    
    # Configurações técnicas de banco de dados e ingestão
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
        """Loads configuration from the JSON file, or falls back to defaults if not found/corrupted."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Merge file configurations with defaults to ensure no keys are missing
                    self._config = {**DEFAULT_CONFIG, **file_config}
            except Exception as e:
                print(f"Warning: Failed to load config: {e}. Using defaults.")
                self._config = DEFAULT_CONFIG.copy()
        else:
            # If the file doesn't exist, use the strictly aligned protocol defaults
            self._config = DEFAULT_CONFIG.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value by key."""
        return self._config.get(key, DEFAULT_CONFIG.get(key, default))

    @property
    def column_aliases(self) -> dict: 
        return self.get("column_aliases", {})
    
    @property
    def source_columns(self) -> list: 
        return self.get("source_columns", [])

def load_config(config_path: str = "project_config.json") -> ConfigManager:
    """Factory function to instantiate and load the ConfigManager."""
    return ConfigManager(config_path)