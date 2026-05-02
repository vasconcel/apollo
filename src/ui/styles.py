"""Custom CSS styles for AIMS Streamlit UI."""

def get_custom_css():
    return """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* === COLOR PALETTE === */
    :root {
        --primary: #00D2FF;
        --secondary: #7000FF;
        --bg-deep: #0A0E14;
        --surface: rgba(255, 255, 255, 0.05);
        --surface-hover: rgba(255, 255, 255, 0.1);
        --text-primary: #FFFFFF;
        --text-secondary: rgba(255, 255, 255, 0.7);
        --border-subtle: rgba(255, 255, 255, 0.1);
        --glow-primary: 0 0 20px rgba(0, 210, 255, 0.3);
        --glow-secondary: 0 0 20px rgba(112, 0, 255, 0.3);
    }
    
    /* === BODY & APP (respect streamlit icons) === */
    html, body, .stApp {
        background: var(--bg-deep) !important;
        color: var(--text-primary) !important;
    }
    
    /* Only apply Inter to text elements, NOT icons */
    .stMarkdown, .stCaption, p, label, span[class*="st-"]:not(.material-symbols-rounded) {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    /* Preserve Material Symbols for icons */
    .material-symbols-rounded {
        font-family: 'Material Symbols Rounded' !important;
    }
    
    /* === SIDEBAR === */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0A0E14 0%, #151520 100%) !important;
        border-right: 1px solid var(--border-subtle) !important;
    }
    
    /* === HEADERS === */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
    
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.25rem !important; }
    
    /* === METRIC CARDS (TRUE GLASSMORPHISM) === */
    div[data-testid="stMetric"] {
        background: var(--surface) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        transition: all 0.3s ease !important;
        position: relative;
        overflow: hidden;
    }
    
    div[data-testid="stMetric"]:hover {
        background: var(--surface-hover) !important;
        box-shadow: var(--glow-primary) !important;
        transform: translateY(-2px);
    }
    
    div[data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--primary), var(--secondary));
    }
    
    /* Metric labels */
    div[data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-size: 0.875rem !important;
    }
    
    /* Metric values - BRIGHT CYAN/WHITE */
    div[data-testid="stMetricValue"] {
        color: var(--primary) !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        text-shadow: 0 0 10px rgba(0, 210, 255, 0.5) !important;
    }
    
    /* === BUTTONS (GLOWING GRADIENT) === */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        box-shadow: 0 0 30px rgba(0, 210, 255, 0.5), 0 0 30px rgba(112, 0, 255, 0.5) !important;
        transform: translateY(-2px);
    }
    
    .stButton > button[kind="secondary"] {
        background: var(--surface) !important;
        border: 1px solid var(--border-subtle) !important;
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: var(--surface-hover) !important;
    }
    
    /* === INPUTS === */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        background: var(--surface) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(0, 210, 255, 0.2) !important;
    }
    
    /* === RADIO BUTTONS === */
    .stRadio > div {
        background: var(--surface);
        padding: 0.5rem;
        border-radius: 8px;
    }
    
    /* === DATA EDITOR === */
    .stDataFrame {
        background: var(--surface) !important;
        border-radius: 12px !important;
    }
    
    /* === EXPANDERS === */
    .streamlit-expanderHeader {
        background: var(--surface) !important;
        border-radius: 8px !important;
        border: 1px solid var(--border-subtle) !important;
    }
    
    /* === DIVIDER / HR === */
    hr, .stDivider {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--primary), var(--secondary), transparent) !important;
    }
    
    /* === PROGRESS BARS === */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--primary), var(--secondary)) !important;
    }
    
    /* === CAPTIONS === */
    .stCaption {
        color: var(--text-secondary) !important;
    }
    
    /* === BADGES / STATUS === */
    .badge {
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .badge-success { background: rgba(16, 185, 129, 0.2); color: #10B981; }
    .badge-error { background: rgba(239, 68, 68, 0.2); color: #EF4444; }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: #F59E0B; }
    .badge-info { background: rgba(0, 210, 255, 0.2); color: #00D2FF; }
    
    /* === SIDEBAR BRANDING === */
    .sidebar-title {
        font-size: 1.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .sidebar-subtitle {
        font-size: 0.75rem;
        color: var(--text-secondary);
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    
    /* === SECTIONS / CONTAINERS === */
    .custom-section {
        background: var(--surface);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid var(--border-subtle);
    }
    
    /* === ALERTS / MESSAGES === */
    .stSuccess {
        background: rgba(16, 185, 129, 0.1) !important;
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
    }
    
    .stError {
        background: rgba(239, 68, 68, 0.1) !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
    }
    
    .stWarning {
        background: rgba(245, 158, 11, 0.1) !important;
        border: 1px solid rgba(245, 158, 11, 0.3) !important;
    }
    
    .stInfo {
        background: rgba(0, 210, 255, 0.1) !important;
        border: 1px solid rgba(0, 210, 255, 0.3) !important;
    }
</style>
"""