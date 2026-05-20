"""
APOLLO Styles - Clean Academic Research Platform

Modern, professional, and visually quiet interface for systematic literature review.
"""
from src.ui.theme import COLORS, TYPOGRAPHY

# DEBUG MODE - Set to True to show verbose operational diagnostics
# When False (production), hides: raw LLM responses, normalization dumps, queue internals
APOLLO_DEBUG = False

# VERBOSE LOGGING - Set to True to see all CACHE HIT, LOOKUP, REUSE messages
# When False (production), only shows: failures, completions, state transitions
APOLLO_DEBUG_VERBOSE = False

# LOG LEVEL - Controls verbosity: DEBUG, INFO, WARNING, ERROR
# Default: INFO (shows important state transitions, warnings, errors)
APOLLO_LOG_LEVEL = "INFO"

# DEBUG MODE - Set to True to outline sidebar containers for visual validation
SIDEBAR_DEBUG = False


def should_log(level: str) -> bool:
    """Check if message at given level should be logged based on APOLLO_LOG_LEVEL."""
    levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    current = levels.get(APOLLO_LOG_LEVEL.upper(), 1)
    msg_level = levels.get(level.upper(), 1)
    return msg_level >= current


def get_custom_css():
    debug_outline = ""
    if SIDEBAR_DEBUG:
        debug_outline = """/* DEBUG: Outline sidebar containers */
[data-testid="stSidebar"] * {{ outline: 1px dashed red !important; }}
[data-testid="stSidebar"] [data-testid="stRadio"] {{ outline: 2px solid yellow !important; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ outline: 2px solid cyan !important; }}
[data-testid="stSidebar"] label {{ outline: 1px solid green !important; }}
"""

    return f"""<style>
{debug_outline}

/* ================================================================================
   SPACING SYSTEM - 4px base unit, consistent rhythm
   ================================================================================ */
:root {{
    /* Spacing Scale */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-6: 24px;
    --space-8: 32px;

    /* Colors */
    --bg-deep: {COLORS['bg_deep']};
    --bg-surface: {COLORS['bg_surface']};
    --bg-elevated: {COLORS['bg_elevated']};
    --bg-card: {COLORS['bg_card']};
    --border: {COLORS['border']};
    --border-light: {COLORS['border_light']};
    --border-accent: {COLORS['border_accent']};
    --text-primary: {COLORS['text_primary']};
    --text-secondary: {COLORS['text_secondary']};
    --text-muted: {COLORS['text_muted']};
    --cyan: {COLORS['cyan']};
    --cyan-dim: {COLORS['cyan_dim']};
    --cyan-subtle: {COLORS['cyan_subtle']};
    --cyan-border: {COLORS['cyan_border']};
    --success: {COLORS['success']};
    --warning: {COLORS['warning']};
    --error: {COLORS['error']};

    /* Layout */
    --sidebar-width: 220px;
    --content-max-width: 1200px;
    --card-radius: 8px;
    --button-radius: 6px;
}}

/* ================================================================================
   BASE RESET
   ================================================================================ */
html, body, .stApp {{
    background: var(--bg-deep) !important;
    color: var(--text-primary) !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
}}

* {{
    color: var(--text-primary) !important;
}}

[data-testid="stAppViewContainer"] {{
    background: var(--bg-deep) !important;
}}

/* ================================================================================
   CONTENT CONTAINER - Centered, max-width for readability
   ================================================================================ */
[data-testid="stMain"] {{
    max-width: var(--content-max-width) !important;
    margin: 0 auto !important;
    padding: var(--space-6) var(--space-8) !important;
}}

/* Fix main block to respect container */
[data-testid="stMain"] > div {{
    max-width: 100% !important;
}}

/* ================================================================================
   SIDEBAR - Fixed compact width, secondary visual hierarchy
   ================================================================================ */
[data-testid="stSidebar"] {{
    background: {COLORS['bg_surface']} !important;
    border-right: 1px solid {COLORS['border']} !important;
    width: var(--sidebar-width) !important;
    min-width: var(--sidebar-width) !important;
    max-width: var(--sidebar-width) !important;
}}

@media (max-width: 1200px) {{
    [data-testid="stSidebar"] {{
        width: 200px !important;
        min-width: 200px !important;
        max-width: 200px !important;
    }}
}}

[data-testid="stSidebar"]::before {{
    content: "APOLLO";
    display: block;
    font-family: {TYPOGRAPHY['sans']};
    font-size: 1rem;
    font-weight: 600;
    color: {COLORS['cyan']};
    letter-spacing: 0.05em;
    padding: var(--space-4) var(--space-4);
    border-bottom: 1px solid {COLORS['border_light']};
    margin-bottom: var(--space-3);
}}

/* ================================================================================
   TYPOGRAPHY - Clean sans-serif, minimal monospace
   ================================================================================ */
h1, h2, h3, h4, h5, h6 {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    letter-spacing: -0.01em !important;
    margin: 0 0 var(--space-4) 0 !important;
}}

h1 {{ font-size: 1.5rem !important; font-weight: 700 !important; }}
h2 {{ font-size: 1.25rem !important; }}
h3 {{ font-size: 1rem !important; }}
h4 {{ font-size: 0.875rem !important; }}

/* ================================================================================
   BUTTONS - Action button groups
   ================================================================================ */
.stButton > button {{
    background: {COLORS['bg_elevated']} !important;
    color: var(--text-primary) !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: var(--button-radius) !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    padding: var(--space-2) var(--space-4) !important;
    transition: all 0.2s !important;
}}

.stButton > button:hover {{
    border-color: {COLORS['cyan']} !important;
    background: {COLORS['bg_card']} !important;
}}

.stButton > button[type="primary"] {{
    background: {COLORS['cyan']} !important;
    color: {COLORS['bg_deep']} !important;
    border-color: {COLORS['cyan']} !important;
    font-weight: 600 !important;
}}

.stButton > button[type="primary"]:hover {{
    background: {COLORS['cyan_bright']} !important;
}}

.stButton > button[kind="secondary"] {{
    background: transparent !important;
    border: 1px solid {COLORS['border_light']} !important;
    color: var(--text-secondary) !important;
}}

/* Button groups - horizontal layout with equal spacing */
div[data-testid="stHorizontalBlock"] {{
    gap: var(--space-2) !important;
}}

div[data-testid="stHorizontalBlock"] > div {{
    gap: var(--space-2) !important;
}}

/* Action button groups: Include / Exclude / Pending */
div[class*="stButton"]:has(button) {{
    display: inline-flex !important;
}}

/* ================================================================================
   FORM INPUTS
   ================================================================================ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: var(--button-radius) !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.875rem !important;
}}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {COLORS['cyan']} !important;
    box-shadow: 0 0 0 1px {COLORS['cyan']} !important;
}}

/* ================================================================================
   ALERTS & TOASTS
   ================================================================================ */
.stSuccess, .stInfo, .stWarning, .stError {{
    border-radius: var(--button-radius) !important;
    padding: var(--space-3) var(--space-4) !important;
    border: 1px solid !important;
}}

.stSuccess {{
    background: rgba(0, 214, 126, 0.1) !important;
    border-color: {COLORS['success']} !important;
    color: {COLORS['success']} !important;
}}

.stWarning {{
    background: rgba(255, 176, 32, 0.1) !important;
    border-color: {COLORS['warning']} !important;
    color: {COLORS['warning']} !important;
}}

.stError {{
    background: rgba(255, 71, 87, 0.1) !important;
    border-color: {COLORS['error']} !important;
    color: {COLORS['error']} !important;
}}

.stInfo {{
    background: {COLORS['cyan_subtle']} !important;
    border-color: {COLORS['cyan_border']} !important;
    color: {COLORS['cyan']} !important;
}}

/* ================================================================================
   PROGRESS & TABS - Clean modern style
   ================================================================================ */
.stProgress > div > div > div {{
    background: {COLORS['cyan']} !important;
    border-radius: 2px !important;
}}

.stTabs [data-baseweb="tab-list"] {{
    border-bottom: 1px solid {COLORS['border']} !important;
    background: transparent !important;
    gap: var(--space-4) !important;
}}

.stTabs [data-baseweb="tab"] {{
    color: var(--text-secondary) !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.875rem !important;
    padding: var(--space-2) var(--space-3) !important;
}}

.stTabs [aria-selected="true"] {{
    color: {COLORS['cyan']} !important;
    border-bottom: 2px solid {COLORS['cyan']} !important;
}}

/* ================================================================================
   SCROLLBARS
   ================================================================================ */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg-deep); }}
::-webkit-scrollbar-thumb {{ background: var(--border-light); }}
::-webkit-scrollbar-thumb:hover {{ background: {COLORS['border']}; }}

/* ================================================================================
   METRICS - Clean card style
   ================================================================================ */
[data-testid="stMetric"] {{
    background: {COLORS['bg_card']} !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: var(--button-radius) !important;
    padding: var(--space-3) !important;
}}

[data-testid="stMetricLabel"] {{
    color: {COLORS['text_muted']} !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.75rem !important;
}}

[data-testid="stMetricValue"] {{
    color: var(--text-primary) !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 1.25rem !important;
    font-weight: 600 !important;
}}

/* ================================================================================
   FORM ELEMENTS
   ================================================================================ */
[data-testid="stSelectbox"] > div > div {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border_light']} !important;
}}

/* ================================================================================
   EXPANDERS - Custom styling
   ================================================================================ */
.stExpander {{
    border: 1px solid {COLORS['border']} !important;
    border-radius: var(--card-radius) !important;
    background: {COLORS['bg_card']} !important;
    margin-bottom: var(--space-4) !important;
}}

.stExpander > div:first-child {{
    background: {COLORS['bg_elevated']} !important;
    border-bottom: 1px solid {COLORS['border']} !important;
    padding: var(--space-3) var(--space-4) !important;
}}

.stExpander > div:first-child > div {{
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: {COLORS['text_secondary']} !important;
}}

.stExpander > div:last-child {{
    padding: var(--space-4) !important;
}}

/* ================================================================================
   DATA FRAME / TABLE
   ================================================================================ */
.stDataFrame {{
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: var(--button-radius) !important;
}}

.stDataFrame [data-testid="stTable"] {{
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.75rem !important;
}}

/* ================================================================================
   NAVIGATION - Sidebar navigation items (full width flex layout)
   ================================================================================ */
section[data-testid="stSidebar"] [data-testid="stRadio"] > div,
section[data-testid="stSidebar"] [data-testid="stRadio"] > div > div,
section[data-testid="stSidebar"] div[class*="stElementContainer"] {{
    width: 100% !important;
    max-width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}}

section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    width: 100% !important;
    min-width: 100% !important;
    box-sizing: border-box !important;
    padding: var(--space-3) var(--space-4) !important;
    margin-bottom: var(--space-2) !important;
    border-radius: var(--button-radius) !important;
    background: {COLORS['bg_card']} !important;
    border: 1px solid transparent !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
    color: {COLORS['text_secondary']} !important;
    text-align: left !important;
    transition: all 0.15s ease !important;
    min-height: 36px !important;
}}

section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
    background: {COLORS['bg_elevated']} !important;
    border-color: {COLORS['border_light']} !important;
    color: {COLORS['text_primary']} !important;
}}

section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
    border: 1px solid {COLORS['cyan']} !important;
    color: {COLORS['cyan']} !important;
    background: {COLORS['cyan_subtle']} !important;
}}

section[data-testid="stSidebar"] [data-testid="stRadio"] {{
    display: flex !important;
    flex-direction: column !important;
    gap: var(--space-1) !important;
    width: 100% !important;
    max-width: 100% !important;
}}

/* General radio fallback */
[data-testid="stRadio"] > div {{
    gap: var(--space-2) !important;
    display: flex !important;
    flex-direction: column !important;
}}

[data-testid="stRadio"] label {{
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: {COLORS['text_secondary']} !important;
    padding: var(--space-2) var(--space-3) !important;
    background: {COLORS['bg_card']} !important;
    border-radius: var(--button-radius) !important;
    width: 100% !important;
    flex: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
}}

[data-testid="stRadio"] label:has(input:checked) {{
    border-color: {COLORS['cyan']} !important;
    color: {COLORS['cyan']} !important;
    background: {COLORS['cyan_subtle']} !important;
}}

/* ================================================================================
   FILE UPLOADER
   ================================================================================ */
div[data-testid="stFileUploader"] {{
    border: 1px dashed {COLORS['border_light']} !important;
    border-radius: var(--card-radius) !important;
    padding: var(--space-4) !important;
    background: {COLORS['bg_elevated']} !important;
}}

div[data-testid="stFileUploader"] label {{
    font-family: {TYPOGRAPHY['mono']} !important;
    color: {COLORS['text_muted']} !important;
}}

/* ================================================================================
   SLIDER
   ================================================================================ */
.stSlider [data-baseweb="slider"] {{
    background: {COLORS['border']} !important;
}}

.stSlider [data-baseweb="slider"] > div > div {{
    background: {COLORS['cyan']} !important;
}}

/* ================================================================================
   TOAST NOTIFICATIONS
   ================================================================================ */
div[data-testid="stToast"] {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: var(--button-radius) !important;
    padding: var(--space-3) var(--space-4) !important;
}}

/* ================================================================================
   CODE & PRE
   ================================================================================ */
code {{
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.8rem !important;
    background: {COLORS['bg_surface']} !important;
    border: 1px solid {COLORS['border']} !important;
    padding: var(--space-1) var(--space-2) !important;
    border-radius: var(--button-radius) !important;
}}

pre {{
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.75rem !important;
    background: {COLORS['bg_surface']} !important;
    border: 1px solid {COLORS['border']} !important;
    border-radius: var(--button-radius) !important;
    padding: var(--space-4) !important;
}}

/* ================================================================================
   MARKDOWN
   ================================================================================ */
div[data-testid="stMarkdownContainer"] p {{
    font-size: 0.875rem !important;
    color: {COLORS['text_secondary']} !important;
    line-height: 1.6 !important;
}}

/* ================================================================================
   SECTION SPACING - Consistent vertical rhythm
   ================================================================================ */
section[data-testid="stVerticalBlock"] {{
    gap: var(--space-6) !important;
}}

section[data-testid="stVerticalBlock"] > div {{
    gap: var(--space-4) !important;
}}

/* ================================================================================
   CONTAINER BORDERS - Remove raw Streamlit look
   ================================================================================ */
div[data-testid="stContainer"] {{
    border: none !important;
    background: transparent !important;
}}

/* Custom container wrapper for content sections */
.apollo-content-container {{
    max-width: var(--content-max-width);
    margin: 0 auto;
    padding: var(--space-4);
}}

/* ================================================================================
   CARD IMPROVEMENTS - Better structure for article cards
   ================================================================================ */
.apollo-card {{
    border: 1px solid {COLORS['border_light']};
    background: {COLORS['bg_card']};
    border-radius: var(--card-radius);
    padding: var(--space-4);
    margin-bottom: var(--space-4);
}}

.apollo-card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-3);
    margin-bottom: var(--space-3);
    border-bottom: 1px solid {COLORS['border']};
}}

.apollo-card-body {{
    padding: var(--space-3) 0;
}}

.apollo-card-footer {{
    padding-top: var(--space-3);
    margin-top: var(--space-3);
    border-top: 1px solid {COLORS['border']};
}}

/* ================================================================================
   METADATA INLINE - Muted, compact display
   ================================================================================ */
.apollo-metadata-inline {{
    font-family: {TYPOGRAPHY['mono']};
    font-size: 0.75rem;
    color: {COLORS['text_muted']};
    display: inline;
}}

.apollo-metadata-inline span {{
    color: {COLORS['text_secondary']};
}}

.apollo-metadata-inline .separator {{
    margin: 0 var(--space-2);
    color: {COLORS['border']};
}}

/* ================================================================================
   ACTION BUTTON GROUP - Horizontal with equal heights
   ================================================================================ */
.apollo-action-group {{
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
}}

.apollo-action-group .stButton {{
    flex: 1;
    min-width: 0;
}}

.apollo-action-group button {{
    width: 100%;
    height: 100%;
    min-height: 36px;
}}

/* ================================================================================
   REMOVE STREAMLIT STACKED WIDGET FEEL
   ================================================================================ */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}}

div[data-testid="stVerticalBlockBorderWrapper"]:has(div) {{
    border: 1px solid {COLORS['border_light']} !important;
    background: {COLORS['bg_card']} !important;
    border-radius: var(--card-radius) !important;
    padding: var(--space-4) !important;
}}

/* Fix for columns within containers */
div[data-testid="stHorizontalBlock"] {{
    gap: var(--space-4) !important;
}}
</style>"""