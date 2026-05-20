"""
Protocol query service - centralized protocol criteria access.

Provides deterministic protocol query helpers that operate purely
on protocol/domain objects. Contains NO Streamlit or UI imports.

This is the single source of truth for protocol criteria retrieval
across all layers (UI, core, advisory).

Dependency direction:
    UI -> Core (protocol_query_service) -> Advisory
    NEVER: Advisory -> UI
"""

from typing import Dict, Optional


_DEFAULT_IC_CRITERIA = {
    "IC1": "Addresses R&S practices",
    "IC2": "Reports empirical findings",
    "IC3": "Focuses on software industry context",
}

_DEFAULT_EC_CRITERIA = {
    "EC1": "Not empirical SE research",
    "EC2": "Published before 2015",
    "EC3": "Not peer-reviewed - WL sources must be peer-reviewed academic publications",
    "EC4": "Duplicate publication",
}

_DEFAULT_QC_CRITERIA = {
    "QC1": "Quality assessment criteria",
    "QC2": "Methodological rigor assessment",
}


def _extract_enabled_criteria(protocol, stage: str) -> Dict[str, str]:
    """
    Extract enabled criteria descriptions from protocol for a given stage.

    Args:
        protocol: A DynamicProtocol object (or duck-typed equivalent).
        stage: Stage name ('ec', 'ic', 'qc').

    Returns:
        Dict of {criterion_id: description} for enabled criteria,
        or None if protocol is None/missing the stage.
    """
    if protocol is None:
        return None
    try:
        stage_container = getattr(protocol, stage, None)
        if stage_container is not None and hasattr(stage_container, 'criteria'):
            return {
                k: v.description
                for k, v in stage_container.criteria.items()
                if v.enabled
            }
    except (AttributeError, TypeError):
        pass
    return None


def get_ic_criteria(protocol=None) -> Dict[str, str]:
    """
    Get enabled IC criteria descriptions from protocol.

    Args:
        protocol: A DynamicProtocol object. If None, returns defaults.

    Returns:
        Dict of {criterion_id: description} for enabled IC criteria.
    """
    result = _extract_enabled_criteria(protocol, 'ic')
    if result is not None:
        return result
    return dict(_DEFAULT_IC_CRITERIA)


def get_ec_criteria(protocol=None) -> Dict[str, str]:
    """
    Get enabled EC criteria descriptions from protocol.

    Args:
        protocol: A DynamicProtocol object. If None, returns defaults.

    Returns:
        Dict of {criterion_id: description} for enabled EC criteria.
    """
    result = _extract_enabled_criteria(protocol, 'ec')
    if result is not None:
        return result
    return dict(_DEFAULT_EC_CRITERIA)


def get_qc_criteria(protocol=None) -> Dict[str, str]:
    """
    Get enabled QC criteria descriptions from protocol.

    Args:
        protocol: A DynamicProtocol object. If None, returns defaults.

    Returns:
        Dict of {criterion_id: description} for enabled QC criteria.
    """
    result = _extract_enabled_criteria(protocol, 'qc')
    if result is not None:
        return result
    return dict(_DEFAULT_QC_CRITERIA)


def get_stage_criteria(protocol, stage: str) -> Dict[str, str]:
    """
    Get enabled criteria for a specific stage.

    Args:
        protocol: A DynamicProtocol object.
        stage: 'ec', 'ic', or 'qc'.

    Returns:
        Dict of {criterion_id: description} for enabled criteria.
    """
    if stage == "ec":
        return get_ec_criteria(protocol)
    elif stage == "ic":
        return get_ic_criteria(protocol)
    elif stage == "qc":
        return get_qc_criteria(protocol)
    return {}
