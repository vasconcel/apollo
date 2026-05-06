"""
APOLLO - Decision Support System for EC/IC/QC
Simplified pipeline: ATLAS Excel → EC → IC → QC → Output
"""
import streamlit as st
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

from src.core.database import Database


st.set_page_config(
    page_title="APOLLO - EC/IC/QC Decision Support",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="⚡"
)


def get_custom_css():
    return """
    <style>
    .stApp { background: #fafafa; }
    </style>
    """


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
    st.session_state.user_id = "system"
if "reviewer_id" not in st.session_state:
    st.session_state.reviewer_id = "system"


from src.ui.modules.overview_view import render_overview
from src.ui.modules.planning_view import render_planning
from src.ui.modules.ingestion_view import render_ingestion
from src.ui.modules.eligibility_view import render_eligibility
from src.ui.modules.quality_view import render_quality
from src.ui.modules.atlas_processor_view import render_atlas_processor


ROUTES = {
    "overview": render_overview,
    "planning": render_planning,
    "ingestion": render_ingestion,
    "atlas_processor": render_atlas_processor,
    "eligibility": render_eligibility,
    "quality": render_quality,
}


with st.sidebar:
    st.markdown("**APOLLO**")
    st.caption("EC/IC/QC Decision Support")
    st.divider()
    
    st.caption("MODULE")
    routes_list = list(ROUTES.keys())
    current_idx = routes_list.index(get_current_route()) if get_current_route() in routes_list else 0
    selected = st.radio(
        "Navigate",
        routes_list,
        index=current_idx,
        label_visibility="collapsed",
        horizontal=False,
        key="route_selector"
    )
    
    if selected != get_current_route():
        set_route(selected)
    
    st.divider()
    
    db = get_database()
    
    st.caption("REVIEW")
    review_id = st.number_input("Review ID", min_value=1, value=st.session_state.get("review_id", 1), step=1)
    if review_id != st.session_state.get("review_id"):
        st.session_state.review_id = review_id
        st.rerun()
    
    st.caption("USER")
    reviewer_id = st.text_input("Reviewer ID", value=st.session_state.get("reviewer_id", "system"))
    if reviewer_id != st.session_state.get("reviewer_id"):
        st.session_state.reviewer_id = reviewer_id
        st.rerun()


st.divider()

render_func = ROUTES.get(get_current_route())
if render_func:
    render_func()
else:
    st.error(f"Unknown route: {get_current_route()}")