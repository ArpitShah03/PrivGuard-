"""
UI package for Phase 7 Enterprise Security Operations Dashboard.
"""

from ui.styles import ENTERPRISE_CSS
from ui.dashboard_data import DashboardDataProvider, default_dashboard_data
from ui.components import (
    render_sidebar_header,
    render_sidebar_policy_card,
    render_top_header,
    render_kpi_cards,
    render_decision_trend_chart,
    render_pii_donut_chart,
    render_performance_and_activity,
)

__all__ = [
    "ENTERPRISE_CSS",
    "DashboardDataProvider",
    "default_dashboard_data",
    "render_sidebar_header",
    "render_sidebar_policy_card",
    "render_top_header",
    "render_kpi_cards",
    "render_decision_trend_chart",
    "render_pii_donut_chart",
    "render_performance_and_activity",
]
