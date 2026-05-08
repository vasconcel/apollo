"""
Protocol Serialization Validation Suite

Validates roundtrip serialization for all protocol classes and ensures
Streamlit lifecycle compatibility.
"""
import sys
sys.path.insert(0, 'D:/Projetos/apollo')

import json
import tempfile
import traceback
from src.core.dynamic_protocol import (
    Criterion, ECProtocol, ICProtocol, QCProtocol,
    ProtocolSnapshot, DynamicProtocol, create_default_protocol
)


def test_criterion_roundtrip():
    """Test Criterion to_dict/from_dict roundtrip."""
    print("\n=== Criterion Roundtrip ===")
    
    original = Criterion(
        id="TEST1",
        description="Test criterion",
        enabled=True,
        keywords=["test", "keyword"],
        weight=2.5
    )
    
    d = original.to_dict()
    restored = Criterion.from_dict(d)
    
    assert d == {"id": "TEST1", "description": "Test criterion", "enabled": True, "keywords": ["test", "keyword"], "weight": 2.5}, f"to_dict mismatch: {d}"
    assert restored.id == original.id
    assert restored.description == original.description
    assert restored.enabled == original.enabled
    assert restored.keywords == original.keywords
    assert restored.weight == original.weight
    
    print("  PASS: Criterion serialization/deserialization works")
    return True


def test_ec_protocol_roundtrip():
    """Test ECProtocol roundtrip."""
    print("\n=== ECProtocol Roundtrip ===")
    
    ec = ECProtocol(criteria={
        "EC1": Criterion(id="EC1", description="Test EC1", keywords=["software"]),
        "EC2": Criterion(id="EC2", description="Test EC2")
    }, min_year=2020)
    
    d = ec.to_dict()
    restored = ECProtocol.from_dict(d)
    
    assert len(restored.criteria) == 2
    assert "EC1" in restored.criteria
    assert "EC2" in restored.criteria
    assert restored.criteria["EC1"].description == "Test EC1"
    assert restored.min_year == 2020
    
    print("  PASS: ECProtocol serialization/deserialization works")
    return True


def test_ic_protocol_roundtrip():
    """Test ICProtocol roundtrip."""
    print("\n=== ICProtocol Roundtrip ===")
    
    ic = ICProtocol(criteria={
        "IC1": Criterion(id="IC1", description="Test IC1")
    })
    
    d = ic.to_dict()
    restored = ICProtocol.from_dict(d)
    
    assert len(restored.criteria) == 1
    assert "IC1" in restored.criteria
    
    print("  PASS: ICProtocol serialization/deserialization works")
    return True


def test_qc_protocol_roundtrip():
    """Test QCProtocol roundtrip with WL/GL separation."""
    print("\n=== QCProtocol Roundtrip ===")

    qc = QCProtocol()
    qc.wl_criteria = {
        "WL-Q1": Criterion(id="WL-Q1", description="Test WL QC1", weight=1.5)
    }
    qc.gl_criteria = {
        "GL-Q1": Criterion(id="GL-Q1", description="Test GL QC1", weight=1.0)
    }
    qc.wl_threshold = 3.0
    qc.gl_threshold = 2.0

    d = qc.to_dict()
    restored = QCProtocol.from_dict(d)

    assert len(restored.wl_criteria) == 1
    assert len(restored.gl_criteria) == 1
    assert restored.wl_criteria["WL-Q1"].weight == 1.5
    assert restored.gl_criteria["GL-Q1"].weight == 1.0
    assert restored.wl_threshold == 3.0
    assert restored.gl_threshold == 2.0

    print("  PASS: QCProtocol serialization/deserialization works")
    return True


def test_dynamic_protocol_roundtrip():
    """Test DynamicProtocol roundtrip."""
    print("\n=== DynamicProtocol Roundtrip ===")

    protocol = create_default_protocol()
    protocol.ec.min_year = 2020
    protocol.ec.criteria['EC1'] = Criterion(id='EC1', description='Test EC1', enabled=True)
    protocol.ic.criteria['IC1'] = Criterion(id='IC1', description='Test IC1', enabled=True)
    protocol.qc.criteria['QC1'] = Criterion(id='QC1', description='Test QC1', weight=1.5)

    d = protocol.to_dict()
    restored = DynamicProtocol.from_dict(d)

    assert restored.protocol_version == "1.0"
    assert len(restored.ec.criteria) == 1
    assert len(restored.ic.criteria) == 1
    assert len(restored.qc.criteria) == 1
    assert restored.ec.min_year == 2020
    assert restored.ec.criteria['EC1'].description == "Test EC1"
    assert restored.qc.criteria['QC1'].weight == 1.5
    assert restored.state == "draft"

    print("  PASS: DynamicProtocol serialization/deserialization works")
    return True


def test_protocol_snapshot():
    """Test ProtocolSnapshot serialization."""
    print("\n=== ProtocolSnapshot ===")
    
    protocol = create_default_protocol()
    snapshot = protocol.create_snapshot("ec")
    
    d = snapshot.to_dict()
    assert "snapshot_id" in d
    assert "ec_protocol" in d
    assert "ic_protocol" in d
    assert "qc_protocol" in d
    assert isinstance(d["ec_protocol"], dict)
    
    print("  PASS: ProtocolSnapshot serialization works")
    return True


