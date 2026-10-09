import streamlit as st
import pandas as pd
import altair as alt
from typing import Dict, Any, List, Optional


def render_sidebar_header():
    """Render top brand header in left sidebar."""
    st.sidebar.markdown("""
    <div class="qs-brand-container">
        <div class="qs-brand-icon">🛡️</div>
        <div>
            <div class="qs-brand-title">PrivGuard</div>
            <div class="qs-brand-sub">AI Data Privacy Gateway</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_policy_card(policy_info: Dict[str, Any]):
    """Render bottom policy status card in left sidebar matching reference design."""
    status_dot_class = "qs-status-dot" if policy_info.get("status") == "ACTIVE" else "qs-status-dot amber"
    status_label = "ACTIVE" if policy_info.get("status") == "ACTIVE" else "FALLBACK STRICT"
    
    st.sidebar.markdown(f"""
    <div class="qs-policy-card">
        <div class="qs-policy-header">
            <span class="qs-policy-title">Active Policy</span>
            <span class="{status_dot_class}"></span>
        </div>
        <div class="qs-policy-name">{policy_info.get('name', 'Enterprise AI Data Security Policy')}</div>
        <div class="qs-policy-ver">Version {policy_info.get('version', '1.0.0')} • {status_label}</div>
        <div class="qs-policy-item">
            <span class="qs-policy-check">✓</span> Fail Closed: Enabled
        </div>
        <div class="qs-policy-item">
            <span class="qs-policy-check">✓</span> Re-scan: Required
        </div>
        <div class="qs-policy-item">
            <span class="qs-policy-check">✓</span> Coverage Gate: Enabled
        </div>
        <div class="qs-sidebar-footer">
            Built for a safer tomorrow<br>
            <strong>Optiv Case Study</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_top_header(title: str = "Security Dashboard", subtitle: str = "Real-time overview of your PII security gateway"):
    """Render top header matching reference design."""
    h_col1, h_col2 = st.columns([3, 2])
    with h_col1:
        st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <div class="qs-title">{title}</div>
            <div class="qs-subtitle">{subtitle}</div>
        </div>
        """, unsafe_allow_html=True)
    with h_col2:
        st.markdown("""
        <div style="display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-top: 6px;">
            <div class="qs-online-badge">
                <span style="width: 7px; height: 7px; background-color: #059669; border-radius: 50%;"></span>
                System Online
            </div>
            <div style="font-size: 16px; cursor: pointer;">🔔</div>
            <div class="qs-avatar-circle">AS</div>
        </div>
        """, unsafe_allow_html=True)


def render_kpi_cards(kpi: Dict[str, Any]):
    """Render 4 prominent KPI cards with SVG sparklines matching reference image."""
    c1, c2, c3, c4 = st.columns(4)

    total_scans = kpi.get("total_scans", 0)
    sanitized = kpi.get("sanitized_count", 0)
    sanitized_pct = kpi.get("sanitized_pct", 0.0)
    review = kpi.get("review_count", 0)
    review_pct = kpi.get("review_pct", 0.0)
    blocked = kpi.get("blocked_count", 0)
    blocked_pct = kpi.get("blocked_pct", 0.0)

    # 1. Total Scans Card
    with c1:
        st.markdown(f"""
        <div class="qs-kpi-card">
            <div class="qs-kpi-top">
                <div class="qs-kpi-icon blue">📄</div>
                <div class="qs-kpi-label">Total Scans</div>
            </div>
            <div class="qs-kpi-value">{total_scans}</div>
            <div class="qs-kpi-sub">
                <span class="qs-kpi-trend-green">↑ 12%</span> vs previous day
            </div>
            <svg viewBox="0 0 100 24" style="width: 100%; height: 26px; margin-top: 6px;" preserveAspectRatio="none">
                <path d="M 0,18 Q 20,20 40,12 T 80,14 T 100,6" fill="none" stroke="#2563EB" stroke-width="2.5" stroke-linecap="round" />
            </svg>
        </div>
        """, unsafe_allow_html=True)

    # 2. Sanitized / Safe Card
    with c2:
        st.markdown(f"""
        <div class="qs-kpi-card">
            <div class="qs-kpi-top">
                <div class="qs-kpi-icon green">✓</div>
                <div class="qs-kpi-label">Sanitized / Safe</div>
            </div>
            <div class="qs-kpi-value">{sanitized}</div>
            <div class="qs-kpi-sub">{sanitized_pct}% of total</div>
            <svg viewBox="0 0 100 24" style="width: 100%; height: 26px; margin-top: 6px;" preserveAspectRatio="none">
                <path d="M 0,16 Q 25,12 50,18 T 80,10 T 100,12" fill="none" stroke="#10B981" stroke-width="2.5" stroke-linecap="round" />
            </svg>
        </div>
        """, unsafe_allow_html=True)

    # 3. Human Review Card
    with c3:
        st.markdown(f"""
        <div class="qs-kpi-card">
            <div class="qs-kpi-top">
                <div class="qs-kpi-icon amber">⚠️</div>
                <div class="qs-kpi-label">Human Review</div>
            </div>
            <div class="qs-kpi-value">{review}</div>
            <div class="qs-kpi-sub">{review_pct}% of total</div>
            <svg viewBox="0 0 100 24" style="width: 100%; height: 26px; margin-top: 6px;" preserveAspectRatio="none">
                <path d="M 0,15 Q 20,18 45,12 T 75,16 T 100,10" fill="none" stroke="#F59E0B" stroke-width="2.5" stroke-linecap="round" />
            </svg>
        </div>
        """, unsafe_allow_html=True)

    # 4. Blocked Card
    with c4:
        st.markdown(f"""
        <div class="qs-kpi-card">
            <div class="qs-kpi-top">
                <div class="qs-kpi-icon red">🛡️</div>
                <div class="qs-kpi-label">Blocked</div>
            </div>
            <div class="qs-kpi-value">{blocked}</div>
            <div class="qs-kpi-sub">{blocked_pct}% of total</div>
            <svg viewBox="0 0 100 24" style="width: 100%; height: 26px; margin-top: 6px;" preserveAspectRatio="none">
                <path d="M 0,16 Q 25,20 50,14 T 80,12 T 100,14" fill="none" stroke="#EF4444" stroke-width="2.5" stroke-linecap="round" />
            </svg>
        </div>
        """, unsafe_allow_html=True)


def render_decision_trend_chart(trend_data: List[Dict[str, Any]]):
    """Render clean Altair line chart matching reference layout."""
    df = pd.DataFrame(trend_data)
    df_melted = df.melt(id_vars=["time"], value_vars=["safe", "review", "blocked"], var_name="Decision", value_name="Count")
    
    # Map decision names and colors
    label_map = {"safe": "Safe", "review": "Human Review", "blocked": "Blocked"}
    df_melted["Decision"] = df_melted["Decision"].map(label_map)

    color_scale = alt.Scale(
        domain=["Safe", "Human Review", "Blocked"],
        range=["#10B981", "#F59E0B", "#EF4444"]
    )

    chart = alt.Chart(df_melted).mark_line(
        interpolate="monotone",
        point=alt.OverlayMarkDef(filled=True, size=40)
    ).encode(
        x=alt.X("time:N", title=None, axis=alt.Axis(labelAngle=0, labelColor="#64748B", domainColor="#E2E8F0")),
        y=alt.Y("Count:Q", title=None, scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(values=[0, 25, 50, 75, 100], gridColor="#F1F5F9")),
        color=alt.Color("Decision:N", scale=color_scale, legend=None),
        tooltip=["time:N", "Decision:N", "Count:Q"]
    ).properties(
        height=240,
        padding={"left": 10, "right": 10, "top": 10, "bottom": 10}
    ).configure_view(
        strokeWidth=0
    )

    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <span style="font-weight: 700; font-size: 15px; color: #0F172A;">Scan Decision Trend</span>
        <span style="font-size: 11px; display: flex; gap: 12px; font-weight: 600;">
            <span style="color: #10B981;">● Safe</span>
            <span style="color: #F59E0B;">● Human Review</span>
            <span style="color: #EF4444;">● Blocked</span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)


def render_pii_donut_chart(dist: Dict[str, Any]):
    """Render PII findings donut chart and breakdown list matching reference layout."""
    total = dist.get("total_findings", 0)
    categories = dist.get("categories", [])

    st.markdown('<div style="font-weight: 700; font-size: 15px; color: #0F172A; margin-bottom: 14px;">PII Findings by Type</div>', unsafe_allow_html=True)

    d_col1, d_col2 = st.columns([1, 1])

    with d_col1:
        circumference = 251.3
        offset = 0.0
        svg_arcs = []

        if total > 0:
            for cat in categories:
                pct = cat.get("pct", 0.0) / 100.0
                dash_len = pct * circumference
                gap_len = circumference - dash_len
                color = cat.get("color", "#64748B")
                svg_arcs.append(
                    f'<circle cx="60" cy="60" r="40" fill="none" stroke="{color}" stroke-width="16" '
                    f'stroke-dasharray="{dash_len:.1f} {gap_len:.1f}" stroke-dashoffset="-{offset:.1f}" />'
                )
                offset += dash_len
        else:
            svg_arcs.append('<circle cx="60" cy="60" r="40" fill="none" stroke="#E2E8F0" stroke-width="16" />')

        arcs_html = "".join(svg_arcs)

        donut_html = (
            f'<div style="display: flex; justify-content: center; align-items: center; height: 230px;">'
            f'<svg viewBox="0 0 120 120" style="width: 170px; height: 170px; transform: rotate(-90deg);">'
            f'{arcs_html}'
            f'<g style="transform: rotate(90deg); transform-origin: 60px 60px;">'
            f'<text x="60" y="58" text-anchor="middle" font-size="18" font-weight="700" fill="#0F172A">{total}</text>'
            f'<text x="60" y="72" text-anchor="middle" font-size="8" font-weight="500" fill="#64748B">Total Findings</text>'
            f'</g>'
            f'</svg>'
            f'</div>'
        )
        st.markdown(donut_html, unsafe_allow_html=True)

    with d_col2:
        legend_rows = []
        if categories:
            for cat in categories:
                color = cat.get("color", "#64748B")
                ctype = cat.get("type", "UNKNOWN")
                cnt = cat.get("count", 0)
                pct = cat.get("pct", 0.0)
                legend_rows.append(
                    f'<div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 7px;">'
                    f'<span style="display: flex; align-items: center; gap: 8px;">'
                    f'<span style="width: 8px; height: 8px; border-radius: 50%; background-color: {color}; display: inline-block;"></span>'
                    f'<strong style="color: #1E293B;">{ctype}</strong>'
                    f'</span>'
                    f'<span style="color: #64748B; font-weight: 500;">{cnt} ({pct}%)</span>'
                    f'</div>'
                )
        legend_body = "".join(legend_rows) if legend_rows else '<div style="color: #64748B; font-size: 12px;">No findings recorded.</div>'
        legend_html = f'<div style="display: flex; flex-direction: column; justify-content: center; height: 230px;">{legend_body}</div>'
        st.markdown(legend_html, unsafe_allow_html=True)


def render_performance_and_activity(perf: Dict[str, Any], activities: List[Dict[str, Any]]):
    """Render Processing Performance grid and Recent Activity feed."""
    p_col1, p_col2 = st.columns([1, 1])

    with p_col1:
        st.markdown("""
        <div style="font-weight: 700; font-size: 15px; color: #0F172A; margin-bottom: 14px;">
            Processing Performance
        </div>
        """, unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns(4)

        with sc1:
            st.markdown(f"""
            <div class="qs-perf-card">
                <div class="qs-perf-icon">⏱️</div>
                <div class="qs-perf-label">Avg Processing Time</div>
                <div class="qs-perf-value">{perf.get('avg_processing_time_s', '2.8s')}</div>
                <div class="qs-perf-sub">↓ 18% vs last week</div>
            </div>
            """, unsafe_allow_html=True)

        with sc2:
            st.markdown(f"""
            <div class="qs-perf-card">
                <div class="qs-perf-icon">⚡</div>
                <div class="qs-perf-label">Avg Extraction Coverage</div>
                <div class="qs-perf-value">{perf.get('avg_extraction_coverage', '98.7%')}</div>
                <div class="qs-perf-sub">↑ 0.2% vs last week</div>
            </div>
            """, unsafe_allow_html=True)

        with sc3:
            st.markdown(f"""
            <div class="qs-perf-card">
                <div class="qs-perf-icon">🛡️</div>
                <div class="qs-perf-label">Residual PII (avg)</div>
                <div class="qs-perf-value">{perf.get('avg_residual_pii', '0.0')}</div>
                <div style="font-size: 11px; color: #64748B;">Target: 0</div>
            </div>
            """, unsafe_allow_html=True)

        with sc4:
            st.markdown(f"""
            <div class="qs-perf-card">
                <div class="qs-perf-icon">🎯</div>
                <div class="qs-perf-label">Model Confidence (avg)</div>
                <div class="qs-perf-value">{perf.get('avg_model_confidence', '0.92')}</div>
                <div class="qs-perf-sub">↑ 0.03 vs last week</div>
            </div>
            """, unsafe_allow_html=True)

    with p_col2:
        st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <span style="font-weight: 700; font-size: 15px; color: #0F172A;">Recent Activity</span>
            <span style="font-size: 12px; color: #2563EB; font-weight: 600; cursor: pointer;">View All →</span>
        </div>
        """, unsafe_allow_html=True)

        if activities:
            for act in activities:
                badge_class = f"qs-badge-{act['badge'].lower()}"
                dot_color = act.get("color", "green")
                st.markdown(f"""
                <div class="qs-activity-item">
                    <div class="qs-activity-left">
                        <span class="qs-activity-dot {dot_color}"></span>
                        <div>
                            <span class="qs-activity-name">{act['title']}</span>
                            <span class="qs-activity-time" style="margin-left: 8px;">{act['time_ago']}</span>
                        </div>
                    </div>
                    <div>
                        <span class="qs-badge {badge_class}">{act['badge']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No recent scan activity.")
