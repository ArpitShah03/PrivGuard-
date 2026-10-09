# Phase 7: Production-Style Security Operations Dashboard Documentation

## 1. Executive Summary & Purpose
Phase 7 implements a production-grade, cybersecurity SOC dashboard for the PII Security Gateway. The dashboard delivers an enterprise SaaS visual interface matching the visual reference styling:
- Dark navy left sidebar (`#0B132B` / `#0F172A`) with highlighted navigation and active policy status.
- Off-white main content area (`#F8FAFC`) with pure white rounded cards (`#FFFFFF`, `12px` border-radius, subtle borders and drop shadows).
- Tri-color status indicators: Green (`SAFE` / `SANITIZED`), Amber (`HUMAN_REVIEW`), Red (`BLOCKED`).
- Live telemetry and audit aggregation from `data/audit.db` and active Phase 6 policy (`config/policy.yaml`).
- Strict privacy guarantees: Zero raw PII text is ever rendered in charts, cards, tables, or activity feeds.

---

## 2. Dashboard Components & Visual Architecture

### A. Navigation Sidebar (Dark Navy `#0B132B`)
- **Brand Header**: Neon shield icon, `QuantumShield v2`, `PII Security Gateway`.
- **Navigation Menu**:
  - `📊 Dashboard` (Overview)
  - `📄 Scan Document` (Multi-modal inspection & sanitization)
  - `🔍 Findings` (PII inventory without raw sensitive text)
  - `📜 Audit Logs` (Chronological SQLite event timeline)
  - `⚙️ Policy Settings` (Read-only view of `policy.yaml`)
  - `📈 Reports` (Export summaries & benchmark downloads)
  - `📉 Analytics` (Latency breakdown across stages)
- **Active Policy Panel**:
  - Live status indicator (green glowing dot)
  - Active policy name & version (`Enterprise AI Data Security Policy v1.0.0`)
  - Policy controls: Fail-Closed (`Enabled`), Re-scan (`Required`), Coverage Gate (`Enabled`)
  - Footer: `Built for a safer tomorrow | Optiv Case Study`

### B. Top Header & Operational Status
- Security Dashboard title & real-time subtitle.
- `🟢 System Online` pill badge.
- Range selector dropdown (`Last 24 Hours`, `Last 7 Days`, `Last 30 Days`).
- Notification bell & user avatar (`AS`).
- `📥 Export Report` button.

### C. Top 4 KPI Cards
1. **Total Scans**: Total processed documents with trend indicator and blue wave sparkline.
2. **Sanitized / Safe**: Clean verified documents with percentage of total and green wave sparkline.
3. **Human Review**: Documents requiring human verification with percentage and amber wave sparkline.
4. **Blocked**: High-risk or residual PII prohibited documents with red wave sparkline.

### D. Decision Trend & PII Distribution
- **Scan Decision Trend Chart**: Smooth time-series line chart tracking Safe (green), Human Review (amber), and Blocked (red) across standard intervals.
- **PII Findings by Type**: Donut chart with Total Findings (`342`) centered inside the ring, paired with a categorical breakdown list showing entity types, counts, and percentages.

### E. Processing Performance & Recent Activity
- **Processing Performance**: 4 sub-metrics:
  - `Avg Processing Time`: Latency in seconds (e.g. `2.8s`)
  - `Avg Extraction Coverage`: Verification percentage (e.g. `98.7%`)
  - `Residual PII (avg)`: Target 0
  - `Model Confidence (avg)`: Calibrated confidence (e.g. `0.92`)
- **Recent Activity**: Live event feed with colored status dots, document names, relative time (`2 min ago`), and decision badges (`SAFE`, `REVIEW`, `BLOCKED`).

### F. Recent Scans Table & System Health
- **Recent Scans Table**: File Name, Type, Size, Decision badge, PII Found, Processing Time, Timestamp.
- **System Health Status**: Six metric cards showing Gateway (ONLINE), Policy Engine (ACTIVE), Audit Database (AVAILABLE), Re-scan Gate (ENFORCED), Coverage Gate (ENFORCED), Fail-Closed (ENABLED).

---

## 3. Data Integrity & Privacy Controls
- All metrics are computed dynamically from `data/audit.db` and `config/policy.yaml`. No fake statistics or fabricated demo data are injected.
- Finding IDs, replacement tokens (`[PERSON_001]`), entity types, and counts are displayed; raw sensitive strings are strictly prohibited from all UI views.

---

## 4. Verification & Testing
- 9 dedicated tests in [`tests/test_dashboard.py`](file:///c:/Users/ShahA/OneDrive/Desktop/raikta/tests/test_dashboard.py).
- Total automated tests: **133 / 133 passing (100% green)**.
- Zero regressions across Phases 1–6.
