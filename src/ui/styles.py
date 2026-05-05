"""Professional CSS styles for AIMS - Slate & Azure Design System"""

def get_custom_css():
    return """<style>
:root {
    --bg-deep: #0B0F1A;
    --bg-card: #161B22;
    --border: #30363D;
    --primary: #2563EB;
    --primary-hover: #1D4ED8;
    --text-primary: #F0F6FC;
    --text-secondary: #8B949E;
    --text-muted: #6E7681;
    --success: #238636;
    --warning: #9E6A03;
    --error: #DA3633;
    --accent: #2563EB;
}

* { box-sizing: border-box; }

html, body, .stApp {
    background: var(--bg-deep) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
}

/* Background layers */
[data-testid="stAppViewContainer"] {
    background: var(--bg-deep) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0D1117 !important;
    border-right: 1px solid var(--border) !important;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    margin: 0 0 0.5rem 0 !important;
}

h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1rem !important; }
h4 { font-size: 0.875rem !important; }

/* Cards */
.ais-card, [data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 0.75rem !important;
}

.ais-card {
    margin-bottom: 0.5rem !important;
}

/* Metric styling */
[data-testid="stMetric"] {
    padding: 0.5rem 0.75rem !important;
}

[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 1.5rem !important;
    font-weight: 600 !important;
}

/* Buttons */
.stButton > button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.5rem 1rem !important;
    transition: background 0.15s ease !important;
}

.stButton > button:hover {
    background: var(--primary-hover) !important;
}

.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}

.stButton > button[kind="secondary"]:hover {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
[data-baseweb="input"] {
    background: var(--bg-deep) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--text-primary) !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary) !important;
    outline: none !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
}

.streamlit-expanderHeader:hover {
    background: var(--bg-deep) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border-radius: 4px 4px 0 0 !important;
    padding: 0.5rem 1rem !important;
    font-size: 0.875rem !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-primary) !important;
}

.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    background: transparent !important;
    border-bottom: 2px solid var(--primary) !important;
}

/* Dataframes */
.stDataFrame {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

/* Dividers */
hr, .stDivider {
    border: none !important;
    height: 1px !important;
    background: var(--border) !important;
    margin: 1rem 0 !important;
}

/* Messages */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 6px !important;
    border-left: 3px solid !important;
    padding: 0.75rem 1rem !important;
}

.stSuccess {
    background: rgba(35, 134, 54, 0.15) !important;
    border-left-color: var(--success) !important;
}

.stWarning {
    background: rgba(158, 106, 3, 0.15) !important;
    border-left-color: var(--warning) !important;
}

.stError {
    background: rgba(218, 54, 51, 0.15) !important;
    border-left-color: var(--error) !important;
}

.stInfo {
    background: rgba(37, 99, 235, 0.15) !important;
    border-left-color: var(--primary) !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background: var(--primary) !important;
    border-radius: 4px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-deep); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Radio buttons in sidebar */
[data-testid="stRadio"] > div {
    gap: 0.25rem !important;
}

/* Empty state styling */
div[data-testid="stInfoMessageContainer"] {
    background: var(--bg-card) !important;
    border: 1px dashed var(--border) !important;
    border-radius: 8px !important;
}
</style>"""