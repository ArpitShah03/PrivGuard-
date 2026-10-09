"""
Enterprise Cybersecurity Design System & CSS Styling for QuantumShield v2.
Matches the enterprise SOC reference design:
- Dark navy left sidebar (#0B132B / #0F172A)
- Clean light main content area (#F8FAFC)
- Pure white rounded cards (#FFFFFF, 12px border-radius, subtle shadow)
- Primary blue accent (#2563EB)
- Tri-color status: Green (SAFE), Amber (HUMAN_REVIEW), Red (BLOCKED)
"""

ENTERPRISE_CSS = """
<style>
/* Global Font & Theme Reset */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #0F172A;
}

/* App Background */
.stApp {
    background-color: #F8FAFC;
}

/* Top Padding reduction */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* Sidebar Styling - Dark Navy */
section[data-testid="stSidebar"] {
    background-color: #0B132B !important;
    border-right: 1px solid #1E293B;
}

section[data-testid="stSidebar"] div.block-container {
    padding-top: 1.5rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

section[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}

/* Sidebar Brand Header */
.qs-brand-container {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px 20px 12px;
    border-bottom: 1px solid #1E293B;
    margin-bottom: 16px;
}

.qs-brand-icon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, #0EA5E9, #2563EB);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    box-shadow: 0 0 12px rgba(14, 165, 233, 0.4);
}

.qs-brand-title {
    font-size: 17px;
    font-weight: 700;
    color: #FFFFFF !important;
    line-height: 1.2;
}

.qs-brand-sub {
    font-size: 11px;
    color: #94A3B8 !important;
    font-weight: 500;
}

/* Sidebar Nav Radio Overrides */
div[data-testid="stSidebar"] .stRadio > div {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

div[data-testid="stSidebar"] .stRadio label {
    background: transparent;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    color: #94A3B8 !important;
    transition: all 0.15s ease-in-out;
}

div[data-testid="stSidebar"] .stRadio label:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #FFFFFF !important;
}

div[data-testid="stSidebar"] .stRadio label[data-checked="true"],
div[data-testid="stSidebar"] .stRadio div[aria-checked="true"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    font-weight: 600;
}

/* Sidebar Active Policy Card */
.qs-policy-card {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 14px;
    margin-top: 24px;
}

.qs-policy-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.qs-policy-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #94A3B8 !important;
    font-weight: 600;
}

.qs-status-dot {
    width: 8px;
    height: 8px;
    background-color: #10B981;
    border-radius: 50%;
    box-shadow: 0 0 8px #10B981;
}

.qs-policy-name {
    font-size: 13px;
    font-weight: 600;
    color: #F8FAFC !important;
    margin-bottom: 2px;
}

.qs-policy-ver {
    font-size: 11px;
    color: #64748B !important;
    margin-bottom: 10px;
}

.qs-policy-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #CBD5E1 !important;
    margin-bottom: 4px;
}

.qs-policy-check {
    color: #10B981 !important;
    font-weight: bold;
}

.qs-sidebar-footer {
    font-size: 10px;
    color: #64748B !important;
    margin-top: 14px;
    text-align: center;
    line-height: 1.4;
}

/* Enterprise Header */
.qs-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
}

.qs-title {
    font-size: 24px;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    letter-spacing: -0.02em;
}

.qs-subtitle {
    font-size: 13px;
    color: #64748B;
    margin-top: 4px;
    margin-bottom: 0;
}

.qs-header-controls {
    display: flex;
    align-items: center;
    gap: 12px;
}

.qs-online-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: #ECFDF5;
    border: 1px solid #A7F3D0;
    color: #059669;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.qs-avatar-circle {
    width: 32px;
    height: 32px;
    background-color: #0F172A;
    color: #FFFFFF;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
}

/* KPI Card Styles */
.qs-kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 18px 20px 14px 20px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    position: relative;
    overflow: hidden;
}

.qs-kpi-top {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}

.qs-kpi-icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}

.qs-kpi-icon.blue { background-color: #EFF6FF; color: #2563EB; }
.qs-kpi-icon.green { background-color: #ECFDF5; color: #059669; }
.qs-kpi-icon.amber { background-color: #FFFBEB; color: #D97706; }
.qs-kpi-icon.red { background-color: #FEF2F2; color: #DC2626; }

.qs-kpi-label {
    font-size: 13px;
    font-weight: 600;
    color: #475569;
}

.qs-kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.1;
    margin-bottom: 6px;
}

.qs-kpi-sub {
    font-size: 12px;
    color: #64748B;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 4px;
}

.qs-kpi-trend-green {
    color: #059669;
    font-weight: 600;
}

/* Dashboard Panel Card */
.qs-panel {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    margin-bottom: 20px;
}

.qs-panel-title {
    font-size: 15px;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Decision Status Badges */
.qs-badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.qs-badge-safe, .qs-badge-sanitized {
    background-color: #ECFDF5 !important;
    color: #059669 !important;
    border: 1px solid #A7F3D0 !important;
}

.qs-badge-review, .qs-badge-human_review, .qs-badge-human-review {
    background-color: #FFFBEB !important;
    color: #D97706 !important;
    border: 1px solid #FDE68A !important;
}

.qs-badge-blocked {
    background-color: #FEF2F2 !important;
    color: #DC2626 !important;
    border: 1px solid #FECACA !important;
}

/* Scan Result Executive Banner */
.qs-decision-banner {
    border-radius: 10px;
    padding: 16px 20px;
    margin: 14px 0 16px 0;
    border: 1px solid;
}
.qs-decision-banner.sanitized {
    background-color: #F0FDF4 !important;
    border-color: #BBF7D0 !important;
}
.qs-decision-banner.human_review {
    background-color: #FFFBEB !important;
    border-color: #FDE68A !important;
}
.qs-decision-banner.blocked {
    background-color: #FEF2F2 !important;
    border-color: #FECACA !important;
}

/* Recent Activity List */
.qs-activity-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 13px;
}

.qs-activity-item:last-child {
    border-bottom: none;
}

.qs-activity-left {
    display: flex;
    align-items: center;
    gap: 10px;
}

.qs-activity-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}
.qs-activity-dot.green { background-color: #10B981; }
.qs-activity-dot.amber { background-color: #F59E0B; }
.qs-activity-dot.red { background-color: #EF4444; }

.qs-activity-name {
    font-weight: 500;
    color: #1E293B;
}

.qs-activity-time {
    font-size: 11px;
    color: #94A3B8;
}

/* Performance Metric Sub-Card */
.qs-perf-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}

.qs-perf-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px 14px;
}

.qs-perf-icon {
    font-size: 16px;
    margin-bottom: 4px;
}

.qs-perf-label {
    font-size: 11px;
    color: #64748B;
    font-weight: 500;
}

.qs-perf-value {
    font-size: 20px;
    font-weight: 700;
    color: #0F172A;
    margin: 2px 0;
}

.qs-perf-sub {
    font-size: 11px;
    color: #059669;
    font-weight: 600;
}

/* Data Tables */
.stDataFrame {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
}

/* Alert Styling - High Contrast */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
    padding: 10px 14px !important;
}
div[data-testid="stAlert"] * {
    color: #1E293B !important;
}

/* File Uploader Contrast Fix */
div[data-testid="stFileUploader"] {
    background-color: #FFFFFF !important;
    border: 1px dashed #CBD5E1 !important;
    border-radius: 10px !important;
    padding: 12px !important;
}
div[data-testid="stFileUploader"] * {
    color: #1E293B !important;
}
div[data-testid="stFileUploader"] button {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border-radius: 6px !important;
}
</style>
"""
