"""Professional CSS styles for AIMS Streamlit UI - Technical Dashboard"""

def get_custom_css():
    return """<style>
:root {
    --primary: #3B82F6;
    --secondary: #475569;
    --accent: #3B82F6;
    --bg-deep: #0A0E14;
    --bg-surface: #1F2937;
    --bg-elevated: #374151;
    --text-primary: #F9FAFB;
    --text-secondary: #9CA3AF;
    --text-muted: #6B7280;
    --border: #374151;
    --success: #22C55E;
    --error: #EF4444;
    --warning: #F59E0B;
}

html, body, .stApp {
    background: var(--bg-deep) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-size: 14px !important;
}

section[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid var(--border) !important;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}

h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1rem !important; }

.ais-card {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    padding: 0.75rem !important;
    margin-bottom: 0.5rem !important;
}

div[data-testid="stMetric"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    padding: 0.5rem !important;
}

div[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-size: 0.75rem !important;
}

div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 1.25rem !important;
    font-weight: 600 !important;
}

.stButton > button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 4px !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
}

.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text-primary) !important;
}

.stDataFrame {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}

.streamlit-expanderHeader {
    background: var(--bg-surface) !important;
    border-radius: 4px !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}

hr, .stDivider {
    border: none !important;
    height: 1px !important;
    background: var(--border) !important;
}

.stProgress > div > div > div {
    background: var(--primary) !important;
}

.stSuccess, .stInfo { border-left: 3px solid var(--success) !important; }
.stError { border-left: 3px solid var(--error) !important; }
.stWarning { border-left: 3px solid var(--warning) !important; }

.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
}

.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom: 2px solid var(--primary) !important;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-surface); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>"""
