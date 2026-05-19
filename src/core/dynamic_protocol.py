"""
APOLLO Dynamic Protocol Model
researcher-configurable screening criteria

This module provides:
- Protocol definition (EC/IC criteria)
- Protocol snapshot for audit
- Stage-aware criteria access
- Protocol versioning and locking
"""
import json
import hashlib
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from types import MappingProxyType


class ProtocolState(Enum):
    """Protocol lifecycle states."""
    DRAFT = "draft"
    LOCKED = "locked"
    ACTIVE_SESSION = "active_session"


class ProtocolTemplate:
    """Centralized protocol bootstrap templates."""

    SE_RS_BOOTSTRAP = {
        "name": "SE Recruitment & Selection (Default)",
        "version": "1.0.0",
        "template_version": "2024.1",
        "description": "Default bootstrap template for Software Engineering Recruitment & Selection studies",
        "ec": {
            "EC1": {"description": "Sources not written in English.", "enabled": True},
            "EC2": {"description": "Sources whose full text was unavailable after reasonable access attempts.", "enabled": True},
            "EC3": {"description": "Short publications lacking sufficient methodological or experiential evidence (e.g., editorials, posters, extended abstracts).", "enabled": True},
            "EC4": {"description": "Sources published before 2015.", "enabled": True},
            "EC5": {"description": "Sources unrelated to Software Engineering Recruitment & Selection (SE R&S).", "enabled": True},
            "EC6": {"description": "Duplicate studies.", "enabled": True},
        },
        "ic": {
            "IC1": {"description": "Sources explicitly addressing recruitment and selection (R&S) processes for software engineering roles.", "enabled": True},
            "IC2": {"description": "Sources describing stages, pipelines, structures, or procedures of SE R&S pipelines.", "enabled": True},
            "IC3": {"description": "Sources reporting challenges, frictions, or perceptions related to SE R&S.", "enabled": True},
            "IC4": {"description": "Sources describing practices, assessment methods, or evaluation mechanisms used in SE R&S.", "enabled": True},
            "IC5": {"description": "Sources providing empirical findings or practitioner-reported experiences related to SE R&S practices.", "enabled": True},
        },
    }

    KITCHENHAM_SLR = {
        "name": "Kitchenham SLR Template",
        "version": "1.0.0",
        "template_version": "2024.1",
        "description": "Standard Kitchenham systematic literature review criteria",
        "ec": {
            "EC1": {"description": "Not published in peer-reviewed venue", "enabled": True},
            "EC2": {"description": "Does not use empirical research methods", "enabled": True},
        },
        "ic": {
            "IC1": {"description": "Focuses on software engineering domain", "enabled": True},
            "IC2": {"description": "Addresses research questions explicitly", "enabled": True},
        },
    }

    GENERIC_MLR = {
        "name": "Generic MLR Template",
        "version": "1.0.0",
        "template_version": "2024.1",
        "description": "Generic minimum replication criteria for meta-analysis",
        "ec": {
            "EC1": {"description": "Not empirical study", "enabled": True},
            "EC2": {"description": "Duplicate publication", "enabled": True},
        },
        "ic": {
            "IC1": {"description": "Relevant to research scope", "enabled": True},
        },
    }

    @classmethod
    def get_template(cls, template_name: str) -> Optional[Dict]:
        """Get template by name."""
        templates = {
            "SE Recruitment & Selection (Default)": cls.SE_RS_BOOTSTRAP,
            "Kitchenham SLR Template": cls.KITCHENHAM_SLR,
            "Generic MLR Template": cls.GENERIC_MLR,
        }
        return templates.get(template_name)

    @classmethod
    def list_templates(cls) -> List[str]:
        """List available template names."""
        return list(ProtocolTemplate.get_template(t).get("name") for t in ["SE_RS_BOOTSTRAP", "KITCHENHAM_SLR", "GENERIC_MLR"])


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
        if not isinstance(data, dict):
            raise TypeError(f"Criterion.from_dict requires dict, got {type(data).__name__}")
        if "id" not in data:
            raise ValueError("Criterion.from_dict missing required field 'id'")
        if "description" not in data:
            raise ValueError("Criterion.from_dict missing required field 'description'")
        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            keywords=data.get("keywords", []) if isinstance(data.get("keywords"), list) else [],
            weight=float(data.get("weight", 1.0))
        )


