"""Custom CSS styles for AIMS Streamlit UI."""

def get_custom_css():
    return """
<style>
    /* === COLOR PALETTE === */
    :root {
        --primary: #00D2FF;
        --secondary: #7000FF;
        --bg-deep: #0A0E14;
        --surface: rgba(255, 255, 255, 0.05);
        --surface-hover: rgba(255, 255, 255, 0.1);
        --surface-elevated: rgba(30, 30, 40, 0.8);
        --text-primary: #FFFFFF;
        --text-secondary: rgba(255, 255, 255, 0.7);
        --text-muted: rgba(255, 255, 255, 0.5);
        --border-subtle: rgba(255, 255, 255, 0.1);
        --glow-primary: 0 0 20px rgba(0, 210, 255, 0.3);
        --glow-secondary: 0 0 20px rgba(112, 0, 255, 0.3);
        
        /* Semantic colors */
        --success: #10B981;
        --error: #EF4444;
        --warning: #F59E0B;
    }
    
    /* === BODY & APP === */
    html, body, .stApp {
        background: var(--bg-deep) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    /* === SIDEBAR === */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0A0E14 0%, #151520 100%) !important;
        border-right: 1px solid var(--border-subtle) !important;
    }
    
    /* === HEADERS WITH TYPOGRAPHY === */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
    
    h1 { font-size: 2rem !important; margin-bottom: 1rem !important; }
    h2 { font-size: 1.5rem !important; margin-bottom: 0.75rem !important; }
    h3 { font-size: 1.25rem !important; margin-bottom: 0.5rem !important; }
    h4 { font-size: 1.1rem !important; margin-bottom: 0.5rem !important; }
    
    /* === CARD CONTAINERS === */
    .ais-card {
        background: var(--surface-elevated) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
        margin-bottom: 1rem !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
    }
    
    .ais-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-subtle);
    }
    
    .ais-card-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    
    /* === METRIC CARDS (GLASSMORPHISM) === */
    div[data-testid="stMetric"] {
        background: var(--surface-elevated) !important;
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
        background: rgba(40, 40, 50, 0.9) !important;
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
    
    /* Metric values - BRIGHT CYAN */
    div[data-testid="stMetricValue"] {
        color: var(--primary) !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        text-shadow: 0 0 10px rgba(0, 210, 255, 0.5) !important;
    }
    
    /* === BUTTONS (PRIMARY vs SECONDARY) === */
    .stButton > button {
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.85rem;
    }
    
    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
        color: white !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 0 30px rgba(0, 210, 255, 0.5), 0 0 30px rgba(112, 0, 255, 0.5) !important;
        transform: translateY(-2px);
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid var(--border-subtle) !important;
        color: var(--text-secondary) !important;
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: rgba(255, 255, 255, 0.15) !important;
        color: var(--text-primary) !important;
    }
    
    /* === TABS (PROGRESSIVE DISCLOSURE) === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: var(--surface) !important;
        padding: 0.5rem;
        border-radius: 12px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        color: var(--text-secondary) !important;
        transition: all 0.2s ease !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
        color: white !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--surface-hover) !important;
        color: var(--text-primary) !important;
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
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > div:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(0, 210, 255, 0.2) !important;
    }
    
    /* === RADIO BUTTONS === */
    .stRadio > div {
        background: var(--surface);
        padding: 0.5rem;
        border-radius: 8px;
    }
    
    /* === DATA FRAME / TABLE === */
    .stDataFrame {
        background: var(--surface) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border-subtle) !important;
    }
    
    [data-testid="stDataFrameResizableColumns"] {
        border: none !important;
    }
    
    /* === EXPANDERS === */
    .streamlit-expanderHeader {
        background: var(--surface) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border-subtle) !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: var(--surface-hover) !important;
    }
    
    /* === DIVIDER / HR === */
    hr, .stDivider {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--primary), var(--secondary), transparent) !important;
        margin: 1.5rem 0 !important;
    }
    
    /* === PROGRESS BARS === */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--primary), var(--secondary)) !important;
        border-radius: 4px;
    }
    
    /* === CAPTIONS === */
    .stCaption {
        color: var(--text-muted) !important;
        font-size: 0.8rem !important;
    }
    
    /* === EMPTY STATES === */
    .ais-empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: var(--surface) !important;
        border-radius: 16px;
        border: 1px dashed var(--border-subtle) !important;
    }
    
    .ais-empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    
    .ais-empty-state-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .ais-empty-state-description {
        color: var(--text-secondary);
        margin-bottom: 1.5rem;
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
    
    /* === PROTOCOL STEPPER === */
    .ais-stepper {
        display: flex;
        gap: 0.5rem;
        padding: 1rem;
        background: var(--surface);
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
    
    .ais-stepper-step {
        flex: 1;
        padding: 0.75rem;
        border-radius: 8px;
        text-align: center;
        transition: all 0.2s ease;
    }
    
    .ais-stepper-step.completed {
        background: rgba(16, 185, 129, 0.2);
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .ais-stepper-step.current {
        background: rgba(0, 210, 255, 0.2);
        border: 1px solid rgba(0, 210, 255, 0.3);
    }
    
    .ais-stepper-step.pending {
        background: var(--surface);
        border: 1px solid var(--border-subtle);
    }
    
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
    
    /* === FILE UPLOADER === */
    .stFileUploader {
        background: var(--surface);
        padding: 1rem;
        border-radius: 12px;
    }
    
    /* === SCROLLBAR === */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--surface);
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.3);
    }
</style>
"""