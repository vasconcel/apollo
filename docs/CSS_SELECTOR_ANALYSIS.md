# CSS Selector Analysis

**APOLLO v2.0.0 Primal - Streamlit DOM Targets**

---

## Executive Summary

Analysis of actual Streamlit DOM structure and corresponding CSS selectors used to style APOLLO interface elements.

---

## Streamlit Radio Navigation

### Real DOM Structure
```html
<div data-testid="stRadio">
    <div>  <!-- flex container -->
        <label>  <!-- each radio option -->
            <span>...</span>
        </label>
        <label>...</label>
        <label>...</label>
    </div>
</div>
```

### CSS Selectors Used

| Selector | Purpose | Applied To |
|----------|---------|-------------|
| `[data-testid="stRadio"]` | Container targeting | Radio widget wrapper |
| `[data-testid="stRadio"] > div` | Flex layout control | Inner container |
| `[data-testid="stRadio"] label` | Option styling | Each navigation item |
| `[data-testid="stRadio"] label:has(input:checked)` | Active state | Selected item |

### Implementation
```css
[data-testid="stRadio"] > div {
    gap: 0.5rem !important;
    display: flex !important;
    flex-direction: column !important;
}

[data-testid="stRadio"] label {
    width: 100% !important;
    flex: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
}
```

### Why These Selectors
- Streamlit renders radio buttons with `data-testid="stRadio"` attribute
- Labels inside contain the visible text for each option
- `:has()` pseudo-class targets selected state

---

## Streamlit Metrics

### Real DOM Structure
```html
<div data-testid="stMetric">
    <div class="stMetricLabel">Label</div>
    <div class="stMetricValue">Value</div>
    <div class="stMetricDelta">Delta</div>
</div>
```

### CSS Selectors Used

| Selector | Purpose |
|----------|---------|
| `st.metric()` | Streamlit primitive - no CSS needed |
| `[data-testid="stMetric"]` | Direct metric targeting if needed |

### Implementation
```python
st.metric("Identification", ec_total, "articles from search")
```

---

## Streamlit Columns

### Real DOM Structure
```html
div[data-testid="stHorizontalBlock"]
    > div[data-testid="stColumn"]
```

### CSS Selectors Used
- `st.columns([2, 0.3, 2])` - creates horizontal blocks
- Each column gets `data-testid="stColumn"`

### Implementation
```python
c1, c2, c3 = st.columns([2, 0.3, 2])
with c1:
    st.metric("Label", value)
```

---

## Streamlit Expanders

### Real DOM Structure
```html
div[data-testid="stExpander"]
    > details
        > summary  <!-- Collapsible header -->
        > div      <!-- Content -->
```

### CSS Selectors Used

| Selector | Purpose |
|----------|---------|
| `st.expander()` | Streamlit primitive |
| `[data-testid="stExpander"]` | Direct targeting if needed |

### Implementation
```python
with st.expander("Metadata & Provenance", expanded=False):
    # content
```

---

## Streamlit Containers

### Real DOM Structure
```html
div[data-testid="stVerticalBlock"]
```

### CSS Selectors Used

| Selector | Purpose |
|----------|---------|
| `st.container(border=True)` | Bordered container |
| `[data-testid="stContainerBorder"]` | Border wrapper |

---

## Workflow Stepper Component

### Custom CSS (Not Streamlit-native)
The workflow stepper uses custom HTML with CSS injection via `st.markdown()`:

```python
st.markdown("""
<style>
.workflow-stepper { ... }
.workflow-step { ... }
.workflow-step.active { ... }
.workflow-connector { ... }
</style>
""", unsafe_allow_html=True)
```

### Selectors

| Selector | Purpose |
|----------|---------|
| `.workflow-stepper` | Container for all steps |
| `.workflow-step` | Individual step block |
| `.workflow-step.active` | Currently active stage |
| `.workflow-step.completed` | Completed stages |
| `.workflow-step.future` | Future stages |
| `.workflow-connector` | Arrow between steps |

---

## Navigation Radio Equal-Width Fix

### Previous (Broken)
```css
/* These didn't enforce equal width */
.workflow-step {
    flex: 1;
    min-width: 100px;
}
```

### Current (Fixed)
```css
/* Applied to actual Streamlit DOM */
[data-testid="stRadio"] label {
    width: 100% !important;
    flex: 1 !important;
    display: flex !important;
    justify-content: center !important;
    text-align: center !important;
}
```

### Why This Works
1. Targets real Streamlit rendered element (`data-testid="stRadio"`)
2. Forces each label to take 100% width
3. Uses flex to distribute equally
4. `!important` ensures override of Streamlit defaults

---

## Selector Validation

All selectors tested and verified:
- ✅ `[data-testid="stRadio"]` - Navigation equal-width
- ✅ `[data-testid="stMetric"]` - Metrics in export
- ✅ `[data-testid="stColumn"]` - Column layouts
- ✅ `[data-testid="stExpander"]` - Expandable sections

---

## Conclusion

Streamlit's DOM structure uses `data-testid` attributes for identification. Key selectors:

1. **Navigation**: `[data-testid="stRadio"] label`
2. **Metrics**: `st.metric()` primitive (no selector needed)
3. **Columns**: `st.columns()` primitive (no selector needed)
4. **Expanders**: `st.expander()` primitive (no selector needed)

All UI fixes use proper Streamlit-native primitives where possible, with CSS only for layout control where primitives aren't sufficient.