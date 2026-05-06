import streamlit as st
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()

from src.core.database import Database
from src.core.services import (
    get_review_options,
    get_current_review_id,
    set_current_review_id,
    get_reviewer_id,
    get_current_user_id,
    set_current_user_id,
    get_user_options,
)

st.set_page_config(page_title="AIMS - Research Synthesis Platform", layout="wide", initial_sidebar_state="expanded", page_icon="")

from src.ui.styles import get_custom_css
st.markdown(get_custom_css(), unsafe_allow_html=True)

@st.cache_resource
def get_database():
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)

def get_current_route():
    if "route" not in st.session_state:
        st.session_state.route = "overview"
    return st.session_state.route

def set_route(route):
    st.session_state.route = route.lower()
    st.rerun()

if "user_id" not in st.session_state:
    st.session_state.user_id = "legacy_user"
if "reviewer_id" not in st.session_state:
    st.session_state.reviewer_id = "legacy_user"
if "current_article_idx" not in st.session_state:
    st.session_state.current_article_idx = 0

from src.ui.modules.overview_view import render_overview_view, get_quick_stats
from src.ui.modules.planning_view import render_planning
from src.ui.modules.ingestion_view import render_ingestion
from src.ui.modules.screening_view import render_screening
from src.ui.modules.consensus_view import render_consensus_view
from src.ui.modules.quality_view import render_quality_view
from src.ui.modules.extraction_view import render_extraction_view
from src.ui.modules.synthesis_view import render_synthesis_view
from src.ui.modules.export_view import render_export_audit_view

ROUTES = {
    "overview": render_overview_view,
    "planning": render_planning,
    "ingestion": render_ingestion,
    "screening": render_screening,
    "consensus": render_consensus_view,
    "quality": render_quality_view,
    "extraction": render_extraction_view,
    "synthesis": render_synthesis_view,
    "export": render_export_audit_view,
}

with st.sidebar:
    st.markdown("**AIMS**", unsafe_allow_html=True)
    st.caption("Research Intelligence Platform")
    st.divider()
    
    st.caption("MODULE")
    routes_list = list(ROUTES.keys())
    current_idx = routes_list.index(get_current_route()) if get_current_route() in routes_list else 0
    selected = st.radio("Navigate", routes_list, index=current_idx, label_visibility="collapsed", horizontal=False, key="route_selector")
    
    if selected != get_current_route():
        set_route(selected)
    
    st.divider()
    
    db = get_database()
    
    st.caption("USER")
    user_options = get_user_options(db)
    current_user = get_current_user_id()
    user_idx = user_options.index(current_user) if current_user in user_options else 0
    selected_user = st.selectbox("Select User", user_options, index=user_idx, key="user_selector")
    if selected_user != current_user:
        set_current_user_id(selected_user)
    
    st.divider()
    
    review_id = get_current_review_id()
    review_options = get_review_options(db)