def _normalize_criteria_for_hash(criteria: Dict[str, Any]) -> str:
    """
    Normalize criteria dict for deterministic hashing.
    
    IMPORTANT: Must produce SAME hash regardless of dict ordering.
    """
    if not criteria:
        return "[]"
    
    normalized_items = []
    for cid in sorted(criteria.keys()):
        c = criteria[cid]
        if isinstance(c, dict):
            normalized_items.append(f"{cid}:{c.get('description', '')}:{c.get('enabled', False)}")
        elif hasattr(c, 'to_dict'):
            d = c.to_dict()
            normalized_items.append(f"{cid}:{d.get('description', '')}:{d.get('enabled', False)}")
    
    return "|" .join(normalized_items)


@dataclass(frozen=True)
class ProtocolSnapshot:
    """
    Immutable protocol snapshot for reproducibility.
    
    Created when protocol is LOCKED.
    Never mutable after creation.
    Hash is deterministic - same protocol = same hash.
    """
    version: str
    hash: str
    name: str
    
    ec_criteria: Dict[str, Dict] = field(default_factory=dict)
    ic_criteria: Dict[str, Dict] = field(default_factory=dict)
    qc_criteria: Dict[str, Dict] = field(default_factory=dict)
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    protocol_state: str = "locked"

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "hash": self.hash,
            "name": self.name,
            "ec_criteria": dict(self.ec_criteria),
            "ic_criteria": dict(self.ic_criteria),
            "qc_criteria": dict(self.qc_criteria),
            "created_at": self.created_at,
            "protocol_state": self.protocol_state
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProtocolSnapshot":
        return cls(**data)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @staticmethod
    def compute_hash(protocol_data: Dict) -> str:
        """
        Compute deterministic hash of protocol data.
        
        IMPORTANT: Hash must be order-independent for dicts.
        """
        ec_normalized = _normalize_criteria_for_hash(protocol_data.get("ec", {}))
        ic_normalized = _normalize_criteria_for_hash(protocol_data.get("ic", {}))
        qc_normalized = _normalize_criteria_for_hash(protocol_data.get("qc", {}))
        
        version = protocol_data.get("version", "1.0.0")
        
        hash_input = f"{version}|{ec_normalized}|{ic_normalized}|{qc_normalized}"
        
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]
    
    @staticmethod
    def create_from_protocol(protocol) -> "ProtocolSnapshot":
        """
        Create immutable snapshot from protocol object.
        
        This should be called when protocol is LOCKED.
        """
        ec_dict = {}
        if hasattr(protocol, 'ec') and protocol.ec:
            for k, v in protocol.ec.criteria.items():
                if hasattr(v, 'to_dict'):
                    ec_dict[k] = v.to_dict()
                else:
                    ec_dict[k] = {"id": k, "description": getattr(v, 'description', ''), "enabled": getattr(v, 'enabled', True)}
        
        ic_dict = {}
        if hasattr(protocol, 'ic') and protocol.ic:
            for k, v in protocol.ic.criteria.items():
                if hasattr(v, 'to_dict'):
                    ic_dict[k] = v.to_dict()
                else:
                    ic_dict[k] = {"id": k, "description": getattr(v, 'description', ''), "enabled": getattr(v, 'enabled', True)}
        
        qc_dict = {}
        if hasattr(protocol, 'qc') and protocol.qc:
            for k, v in protocol.qc.criteria.items():
                if hasattr(v, 'to_dict'):
                    qc_dict[k] = v.to_dict()
                else:
                    qc_dict[k] = {"id": k, "description": getattr(v, 'description', ''), "enabled": getattr(v, 'enabled', True)}
        
        protocol_data = {
            "version": getattr(protocol, 'protocol_version', '1.0.0'),
            "ec": ec_dict,
            "ic": ic_dict,
            "qc": qc_dict
        }
        
        protocol_hash = getattr(protocol, 'protocol_hash', '') or ProtocolSnapshot.compute_hash(protocol_data)
        
        snapshot = ProtocolSnapshot(
            version=getattr(protocol, 'protocol_version', '1.0.0'),
            hash=protocol_hash,
            name=getattr(protocol, 'name', 'Unnamed Protocol'),
            ec_criteria=MappingProxyType(ec_dict),
            ic_criteria=MappingProxyType(ic_dict),
            qc_criteria=MappingProxyType(qc_dict),
            protocol_state="locked"
        )
        
        return snapshot
    
    def save_to_file(self, base_path: str = "data/protocol_snapshots") -> str:
        """Save snapshot to file and return path."""
        import os
        os.makedirs(base_path, exist_ok=True)
        
        filename = f"protocol_v{self.version}_{self.hash}.json"
        filepath = os.path.join(base_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        
        return filepath
    
    @staticmethod
    def load_from_file(filepath: str) -> "ProtocolSnapshot":
        """Load snapshot from file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ProtocolSnapshot.from_dict(data)


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
        if not isinstance(data, dict):
            raise TypeError(f"ECProtocol.from_dict requires dict, got {type(data).__name__}")
        criteria = {}
        for k, v in data.get("criteria", {}).items():
            if isinstance(v, dict):
                criteria[k] = Criterion.from_dict(v)
            elif isinstance(v, Criterion):
                criteria[k] = v
            else:
                raise ValueError(f"ECProtocol.from_dict: criteria['{k}'] must be dict or Criterion")
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
        if not isinstance(data, dict):
            raise TypeError(f"ICProtocol.from_dict requires dict, got {type(data).__name__}")
        criteria = {}
        for k, v in data.get("criteria", {}).items():
            if isinstance(v, dict):
                criteria[k] = Criterion.from_dict(v)
            elif isinstance(v, Criterion):
                criteria[k] = v
            else:
                raise ValueError(f"ICProtocol.from_dict: criteria['{k}'] must be dict or Criterion")
        return cls(criteria=criteria)
    
    def to_prompt(self) -> str:
        """Format for LLM prompt."""
        if not self.criteria:
            return "No IC criteria defined"
        lines = [f"IC{i+1}: {c.description}" for i, c in enumerate(self.criteria.values()) if c.enabled]
        return "\n".join(lines) if lines else "No IC criteria enabled"


class DynamicProtocol:
    """
    Dynamic protocol that can be configured per session.

    Researchers can:
    - Add/edit/remove criteria per stage
    - Save protocol snapshots
    - Load protocol from file
    - Export protocol
    - Lock protocol before screening
    - Create versioned snapshots for audit
    - Bootstrap from templates
    """

    def __init__(self, protocol_version: str = "1.0", template: Optional[Dict] = None):
        self._protocol_version = protocol_version
        self.created_at = datetime.now().isoformat()
        self._state = ProtocolState.DRAFT.value
        self._locked_at: Optional[str] = None
        self._protocol_hash: str = ""
        self._snapshot: Optional[ProtocolSnapshot] = None

        self.template_name: Optional[str] = None
        self.template_version: Optional[str] = None

        self._snapshots: List[ProtocolSnapshot] = []
        self._locked: bool = False

        self._ec: ECProtocol = ECProtocol(criteria={})
        self._ic: ICProtocol = ICProtocol(criteria={})

        if template:
            self._apply_template(template)

    def _apply_template(self, template: Dict) -> None:
        """Apply a bootstrap template to the protocol."""
        self.template_name = template.get("name")
        self.template_version = template.get("template_version")

        for ec_id, ec_data in template.get("ec", {}).items():
            self.ec.criteria[ec_id] = Criterion(
                id=ec_id,
                description=ec_data.get("description", ""),
                enabled=ec_data.get("enabled", True)
            )

        for ic_id, ic_data in template.get("ic", {}).items():
            self.ic.criteria[ic_id] = Criterion(
                id=ic_id,
                description=ic_data.get("description", ""),
                enabled=ic_data.get("enabled", True)
            )

    def get_template_info(self) -> Dict:
        """Get template metadata if bootstrapped from template."""
        if not self.template_name:
            return {"bootstrapped": False}
        return {
            "bootstrapped": True,
            "template_name": self.template_name,
            "template_version": self.template_version
        }
    
    def get_snapshot(self) -> Optional[ProtocolSnapshot]:
        """Get the protocol snapshot (only available after lock)."""
        return self._snapshot
    
    def get_protocol_info(self) -> Dict:
        """Get comprehensive protocol info including snapshot details."""
        info = self.get_summary()
        if self._snapshot:
            info["snapshot_hash"] = self._snapshot.hash
            info["snapshot_version"] = self._snapshot.version
            info["snapshot_created_at"] = self._snapshot.created_at
            info["snapshot_path"] = f"data/protocol_snapshots/protocol_v{self._snapshot.version}_{self._snapshot.hash}.json"
        return info

    def is_complete(self) -> tuple:
        """Check if protocol has minimum required criteria."""
        ec_count = len(self.ec.criteria)
        ic_count = len(self.ic.criteria)

        errors = []
        if ec_count == 0:
            errors.append("At least one Exclusion Criterion (EC) required")
        if ic_count == 0:
            errors.append("At least one Inclusion Criterion (IC) required")

        return (len(errors) == 0, errors)

    def compute_hash(self) -> str:
        """Compute deterministic hash of current protocol criteria."""
        ec_data = {k: v.to_dict() for k, v in self.ec.criteria.items()}
        ic_data = {k: v.to_dict() for k, v in self.ic.criteria.items()}
        qc_data = {k: v.to_dict() for k, v in self.qc.criteria.items()} if hasattr(self, 'qc') and self.qc else {}
        
        protocol_data = {
            "version": self.protocol_version,
            "ec": ec_data,
            "ic": ic_data,
            "qc": qc_data
        }
        
        return ProtocolSnapshot.compute_hash(protocol_data)

    def lock(self) -> None:
        """Lock the protocol, making it immutable for screening."""
        is_complete, errors = self.is_complete()
        if not is_complete:
            raise ValueError(f"Cannot lock incomplete protocol: {'; '.join(errors)}")

        if self._state == ProtocolState.ACTIVE_SESSION.value:
            raise ValueError("Cannot lock protocol with active session")

        if self._state == ProtocolState.LOCKED.value:
            raise ValueError("Protocol is already locked")

        self._state = ProtocolState.LOCKED.value
        self._locked = True
        self._locked_at = datetime.now().isoformat()
        self._protocol_hash = self.compute_hash()

        self._ec_criteria = {k: v for k, v in self._ec.criteria.items()}
        self._ic_criteria = {k: v for k, v in self._ic.criteria.items()}

        self._ec = ECProtocol(criteria=MappingProxyType(self._ec_criteria))
        self._ic = ICProtocol(criteria=MappingProxyType(self._ic_criteria))

        snapshot = ProtocolSnapshot.create_from_protocol(self)
        if snapshot:
            self._snapshot = snapshot
            snapshot_path = snapshot.save_to_file()
            print(f"[PROTOCOL SNAPSHOT] Created and saved: {snapshot_path}")

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        if self._locked:
            raise AttributeError("Locked protocols are immutable. State cannot be changed.")
        self._state = value

    @property
    def protocol_version(self) -> str:
        return self._protocol_version

    @protocol_version.setter
    def protocol_version(self, value: str) -> None:
        if self._locked:
            raise AttributeError("Locked protocols are immutable. Version cannot be changed.")
        self._protocol_version = value

    @property
    def protocol_hash(self) -> str:
        return self._protocol_hash

    @protocol_hash.setter
    def protocol_hash(self, value: str) -> None:
        if self._locked:
            raise AttributeError("Locked protocols are immutable. Hash cannot be changed.")
        self._protocol_hash = value

    @property
    def locked_at(self) -> Optional[str]:
        return self._locked_at

    @locked_at.setter
    def locked_at(self, value: str) -> None:
        if self._locked:
            raise AttributeError("Locked protocols are immutable. Lock timestamp cannot be changed.")
        self._locked_at = value

    @property
    def ec(self) -> "ECProtocol":
        return self._ec

    @ec.setter
    def ec(self, value: "ECProtocol") -> None:
        if self._locked:
            raise AttributeError("Locked protocols are immutable. EC criteria cannot be changed.")
        self._ec = value

    @property
    def ic(self) -> "ICProtocol":
        return self._ic

    @ic.setter
    def ic(self, value: "ICProtocol") -> None:
        if self._locked:
            raise AttributeError("Locked protocols are immutable. IC criteria cannot be changed.")
        self._ic = value

    def unlock(self) -> "DynamicProtocol":
        """
        Unlock and create a new protocol version for modification.
        Returns a new protocol instance with incremented version.
        """
        if self.state != ProtocolState.LOCKED.value:
            raise ValueError("Can only unlock locked protocols")

        version_parts = self.protocol_version.split(".")
        major = int(version_parts[0])
        new_version = f"{major + 1}.0"

        new_protocol = DynamicProtocol(protocol_version=new_version)
        new_protocol.ec = ECProtocol(criteria={k: Criterion.from_dict(v.to_dict()) for k, v in self.ec.criteria.items()})
        new_protocol.ic = ICProtocol(criteria={k: Criterion.from_dict(v.to_dict()) for k, v in self.ic.criteria.items()})

        return new_protocol

    def create_session(self) -> None:
        """Mark protocol as having an active session."""
        if self.state != ProtocolState.LOCKED.value:
            raise ValueError("Can only start session with locked protocol")
        self.state = ProtocolState.ACTIVE_SESSION.value

    def get_summary(self) -> Dict[str, Any]:
        """Get protocol summary for display."""
        ec_count = len(self.ec.criteria)
        ic_count = len(self.ic.criteria)
        ec_enabled = len([c for c in self.ec.criteria.values() if c.enabled])
        ic_enabled = len([c for c in self.ic.criteria.values() if c.enabled])

        return {
            "version": self.protocol_version,
            "state": self.state,
            "hash": self.protocol_hash,
            "ec_count": ec_count,
            "ic_count": ic_count,
            "ec_enabled": ec_enabled,
            "ic_enabled": ic_enabled,
            "locked_at": self.locked_at,
            "template_name": self.template_name,
            "template_version": self.template_version
        }

    def get_stage_protocol(self, stage: str):
        """Get protocol container for a specific stage."""
        if stage == "ec":
            return self.ec
        elif stage == "ic":
            return self.ic
        return None

    def get_criteria_for_stage(self, stage: str, literature_type: str = "WL") -> Dict[str, Criterion]:
        """Get enabled criteria for a stage."""
        if stage == "ec":
            return {k: v for k, v in self.ec.criteria.items() if v.enabled}
        elif stage == "ic":
            return {k: v for k, v in self.ic.criteria.items() if v.enabled}
        return {}
    
    def add_criterion(self, stage: str, criterion_id: str, description: str, **kwargs) -> None:
        """Add a new criterion."""
        criterion = Criterion(id=criterion_id, description=description, **kwargs)
        protocol = self.get_stage_protocol(stage)
        if protocol:
            protocol.criteria[criterion_id] = criterion

    def remove_criterion(self, stage: str, criterion_id: str, literature_type: str = "WL") -> None:
        """Remove a criterion."""
        protocol = self.get_stage_protocol(stage)
        if protocol and criterion_id in protocol.criteria:
            del protocol.criteria[criterion_id]

    def enable_criterion(self, stage: str, criterion_id: str, enabled: bool = True, literature_type: str = "WL") -> None:
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
            ic_protocol=self.ic.to_dict()
        )
        self._snapshots.append(snapshot)
        return snapshot
    
    def to_dict(self) -> Dict:
        """Export protocol as dictionary."""
        result = {
            "protocol_version": self.protocol_version,
            "created_at": self.created_at,
            "state": self.state,
            "locked_at": self.locked_at,
            "protocol_hash": self.protocol_hash,
            "template_name": self.template_name,
            "template_version": self.template_version,
            "ec": self.ec.to_dict(),
            "ic": self.ic.to_dict()
        }
        if self._snapshot:
            result["snapshot"] = self._snapshot.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "DynamicProtocol":
        """Load protocol from dictionary with defensive validation."""
        if not isinstance(data, dict):
            raise TypeError(f"DynamicProtocol.from_dict requires dict, got {type(data).__name__}")

        protocol = cls(protocol_version=data.get("protocol_version", "1.0"))
        protocol.created_at = data.get("created_at", datetime.now().isoformat())

        state = data.get("state", ProtocolState.DRAFT.value)
        protocol._state = state

        protocol._locked_at = data.get("locked_at")
        protocol._protocol_hash = data.get("protocol_hash", "")
        protocol.template_name = data.get("template_name")
        protocol.template_version = data.get("template_version")

        if state == ProtocolState.LOCKED.value:
            protocol._locked = True
            protocol._ec_criteria = {}
            protocol._ic_criteria = {}

        if "ec" in data:
            ec_data = data["ec"]
            if isinstance(ec_data, dict):
                ec = ECProtocol.from_dict(ec_data)
                if state == ProtocolState.LOCKED.value:
                    protocol._ec = ECProtocol(criteria=MappingProxyType(dict(ec.criteria)))
                    protocol._ec_criteria = {k: v for k, v in ec.criteria.items()}
                else:
                    protocol._ec = ec
            else:
                raise ValueError("DynamicProtocol.from_dict: 'ec' must be dict")

        if "ic" in data:
            ic_data = data["ic"]
            if isinstance(ic_data, dict):
                ic = ICProtocol.from_dict(ic_data)
                if state == ProtocolState.LOCKED.value:
                    protocol._ic = ICProtocol(criteria=MappingProxyType(dict(ic.criteria)))
                    protocol._ic_criteria = {k: v for k, v in ic.criteria.items()}
                else:
                    protocol._ic = ic
            else:
                raise ValueError("DynamicProtocol.from_dict: 'ic' must be dict")

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
