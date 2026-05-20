"""
Protocol Service Layer - Business logic for protocol operations.

This module provides protocol-related services that should not be in UI code.
Decoupled from Streamlit for testability and maintainability.
"""

from typing import Optional
from src.core.dynamic_protocol import ProtocolState


def ensure_protocol_locked(protocol) -> bool:
    """
    Ensure protocol is locked before screening begins.
    
    This is a system invariant: protocols must be LOCKED before any
    screening workflow can begin.
    
    Args:
        protocol: Protocol instance to check/lock
        
    Returns:
        True if protocol is now locked, False otherwise
    """
    if protocol is None:
        return False
    
    if protocol.state == ProtocolState.DRAFT.value:
        protocol.state = ProtocolState.LOCKED.value
        protocol.lock()
        return True
    
    return protocol.state == ProtocolState.LOCKED.value


def validate_protocol_for_screening(protocol) -> tuple[bool, Optional[str]]:
    """
    Validate that protocol is ready for screening.
    
    Returns:
        (is_valid, error_message)
    """
    if protocol is None:
        return False, "No protocol configured"
    
    if protocol.state != ProtocolState.LOCKED.value:
        return False, f"Protocol must be LOCKED (current: {protocol.state})"
    
    return True, None


def get_protocol_version_hash(protocol) -> str:
    """
    Get deterministic hash of protocol for reproducibility.
    """
    if hasattr(protocol, 'protocol_version'):
        return str(protocol.protocol_version)
    return "unknown"