def test_file_save_load():
    """Test save/load to file."""
    print("\n=== File Save/Load ===")
    
    import os
    
    protocol = create_default_protocol()
    protocol.ec.min_year = 2018
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        temp_path = f.name
    
    try:
        protocol.save_to_file(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data["ec"]["min_year"] == 2018
        
        restored = DynamicProtocol.load_from_file(temp_path)
        assert restored.ec.min_year == 2018
        
        print("  PASS: File save/load works")
        return True
    finally:
        os.unlink(temp_path)


def test_defensive_validation():
    """Test defensive validation catches malformed data."""
    print("\n=== Defensive Validation ===")
    
    errors_caught = 0
    
    try:
        Criterion.from_dict(None)
    except TypeError:
        errors_caught += 1
    
    try:
        Criterion.from_dict("not a dict")
    except TypeError:
        errors_caught += 1
    
    try:
        Criterion.from_dict({})
    except ValueError:
        errors_caught += 1
    
    try:
        Criterion.from_dict({"id": "X"})
    except ValueError:
        errors_caught += 1
    
    try:
        ECProtocol.from_dict("not a dict")
    except TypeError:
        errors_caught += 1
    
    try:
        DynamicProtocol.from_dict(None)
    except TypeError:
        errors_caught += 1
    
    assert errors_caught == 6, f"Expected 6 errors caught, got {errors_caught}"
    
    print("  PASS: Defensive validation catches all malformed inputs")
    return True


def test_hybrid_dict_object_handling():
    """Test that hybrid dict/object structures are handled properly."""
    print("\n=== Hybrid Dict/Object Handling ===")
    
    criterion = Criterion(id="TEST", description="Test")
    ec = ECProtocol(criteria={"C1": criterion})
    
    d = ec.to_dict()
    assert isinstance(d["criteria"]["C1"], dict)
    
    restored = ECProtocol.from_dict(d)
    assert isinstance(restored.criteria["C1"], Criterion)
    
    print("  PASS: Hybrid dict/object handling works")
    return True


def test_malformed_criteria_in_protocol():
    """Test that malformed criteria in protocol are caught."""
    print("\n=== Malformed Criteria Detection ===")
    
    bad_data = {
        "criteria": {
            "C1": {"id": "C1", "description": "Valid"},
            "C2": "not a dict or Criterion"
        }
    }
    
    try:
        ECProtocol.from_dict(bad_data)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "C2" in str(e)
        print("  PASS: Malformed criteria detected and rejected")
        return True


def test_streamlit_rerun_simulation():
    """Simulate Streamlit rerun scenario."""
    print("\n=== Streamlit Rerun Simulation ===")
    
    session_protocol = None
    
    if not session_protocol:
        session_protocol = DynamicProtocol().to_dict()
    
    protocol = DynamicProtocol.from_dict(session_protocol)
    protocol.ec.criteria["NEW_EC"] = Criterion(
        id="NEW_EC", description="Added after first interaction"
    )
    session_protocol = protocol.to_dict()
    
    restored = DynamicProtocol.from_dict(session_protocol)
    assert "NEW_EC" in restored.ec.criteria
    assert restored.ec.criteria["NEW_EC"].description == "Added after first interaction"
    
    print("  PASS: Simulated Streamlit rerun preserves state")
    return True


def test_criterion_field_types():
    """Test that field types are properly handled during serialization."""
    print("\n=== Field Type Handling ===")
    
    c = Criterion(
        id="TEST",
        description="Test",
        keywords="not a list"
    )
    d = c.to_dict()
    assert d["keywords"] == "not a list"
    
    restored = Criterion.from_dict(d)
    assert restored.keywords == []
    
    c2 = Criterion(id="TEST", description="Test", weight="2.5")
    d2 = c2.to_dict()
    restored2 = Criterion.from_dict(d2)
    assert restored2.weight == 2.5
    
    print("  PASS: Field types handled correctly")
    return True


def main():
    print("=" * 60)
    print("PROTOCOL SERIALIZATION VALIDATION SUITE")
    print("=" * 60)
    
    tests = [
        ("Criterion Roundtrip", test_criterion_roundtrip),
        ("ECProtocol Roundtrip", test_ec_protocol_roundtrip),
        ("ICProtocol Roundtrip", test_ic_protocol_roundtrip),
        ("QCProtocol Roundtrip", test_qc_protocol_roundtrip),
        ("DynamicProtocol Roundtrip", test_dynamic_protocol_roundtrip),
        ("ProtocolSnapshot", test_protocol_snapshot),
        ("File Save/Load", test_file_save_load),
        ("Defensive Validation", test_defensive_validation),
        ("Hybrid Dict/Object", test_hybrid_dict_object_handling),
        ("Malformed Criteria", test_malformed_criteria_in_protocol),
        ("Streamlit Rerun", test_streamlit_rerun_simulation),
        ("Field Type Handling", test_criterion_field_types),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, traceback.format_exc()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed, error in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed and error:
            print(f"    {error[:200]}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("ALL TESTS PASSED - Serialization validation complete")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
