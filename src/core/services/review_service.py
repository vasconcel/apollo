def get_review_options(db):
    """Get available reviews for dropdown."""
    reviews = db.get_reviews()
    return {r[1]: r[0] for r in reviews}


def get_current_review_id():
    """Get current review ID from session state."""
    import streamlit as st
    if "review_id" not in st.session_state:
        st.session_state.review_id = 1
    return st.session_state.review_id


def set_current_review_id(review_id):
    """Set current review ID and refresh."""
    import streamlit as st
    st.session_state.review_id = review_id
    st.rerun()


def get_current_user_id(db=None):
    """Get current user ID from session state (for reviewer isolation).
    Validates against database to ensure user exists."""
    import streamlit as st
    if "user_id" not in st.session_state:
        st.session_state.user_id = "legacy_user"
    user_id = st.session_state.user_id
    if db and not db.is_valid_user(user_id):
        import logging
        logger = logging.getLogger("aims")
        logger.warning(f"[SECURITY] Invalid user_id {user_id} in session, falling back to legacy_user")
        st.session_state.user_id = "legacy_user"
        user_id = "legacy_user"
    return user_id


def set_current_user_id(user_id, db=None):
    """Set current user ID with validation."""
    import streamlit as st
    import logging
    logger = logging.getLogger("aims")
    if db and not db.is_valid_user(user_id):
        logger.error(f"[SECURITY] Attempt to set invalid user_id: {user_id}")
        return False
    logger.info(f"[AUDIT] User switched to: {user_id}")
    st.session_state.user_id = user_id
    st.rerun()
    return True


def get_reviewer_id():
    """Get current reviewer ID from session state (legacy - maps to user_id)."""
    import streamlit as st
    if "reviewer_id" not in st.session_state:
        st.session_state.reviewer_id = get_current_user_id()
    return st.session_state.reviewer_id


def get_article_index():
    """Get current article index from session state."""
    import streamlit as st
    if "current_article_idx" not in st.session_state:
        st.session_state.current_article_idx = 0
    return st.session_state.current_article_idx


def format_review_for_selector(reviews, current_id):
    """Format reviews for Streamlit selectbox."""
    options = list(reviews.keys())
    if current_id in reviews.values():
        idx = list(reviews.values()).index(current_id)
    else:
        idx = 0
    return options, idx


def get_user_list(db):
    """Get all users for selection."""
    users = db.get_users()
    return {u[0]: u[1] for u in users}


def get_user_options(db):
    """Get user list formatted for selectbox."""
    users = db.get_users()
    return [u[0] for u in users]


def get_pending_articles_for_current_user(db):
    """Get pending articles for current user (isolation enforced)."""
    user_id = get_current_user_id()
    return db.get_pending_articles_for_user(user_id)


def get_assigned_articles_for_current_user(db):
    """Get all articles assigned to current user."""
    user_id = get_current_user_id()
    return db.get_assigned_articles(user_id)