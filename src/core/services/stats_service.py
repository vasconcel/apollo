from src.core.config_manager import load_config


def get_settings():
    """Load project settings from config."""
    config_mgr = load_config()
    return {
        "project_name": config_mgr.get("project_name", "My Research Project"),
        "project_description": config_mgr.get("project_description"),
        "research_questions": config_mgr.get("research_questions"),
        "inclusion_criteria": config_mgr.get("inclusion_criteria"),
        "exclusion_criteria": config_mgr.get("exclusion_criteria"),
        "quality_criteria": config_mgr.get("quality_criteria"),
        "extraction_fields": config_mgr.get("extraction_fields")
    }


def get_dashboard_stats(db, review_id: int):
    """Get dashboard statistics for sidebar."""
    return db.get_stats(review_id)


def get_prisma_flow(db, review_id: int):
    """Get PRISMA flow statistics."""
    return db.get_prisma_stats(review_id)


def get_gl_inventory(db):
    """Get Grey Literature articles for inventory display."""
    return db.get_gl_articles()


def format_research_questions(rqs):
    """Format research questions for display."""
    return [{"id": r[0], "question": r[1][:70], "type": r[3]} for r in rqs]


def format_exclusion_criteria(ec_list):
    """Format exclusion criteria for display."""
    return [{"id": ec[0], "description": ec[2][:60]} for ec in ec_list[:5]]


def get_protocol_stage_info(db):
    """Get current protocol stage and transition info."""
    current_stage = db.get_current_stage()
    stage_options = ["planning", "search", "screening", "quality", "extraction", "synthesis"]
    stage_labels = ["Planning", "Search & Ingestion", "Screening", "Quality Assessment", "Data Extraction", "Synthesis"]
    
    current_idx = stage_options.index(current_stage) if current_stage in stage_options else 0
    next_stage = stage_options[current_idx + 1] if current_idx < len(stage_options) - 1 else None
    
    return {
        "current_stage": current_stage,
        "current_idx": current_idx,
        "next_stage": next_stage,
        "stage_labels": stage_labels,
        "can_advance": next_stage is not None
    }


def advance_protocol_stage(db, target_stage, review_id: int):
    """Attempt to advance protocol stage."""
    return db.advance_stage(target_stage, review_id=review_id)