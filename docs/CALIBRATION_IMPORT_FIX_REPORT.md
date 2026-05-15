# Calibration Import Fix Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem Statement

Runtime error when accessing Calibration workspace:
```
ImportError: cannot import name 'render_calibration_workspace'
from 'src.ui.modules.calibration_view'
```

## Root Cause

**Naming Mismatch:**
- `app.py` imports: `render_calibration_workspace`
- `calibration_view.py` defines: `render_calibration_view`

The module defines `render_calibration_view()` but app.py tries to import `render_calibration_workspace()`.

## Fix Implementation

**File:** `src/ui/modules/calibration_view.py`

### 1. Rename Main Function

**Before:**
```python
def render_calibration_view():
    """Main Calibration Dashboard."""
```

**After:**
```python
def render_calibration_workspace():
    """Main Calibration Dashboard."""
```

### 2. Update Wrapper

**Before:**
```python
def render():
    """Wrapper for routing."""
    render_calibration_view()
```

**After:**
```python
def render():
    """Wrapper for routing."""
    render_calibration_workspace()
```

## Validation

- [x] ImportError resolved
- [x] Calibration workspace renders
- [x] No crashes on navigation to calibration
- [x] Two-file upload flow works

## Constraint Compliance

- ✅ Calibration methodology unchanged
- ✅ Determinism unchanged
- ✅ IRR calculation logic unchanged
- ✅ Export behavior unchanged