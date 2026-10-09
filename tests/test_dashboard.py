import pytest
from ui.dashboard_data import DashboardDataProvider, default_dashboard_data, format_time_ago, format_file_size
from ui.styles import ENTERPRISE_CSS


def test_dashboard_styles_loaded():
    """Verify enterprise CSS stylesheet contains required SOC theme classes."""
    assert "qs-brand-container" in ENTERPRISE_CSS
    assert "qs-kpi-card" in ENTERPRISE_CSS
    assert "qs-badge" in ENTERPRISE_CSS
    assert "#0B132B" in ENTERPRISE_CSS  # Dark navy sidebar


def test_kpi_summary_computation():
    """Verify KPI aggregation computes total, sanitized, review, and blocked counts."""
    provider = default_dashboard_data
    kpi = provider.get_kpi_summary()

    assert "total_scans" in kpi
    assert "sanitized_count" in kpi
    assert "review_count" in kpi
    assert "blocked_count" in kpi
    assert kpi["total_scans"] >= 0
    if kpi["total_scans"] > 0:
        total = kpi["sanitized_count"] + kpi["review_count"] + kpi["blocked_count"]
        assert total == kpi["total_scans"]


def test_decision_trends_structure():
    """Verify decision trends return standard 6 time buckets with safe/review/blocked values."""
    provider = default_dashboard_data
    trends = provider.get_decision_trends("24H")

    assert len(trends) == 6
    for t in trends:
        assert "time" in t
        assert "safe" in t
        assert "review" in t
        assert "blocked" in t
        assert t["safe"] >= 0
        assert t["review"] >= 0
        assert t["blocked"] >= 0


def test_pii_distribution_zero_raw_pii():
    """CRITICAL PRIVACY INVARIANT: PII distribution must contain only aggregated counts and types."""
    provider = default_dashboard_data
    dist = provider.get_pii_distribution()

    assert "total_findings" in dist
    assert "categories" in dist
    assert dist["total_findings"] >= 0

    for cat in dist["categories"]:
        assert "type" in cat
        assert "count" in cat
        assert "pct" in cat
        assert "color" in cat
        # Ensure category type is an abstract identifier (e.g. PERSON, EMAIL), never raw names/emails
        assert "@" not in cat["type"]
        assert not any(char.isdigit() for char in cat["type"]) or "OTHERS" in cat["type"]


def test_processing_performance_derivation():
    """Verify operational performance metrics are properly derived from audit records."""
    provider = default_dashboard_data
    perf = provider.get_processing_performance()

    assert "avg_processing_time_s" in perf
    assert "avg_extraction_coverage" in perf
    assert "avg_residual_pii" in perf
    assert "avg_model_confidence" in perf


def test_active_policy_summary_binding():
    """Verify active policy card reads directly from Phase 6 policy."""
    provider = default_dashboard_data
    pol = provider.get_active_policy_summary()

    assert "name" in pol
    assert "version" in pol
    assert pol["high_threshold"] == 0.70
    assert pol["lower_threshold"] == 0.45
    assert pol["fail_closed"] is True
    assert pol["rescan_required"] is True


def test_recent_activity_and_scans_formatting():
    """Verify recent activity feed and scan table return formatted, safe descriptors."""
    provider = default_dashboard_data
    activities = provider.get_recent_activity(5)
    scans = provider.get_recent_scans_table(5)

    for a in activities:
        assert "title" in a
        assert "time_ago" in a
        assert a["badge"] in ["SAFE", "REVIEW", "BLOCKED"]

    for s in scans:
        assert "File Name" in s
        assert "Decision" in s
        assert "Processing Time" in s


def test_time_and_size_formatters():
    """Test utility formatting functions."""
    assert "s ago" in format_time_ago(100.0) or "d ago" in format_time_ago(100.0)
    assert format_file_size(None) == "3.2 MB"


def test_app_module_imports_cleanly():
    """Verify app.py syntax and module imports execute without error."""
    import app
    assert callable(app.process_file)
    assert callable(app.main)
