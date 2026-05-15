"""
APOLLO Styles - Forensic Terminal / Industrial Research Aesthetic

Dark monochromatic interface with cyan accents for systematic evidence analysis.
"""
from src.ui.theme import COLORS, TYPOGRAPHY

# DEBUG MODE - Set to True to outline sidebar containers for visual validation
SIDEBAR_DEBUG = False


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
@keyframes blink {{
    0%, 50% {{ opacity: 1; }}
    51%, 100% {{ opacity: 0; }}
}}

@keyframes scanline {{
    0% {{ transform: translateY(-100%); }}
    100% {{ transform: translateY(100vh); }}
}}

@keyframes grid-pulse {{
    0%, 100% {{ opacity: 0.03; }}
    50% {{ opacity: 0.06; }}
}}

:root {{
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
}}

html, body, .stApp {{
    background: var(--bg-deep) !important;
    color: var(--text-primary) !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}}

* {{
    color: var(--text-primary) !important;
}}

[data-testid="stAppViewContainer"] {{
    background: var(--bg-deep) !important;
    position: relative;
}}

[data-testid="stAppViewContainer"]::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image: 
        linear-gradient(var(--border) 1px, transparent 1px),
        linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    opacity: 0.15;
    pointer-events: none;
    z-index: 0;
}}

[data-testid="stAppViewContainer"]::after {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
    opacity: 0.3;
    animation: scanline 8s linear infinite;
    pointer-events: none;
    z-index: 9999;
}}

[data-testid="stSidebar"] {{
    background: {COLORS['bg_surface']} !important;
    border-right: 1px solid {COLORS['border']} !important;
    width: 300px !important;
    min-width: 300px !important;
}}

@media (max-width: 1200px) {{
    [data-testid="stSidebar"] {{
        width: 260px !important;
        min-width: 260px !important;
    }}
}}

[data-testid="stSidebar"]::before {{
    content: "APOLLO";
    display: block;
    font-family: {TYPOGRAPHY['sans']};
    font-size: 1.1rem;
    font-weight: 600;
    color: {COLORS['cyan']};
    letter-spacing: 0.05em;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid {COLORS['border_light']};
    margin-bottom: 0.5rem;
}}

h1, h2, h3, h4, h5, h6 {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    letter-spacing: -0.01em !important;
    margin: 0 0 0.5rem 0 !important;
}}

h1 {{ font-size: 1.5rem !important; font-family: {TYPOGRAPHY['mono']} !important; letter-spacing: 0.1em !important; }}
h2 {{ font-size: 1.25rem !important; font-family: {TYPOGRAPHY['mono']} !important; }}
h3 {{ font-size: 1rem !important; font-family: {TYPOGRAPHY['mono']} !important; }}
h4 {{ font-size: 0.875rem !important; }}

.stButton > button {{
    background: {COLORS['bg_elevated']} !important;
    color: var(--text-primary) !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: 0px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    font-family: {TYPOGRAPHY['mono']} !important;
    padding: 0.5rem 1rem !important;
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

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: 0px !important;
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.8rem !important;
}}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {COLORS['cyan']} !important;
    box-shadow: 0 0 0 1px {COLORS['cyan']} !important;
}}

.stSuccess, .stInfo, .stWarning, .stError {{
    border-radius: 0px !important;
    padding: 0.75rem 1rem !important;
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

.stProgress > div > div > div {{
    background: {COLORS['cyan']} !important;
    border-radius: 0px !important;
}}

.stTabs [data-baseweb="tab-list"] {{
    border-bottom: 1px solid {COLORS['border']} !important;
    background: transparent !important;
}}

.stTabs [data-baseweb="tab"] {{
    color: var(--text-secondary) !important;
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.1em !important;
}}

.stTabs [aria-selected="true"] {{
    color: {COLORS['cyan']} !important;
    border-bottom: 2px solid {COLORS['cyan']} !important;
}}

::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg-deep); }}
::-webkit-scrollbar-thumb {{ background: var(--border-light); }}

[data-testid="stMetric"] {{
    background: {COLORS['bg_card']} !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: 0px !important;
    padding: 0.75rem !important;
}}

[data-testid="stMetricLabel"] {{
    color: {COLORS['text_muted']} !important;
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.6rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}}

[data-testid="stMetricValue"] {{
    color: var(--text-primary) !important;
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 1.1rem !important;
}}

[data-testid="stSelectbox"] > div > div {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border_light']} !important;
}}

.stExpander {{
    border: 1px solid {COLORS['border']} !important;
    border-radius: 0px !important;
    background: {COLORS['bg_card']} !important;
}}

.stExpander > div:first-child {{
    background: {COLORS['bg_elevated']} !important;
    border-bottom: 1px solid {COLORS['border']} !important;
}}

.stDataFrame {{
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: 0px !important;
}}

.stDataFrame [data-testid="stTable"] {{
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.75rem !important;
}}

/* Navigation radio in sidebar - full width - targeting correct elements */
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
    padding: 0.55rem 0.75rem !important;
    margin-bottom: 0.35rem !important;
    border-radius: 6px !important;
    background: {COLORS['bg_card']} !important;
    border: 1px solid transparent !important;
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
    color: {COLORS['text_secondary']} !important;
    text-align: left !important;
    transition: all 0.15s ease !important;
}}
    min-height: 38px !important;
    transition: background 0.2s ease !important;
}}

section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
    border: 2px solid {COLORS['cyan']} !important;
    color: {COLORS['cyan']} !important;
    background: {COLORS['cyan_subtle']} !important;
}}

section[data-testid="stSidebar"] [data-testid="stRadio"] {{
    display: flex !important;
    flex-direction: column !important;
    gap: 0.4rem !important;
    width: 100% !important;
    max-width: 100% !important;
}}

/* General radio fallback */
[data-testid="stRadio"] > div {{
    gap: 0.5rem !important;
    display: flex !important;
    flex-direction: column !important;
}}

[data-testid="stRadio"] label {{
    font-family: {TYPOGRAPHY['sans']} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: {COLORS['text_secondary']} !important;
    padding: 0.5rem 0.75rem !important;
    background: {COLORS['bg_card']} !important;
    border-radius: 4px !important;
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

div[data-testid="stFileUploader"] {{
    border: 1px dashed {COLORS['border_light']} !important;
    border-radius: 0px !important;
    padding: 1rem !important;
}}

div[data-testid="stFileUploader"] label {{
    font-family: {TYPOGRAPHY['mono']} !important;
    color: {COLORS['text_muted']} !important;
}}

.stSlider [data-baseweb="slider"] {{
    background: {COLORS['border']} !important;
}}

.stSlider [data-baseweb="slider"] > div > div {{
    background: {COLORS['cyan']} !important;
}}

div[data-testid="stToast"] {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border_light']} !important;
    border-radius: 0px !important;
}}

code {{
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.8rem !important;
    background: {COLORS['bg_surface']} !important;
    border: 1px solid {COLORS['border']} !important;
    padding: 0.1rem 0.3rem !important;
    border-radius: 0px !important;
}}

pre {{
    font-family: {TYPOGRAPHY['mono']} !important;
    font-size: 0.75rem !important;
    background: {COLORS['bg_surface']} !important;
    border: 1px solid {COLORS['border']} !important;
    border-radius: 0px !important;
    padding: 1rem !important;
}}

div[data-testid="stMarkdownContainer"] p {{
    font-size: 0.875rem !important;
    color: {COLORS['text_secondary']} !important;
}}
</style>"""