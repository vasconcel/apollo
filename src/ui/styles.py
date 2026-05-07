"""Professional CSS styles for APOLLO - Dark Research Tool Aesthetic"""

def get_custom_css():
    return """<style>
:root {
    --bg-deep: #0D1117;
    --bg-card: #161B22;
    --bg-elevated: #1F2937;
    --border: #30363D;
    --border-muted: #21262D;
    --primary: #58A6FF;
    --primary-hover: #79B8FF;
    --success: #3FB950;
    --warning: #D29922;
    --error: #F85149;
    --text-primary: #F0F6FC;
    --text-secondary: #8B949E;
    --text-muted: #6E7681;
    --accent: #58A6FF;
}

/* Force dark theme */
html, body, .stApp {
    background: var(--bg-deep) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}

/* Force dark on all elements */
* {
    color: var(--text-primary) !important;
}

/* Background layers */
[data-testid="stAppViewContainer"] {
    background: var(--bg-deep) !important;
}

[data-testid="stSidebar"] {
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

/* Buttons */
.stButton > button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.5rem 1rem !important;
}

.stButton > button:hover {
    background: var(--primary-hover) !important;
}

.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary) !important;
}

/* Messages */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 6px !important;
    padding: 0.75rem 1rem !important;
}

.stSuccess {
    background: rgba(63, 185, 80, 0.15) !important;
    border-left: 3px solid var(--success) !important;
}

.stWarning {
    background: rgba(210, 153, 34, 0.15) !important;
    border-left: 3px solid var(--warning) !important;
}

.stError {
    background: rgba(248, 81, 73, 0.15) !important;
    border-left: 3px solid var(--error) !important;
}

.stInfo {
    background: rgba(88, 166, 255, 0.15) !important;
    border-left: 3px solid var(--primary) !important;
}

/* Progress */
.stProgress > div > div > div {
    background: var(--primary) !important;
    border-radius: 4px !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--border) !important;
}

.stTabs [data-baseweb="tab"] {
    color: var(--text-secondary) !important;
}

.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom: 2px solid var(--primary) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-deep); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* Metrics */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-size: 0.7rem !important;
}

[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
}
</style>"""