# Sidebar DOM Forensics

## Issue
Navigation radio buttons in sidebar do NOT occupy full available width.

## Streamlit DOM Structure Analysis

The Streamlit radio component has this hierarchy:
```
section[data-testid="stSidebar"]
  → div (content wrapper)
    → div[class*="stElementContainer"]
      → div[data-testid="stRadio"]
        → div (wrapper)
          → div (inner wrapper)
            → div[data-baseweb="radio"]
              → div (BaseWeb container)
                → div (radio group container)
                  → role="radiogroup"
                    → label[data-baseweb="radio"]
```

## Hypotheses Tested

### Hypothesis 1: Label width constraint
- **Fix applied**: Set `width: 100% !important` on labels
- **Status**: Not sufficient - labels are not the constraint

### Hypothesis 2: Parent container width
- **Fix applied**: Set `width: 100% !important` on parent divs
- **Status**: Partial - helps but may not be sufficient

### Hypothesis 3: BaseWeb radio internal width
- **Fix applied**: Added targeting for `[data-baseweb="radio"]` and `[role="radiogroup"]`
- **Status**: More aggressive targeting applied

### Hypothesis 4: Streamlit inline styles override
- **Analysis**: Streamlit uses BaseWeb components with internal styling that may override user CSS
- **Status**: May need `!important` on more properties or different selectors

## Enhanced CSS Applied

```css
/* Target radiogroup specifically */
section[data-testid="stSidebar"] [role="radiogroup"] {
    width: 100% !important;
    max-width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 0.4rem !important;
}

/* Target BaseWeb radio container */
section[data-testid="stSidebar"] [data-baseweb="radio"] {
    width: 100% !important;
    max-width: 100% !important;
}

/* Target inner divs */
section[data-testid="stSidebar"] [data-testid="stRadio"] > div > div > div {
    width: 100% !important;
    max-width: 100% !important;
}
```

## Unresolved Issues

1. **Streamlit may reset width** on re-render
2. **BaseWeb internal CSS** may take precedence
3. **Inline styles** may override external CSS
4. **Cannot test without runtime** - CSS changes require actual Streamlit app to verify

## Validation Required

User must verify in runtime:
1. Navigation buttons now fill sidebar width
2. Visual alignment with content area panels
3. No text clipping or truncation

## Risk Assessment

- **High uncertainty**: CSS fixes in Streamlit are fragile
- **May need config change**: Streamlit may need `.streamlit/config.toml` adjustment for sidebar width
- **Alternative**: Use native Streamlit `st.radio()` with `horizontal=True` instead of custom styling