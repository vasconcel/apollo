# Sidebar Runtime Validation - DOM Forensics

## Visual Debug Mode Added

```python
# In styles.py
SIDEBAR_DEBUG = False  # Set to True to enable
```

When enabled, adds CSS outlines:
- `[data-testid="stSidebar"] *` → red dashed outline
- `[data-testid="stRadio"]` → yellow solid outline
- `[role="radiogroup"]` → cyan solid outline
- Labels → green solid outline

## Enhanced CSS Selectors

Added targeting for:
1. BaseWeb radio container: `[data-baseweb="radio"]`
2. Radio group role: `[role="radiogroup"]`
3. Inner wrapper divs: `[data-testid="stRadio"] > div > div > div`
4. Max-width enforcement on all containers

## DOM Hierarchy Analysis

```
section[data-testid="stSidebar"]
  └─ div (content wrapper)
      └─ div[class*="stElementContainer"]
          └─ div[data-testid="stRadio"]
              └─ div (wrapper)
                  └─ div (inner wrapper)
                      └─ div[data-baseweb="radio"]
                          └─ div (BaseWeb container)
                              └─ div (radiogroup container)
                                  └─ role="radiogroup"
                                      └─ label[data-baseweb="radio"]
```

## Potential Constraints Identified

| Potential Constraint | CSS Applied | Status |
|---------------------|-------------|--------|
| Label width | `width: 100%` | ✅ Applied |
| Container width | `width: 100%; max-width: 100%` | ✅ Applied |
| BaseWeb internal | `[data-baseweb="radio"]` targeting | ✅ Applied |
| radiogroup role | `[role="radiogroup"]` targeting | ✅ Applied |
| Streamlit inline | None (cannot override) | ⚠️ May fail |
| BaseWeb CSS | None (component internal) | ⚠️ May fail |

## Validation Required

User must:
1. Set `SIDEBAR_DEBUG = True` in styles.py
2. Run Streamlit app
3. Inspect sidebar - verify outlines visible
4. Check:
   - Are labels full width? (green outline should span sidebar)
   - Is radiogroup full width? (cyan outline)
   - Any clipping or overflow?

## If CSS Still Fails

Alternative approaches:
1. **Use Streamlit native buttons** - Replace radio with `st.segmented_control()`
2. **Horizontal layout** - Use `horizontal=True` in st.radio()
3. **Config adjustment** - Modify Streamlit config for wider sidebar

## Code Change vs Runtime Validation

| Item | Code Change | Runtime Validation |
|------|-------------|-------------------|
| CSS selectors | ✅ Enhanced | ❌ Pending |
| Debug mode | ✅ Added | ❌ Pending |
| BaseWeb targeting | ✅ Added | ❌ Pending |
| Streamlit config | ❌ Not done | ❌ N/A |

## Streamlit Config Option

If CSS fails, add to `.streamlit/config.toml`:
```toml
[runner]
fastReruns = false

[layout]
wideMode = true
```

Or increase sidebar width:
```toml
[server]
headless = true
```

Note: Streamlit's sidebar width is not directly configurable via config.