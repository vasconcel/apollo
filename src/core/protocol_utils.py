"""
Protocol Compatibility Utilities

Centralized helpers for protocol field extraction with dict/object compatibility.
"""


def get_protocol_value(protocol, field: str, default=None):
    """
    Safely extract protocol field with dict/object compatibility.

    Handles both DynamicProtocol objects and legacy dict formats.
    """
    if protocol is None:
        return default

    if isinstance(protocol, dict):
        return protocol.get(field, default)

    return getattr(protocol, field, default)