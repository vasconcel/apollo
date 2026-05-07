"""
APOLLO Dynamic Protocol Model
 researcher-configurable screening criteria

This module provides:
- Protocol definition (EC/IC/QC criteria)
- Protocol snapshot for audit
- Stage-aware criteria access
"""
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class Criterion:
    """Single screening criterion."""
    id: str
    description: str
    enabled: bool = True
    keywords: List[str] = field(default_factory=list)
    weight: float = 1.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Criterion":
        return cls(**data)


@dataclass
class ECProtocol:
    """Exclusion Criteria protocol."""
    criteria: Dict[str, Criterion] = field(default_factory=dict)
    min_year: int = 2015
    
    def to_dict(self) -> Dict:
        return {
            "criteria": {k: v.to_dict() for k, v in self.criteria.items()},
            "min_year": self.min_year
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ECProtocol":
        criteria = {k: Criterion.from_dict(v) for k, v in data.get("criteria", {}).items()}
        return cls(criteria=criteria, min_year=data.get("min_year", 2015))
    
    def to_prompt(self) -> str:
        """Format for LLM prompt."""
        if not self.criteria:
            return "No EC criteria defined"
        lines = [f"EC{i+1}: {c.description}" for i, c in enumerate(self.criteria.values()) if c.enabled]
        return "\n".join(lines) if lines else "No EC criteria enabled"


@dataclass
class ICProtocol:
    """Inclusion Criteria protocol."""
    criteria: Dict[str, Criterion] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {"criteria": {k: v.to_dict() for k, v in self.criteria.items()}}
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ICProtocol":
        criteria = {k: Criterion.from_dict(v) for k, v in data.get("criteria", {}).items()}
        return cls(criteria=criteria)
    
    def to_prompt(self) -> str:
        """Format for LLM prompt."""
        if not self.criteria:
            return "No IC criteria defined"
        lines = [f"IC{i+1}: {c.description}" for i, c in enumerate(self.criteria.values()) if c.enabled]
        return "\n".join(lines) if lines else "No IC criteria enabled"


@dataclass
class QCProtocol:
    """Quality Assessment protocol."""
    criteria: Dict[str, Criterion] = field(default_factory=dict)
    threshold: float = 2.0
    
    def to_dict(self) -> Dict:
        return {
            "criteria": {k: v.to_dict() for k, v in self.criteria.items()},
            "threshold": self.threshold
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "QCProtocol":
        criteria = {k: Criterion.from_dict(v) for k, v in data.get("criteria", {}).items()}
        return cls(criteria=criteria, threshold=data.get("threshold", 2.0))
    
    def to_prompt(self) -> str:
        """Format for LLM prompt."""
        if not self.criteria:
            return "No QC criteria defined"
        lines = [f"QC{i+1}: {c.description} (weight: {c.weight})" for i, c in enumerate(self.criteria.values()) if c.enabled]
        return "\n".join(lines) if lines else "No QC criteria enabled"


@dataclass
class ProtocolSnapshot:
    """Snapshot of protocol at a point in time."""
    snapshot_id: str
    created_at: str
    stage: str  # "ec", "ic", "qc"
    
    ec_protocol: Dict
    ic_protocol: Dict
    qc_protocol: Dict
    
    snapshot_hash: str = ""
    
    def __post_init__(self):
        content = f"{self.snapshot_id}|{self.created_at}|{self.stage}|{json.dumps(self.ec_protocol, sort_keys=True)}"
        self.snapshot_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DynamicProtocol:
    """
    Dynamic protocol that can be configured per session.
    
    Researchers can:
    - Add/edit/remove criteria per stage
    - Save protocol snapshots
    - Load protocol from file
    - Export protocol
    """
    
    DEFAULT_EC = {
        "EC1": Criterion(
            id="EC1",
            description="Not empirical software engineering research",
            keywords=["software", "software engineering", "programming"]
        ),
        "EC2": Criterion(
            id="EC2", 
            description="Published before 2015",
            keywords=[]
        ),
        "EC3": Criterion(
            id="EC3",
            description="Not peer-reviewed (for WL)",
            keywords=[]
        ),
        "EC4": Criterion(
            id="EC4",
            description="Duplicate publication (by Global_ID)",
            keywords=[]
        )
    }
    
    DEFAULT_IC = {
        "IC1": Criterion(
            id="IC1",
            description="Addresses recruitment/selection practices in software organizations",
            keywords=["recruit", "hire", "hiring", "selection", "talent", "interview"]
        ),
        "IC2": Criterion(
            id="IC2",
            description="Reports empirical findings (qualitative or quantitative)",
            keywords=["empirical", "study", "research", "survey", "case study"]
        ),
        "IC3": Criterion(
            id="IC3",
            description="Focuses on software industry context",
            keywords=["software", "software industry", "tech company"]
        )
    }
    
    DEFAULT_QC = {
        "WL-Q1": Criterion(
            id="WL-Q1",
            description="Are the research aims and the SE R&S context clearly stated?",
            weight=1.0
        ),
        "WL-Q2": Criterion(
            id="WL-Q2",
            description="Is the research methodology adequately described and appropriate?",
            weight=1.0
        ),
        "WL-Q3": Criterion(
            id="WL-Q3",
            description="Are the findings clearly supported by the collected data?",
            weight=1.0
        ),
        "WL-Q4": Criterion(
            id="WL-Q4",
            description="Does the study adequately discuss its limitations or threats to validity?",
            weight=1.0
        )
    }
    
    def __init__(self, protocol_version: str = "1.0"):
        self.protocol_version = protocol_version
        self.created_at = datetime.now().isoformat()
        
        self.ec = ECProtocol(criteria=self.DEFAULT_EC.copy())
        self.ic = ICProtocol(criteria=self.DEFAULT_IC.copy())
        self.qc = QCProtocol(criteria=self.DEFAULT_QC.copy())
        
        self._snapshots: List[ProtocolSnapshot] = []
    
    def get_stage_protocol(self, stage: str) -> Any:
        """Get protocol for a specific stage."""
        if stage == "ec":
            return self.ec
        elif stage == "ic":
            return self.ic
        elif stage == "qc":
            return self.qc
        return None
    
    def get_criteria_for_stage(self, stage: str) -> Dict[str, Criterion]:
        """Get enabled criteria for a stage."""
        protocol = self.get_stage_protocol(stage)
        if protocol:
            return {k: v for k, v in protocol.criteria.items() if v.enabled}
        return {}
    
    def add_criterion(self, stage: str, criterion_id: str, description: str, **kwargs) -> None:
        """Add a new criterion."""
        criterion = Criterion(id=criterion_id, description=description, **kwargs)
        protocol = self.get_stage_protocol(stage)
        if protocol:
            protocol.criteria[criterion_id] = criterion
    
    def remove_criterion(self, stage: str, criterion_id: str) -> None:
        """Remove a criterion."""
        protocol = self.get_stage_protocol(stage)
        if protocol and criterion_id in protocol.criteria:
            del protocol.criteria[criterion_id]
    
    def enable_criterion(self, stage: str, criterion_id: str, enabled: bool = True) -> None:
        """Enable/disable a criterion."""
        protocol = self.get_stage_protocol(stage)
        if protocol and criterion_id in protocol.criteria:
            protocol.criteria[criterion_id].enabled = enabled
    
    def create_snapshot(self, stage: str) -> ProtocolSnapshot:
        """Create a protocol snapshot for audit."""
        snapshot = ProtocolSnapshot(
            snapshot_id=hashlib.sha256(f"{self.created_at}{stage}".encode()).hexdigest()[:12],
            created_at=datetime.now().isoformat(),
            stage=stage,
            ec_protocol=self.ec.to_dict(),
            ic_protocol=self.ic.to_dict(),
            qc_protocol=self.qc.to_dict()
        )
        self._snapshots.append(snapshot)
        return snapshot
    
    def to_dict(self) -> Dict:
        """Export protocol as dictionary."""
        return {
            "protocol_version": self.protocol_version,
            "created_at": self.created_at,
            "ec": self.ec.to_dict(),
            "ic": self.ic.to_dict(),
            "qc": self.qc.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DynamicProtocol":
        """Load protocol from dictionary."""
        protocol = cls(protocol_version=data.get("protocol_version", "1.0"))
        protocol.created_at = data.get("created_at", datetime.now().isoformat())
        
        if "ec" in data:
            protocol.ec = ECProtocol.from_dict(data["ec"])
        if "ic" in data:
            protocol.ic = ICProtocol.from_dict(data["ic"])
        if "qc" in data:
            protocol.qc = QCProtocol.from_dict(data["qc"])
        
        return protocol
    
    def save_to_file(self, path: str) -> None:
        """Save protocol to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, path: str) -> "DynamicProtocol":
        """Load protocol from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def create_default_protocol() -> DynamicProtocol:
    """Create default protocol for backward compatibility."""
    return DynamicProtocol()


def get_default_protocol() -> Dict:
    """
    Get the default built-in protocol equivalent to current APOLLO behavior.
    
    Returns:
        Default protocol dictionary
    """
    from src.core.dynamic_protocol import create_default_protocol
    return create_default_protocol().to_dict()
