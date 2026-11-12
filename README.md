# MukoLend — Borrow Through Trust, Repay With Confidence

> **A Zimbabwe-focused community-based peer-to-peer lending management platform inspired by the Mukando savings model.**  
> **Tagline:** “Borrow through trust. Repay with confidence.”

---

## 📖 1. Project Overview & The Pitch

Imagine belonging to a trusted savings group where members help one another financially. When someone needs a small emergency loan, a fellow member may be willing to help. But how do you keep the agreement clear, track repayments, and ensure both parties have the same records?

**That is the problem we solve with MukoLend.**

MukoLend is a peer-to-peer lending management platform designed for Mukando groups, savings clubs, and trusted communities across Zimbabwe.

Our platform allows members to request short-term loans, enables other members to review and accept requests, and records the agreed terms, repayment dates, and outstanding balances in one place.

What makes MukoLend different is our focus on **community trust and transparency**. We want to make informal lending easier to manage without pretending that technology can eliminate financial risk.

Our product is a functional, full-stack fintech MVP built with **Python (Flask), SQLite, Jinja2, TailwindCSS, Chart.js, and Power BI reporting exports**. All financial transactions are simulated to demonstrate the entire peer lending lifecycle with complete clarity.

---

## 🎨 2. Visual Identity & Design System

The application is styled with an executive fintech palette:
- **Primary Brand Color**: **Bordeaux Silk** (`#50222D` / `bordeaux-900`)
- **Secondary Neutral Color**: **Silver Dust** (`#C4C3D0` / `silver-400`)
- **Accents**: Emerald Green (`#059669` for active/repaid), Amber Gold (`#D97706` for agreements/admin), Rose Red (`#E11D48` for overdue)
- **Typography**: Clean sans-serif with accessible color contrast and readable typography across desktop, tablet, and mobile.

---

## 🏛️ 3. Core Architecture & Database Schema

MukoLend strictly implements the **7-Table Master Schema** with foreign key constraints, indexing, and tamper-evident audit logging:

1. **`users`**: Secure credentials (Werkzeug password hashing), full name, email, role (`user`, `admin`).
2. **`communities`**: Mukando circles with unique invite codes (e.g. `MUKO-XXXXXX`), creator ID, and descriptions.
3. **`community_members`**: Role-based access control (`admin`, `member`) mapping users to groups.
4. **`loan_requests`**: Borrowing requests in integer cents minor units (`amount_minor`), proposed due dates, and status tracking (`pending`, `accepted`, `declined`, `cancelled`).
5. **`loans`**: Formal agreements recording principal, fees, dual acknowledgement timestamps (`borrower_accepted`, `lender_accepted`), and status (`awaiting_agreement`, `active`, `repaid`, `overdue`, `cancelled`).
6. **`repayments`**: Simulated payment ledger reducing balances with unique references (e.g. `SIM-ECO-XXXXXX`), timestamps, and recorder tracking.
7. **`audit_log`**: Tamper-evident ledger recording every security, agreement, and payment action.

---

## 🌟 4. Key Functional Features

1. **Dual-Acknowledgement Promissory Agreements**:
   - A loan only activates when **both** borrower and lender review and acknowledge identical terms.
   - Prevents disputes and unilateral changes.
2. **Precision Minor Units Engine**:
   - All financial figures are stored as integer minor units (cents) to completely eliminate floating-point drift.
3. **Due-Date Urgency & Overdue Synchronization**:
   - Real-time badges for *Due Soon* ($\le 3$ days), *Overdue*, and *On Track*.
   - Automatic background synchronization marks delinquent loans overdue.
4. **Interactive In-App Analytics (Chart.js)**:
   - 11 real-time financial KPIs.
   - 7 interactive charts: Request Velocity, Status Distribution, Capital by Group, Repayment Inflows, Outstanding Risk, Maturity Profile, and Member Growth.
5. **Power BI Ready Star Schema**:
   - Direct CSV export endpoints (`/analytics/export/<table_name>`) formatted for instant Power BI ingestion.
   - Comprehensive guide in `POWER_BI_REPORTING_GUIDE.md` with DAX measures and page designs.
6. **One-Click Prototype Persona Switcher**:
   - Instant switcher bar on top of every page to evaluate all 7 Zimbabwean member and admin roles.

---

## 🧑‍🤝‍🧑 5. Pre-Seeded Zimbabwean Personas

| Name | Role | Email | Scenario |
| :--- | :--- | :--- | :--- |
| **Farai Moyo** | Active Lender | `farai@mukolend.co.zw` | Hardware merchant in Mbare; active lender in Harare Central Traders |
| **Tinashe Mutasa** | Active Borrower | `tinashe@mukolend.co.zw` | Electronics vendor; active borrower with loan #ML-0003 |
| **Chipo Ndlovu** | Administrator | `chipo@mukolend.co.zw` | Uniform maker; founder/admin of Kambuzuma Friends circle |
| **Ruvimbo Chiweshe** | Active Peer | `ruvimbo@mukolend.co.zw` | Nurse & medical supplier; active member in Avondale Professionals |
| **Blessing Sibanda** | Partial Repayer | `blessing@mukolend.co.zw` | Broiler farmer; active borrower with loan #ML-0002 |
| **Tariro Sithole** | Overdue Debtor | `tariro@mukolend.co.zw` | Creative designer; has overdue loan #ML-0005 for testing alerts |
| **Executive Admin** | Global Admin | `admin@mukolend.co.zw` | Platform supervisor with access to `/admin` and audit logs |

*All standard accounts have default password `password123`. Global admin password is `admin12345`.*

---

## 🚀 6. Quick Start & Setup

### Prerequisites
- Python 3.10+ installed

### Installation & Run

1. **Clone or navigate to the directory:**
   ```bash
   cd mukolen
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize and seed the database:**
   ```bash
   python seed.py
   ```

4. **Launch the MukoLend application:**
   ```bash
   python app.py
   ```

5. **Open in your web browser:**
   ```
   http://127.0.0.1:5000
   ```

---

## 🧪 7. Automated Test Suite

Run the comprehensive automated test suite (11 test cases covering auth, RBAC, dual agreements, repayments, overdue sync, and CSV exports):

```bash
python -m unittest test_mukolend.py
```

Expected output:
```
...........
----------------------------------------------------------------------
Ran 11 tests in 4.206s

OK
```

---

## 📊 8. External Analytics with Power BI

For instructions on connecting Power BI Desktop to MukoLend's CSV exports, see [POWER_BI_REPORTING_GUIDE.md](file:///c:/Users/HP%20EliteBook/OneDrive/Desktop/mukolen/POWER_BI_REPORTING_GUIDE.md). It includes:
- Star schema dimension and fact tables
- DAX measures (Total Approved Volume, Repayment Rate, Delinquency Rate, etc.)
- Recommended report page wireframes
- Data validation checklist

---

## 🛡️ 9. Community Trust Philosophy

> *"We want to make informal lending easier to manage without pretending that technology can eliminate financial risk."*

MukoLend is not a speculative algorithm or predatory lender. It is a digital constitution for community solidarity that empowers Zimbabwean Mukando groups to manage their existing financial trust with absolute clarity and confidence.
