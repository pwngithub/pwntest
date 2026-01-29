# dashboard.py — ENHANCED (1,3,4,5,6,7,8,9)
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

st.markdown("""
<style>
    .big-title {font-size: 44px !important; font-weight: bold; color: #1E3A8A; text-align: center;}
    .net-mrr {font-size: 68px !important; font-weight: bold; text-align: center; margin: 30px 0;}
    .positive {color: #16A34A !important;}
    .negative {color: #DC2626 !important;}
    .card {padding: 20px; border-radius: 12px; background: #1E293B; color: white;
           border-left: 6px solid; height: 170px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);}
    .win {border-left-color: #16A34A;}
    .flag {border-left-color: #DC2626;}
    .stApp {background-color: #0F172A;}
    .tiny {color:#94A3B8; font-size: 12px;}
</style>
""", unsafe_allow_html=True)

# ----------------------- Helpers -----------------------
def _clean_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip()

def _norm_reason_series(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str).str.strip()
    return s.str.lower()

def _safe_col(df: pd.DataFrame, col: str, default=pd.NA):
    if col not in df.columns:
        df[col] = default
    return df

def _to_money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"

# ----------------------- Data Loader -----------------------
def load_from_jotform():
    api_key = "22179825a79dba61013e4fc3b9d30fa4"
    form_id = "240073839937062"
    url = f"https://api.jotform.com/form/{form_id}/submissions"

    submissions = []
    offset = 0
    limit = 1000

    while True:
        params = {"apiKey": api_key, "limit": limit, "offset": offset, "orderby": "created_at"}
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            content = data.get("content") or []
            if not content:
                break

            for item in content:
                row = {"Submission Date": item.get("created_at"), "Submission ID": item.get("id")}
                for ans in (item.get("answers", {}) or {}).values():
                    name = ans.get("name") or ans.get("text") or "unknown"
                    answer = ans.get("answer")

                    # flatten dict/list answers
                    if isinstance(answer, dict):
                        parts = []
                        for v in answer.values():
                            if isinstance(v, list):
                                parts.append(", ".join(map(str, v)))
                            else:
                                parts.append(str(v))
                        answer = ", ".join([p for p in parts if p and p.strip()])
                    elif isinstance(answer, list):
                        answer = ", ".join(map(str, answer))

                    if answer is None or str(answer).strip() == "":
                        continue
                    row[name] = str(answer).strip()

                submissions.append(row)

            if len(content) < limit:
                break
            offset += limit

        except Exception as e:
            st.error(f"Error loading data: {e}")
            return pd.DataFrame()

    return pd.DataFrame(submissions)

@st.cache_data(ttl=300)
def get_data():
    df = load_from_jotform()
    if df.empty:
        return df

    rename_map = {
        "customerName": "Customer Name",
        "date": "Date",
        "employee": "Employee",
        "location": "Location",
        "status": "Status",
        "category": "Category",
        "reason": "Reason",
        "mrc": "MRC",
        "reasonOther": "Reason Other",
        "disconnectReason": "Disconnect Reason Detail",
    }
    df.rename(columns=rename_map, inplace=True)

    df["Submission Date"] = pd.to_datetime(df.get("Submission Date"), errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()

    df = _safe_col(df, "Status", "")
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()

    df = _safe_col(df, "MRC", 0)
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)

    df = _safe_col(df, "Customer Name", "")
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()

    for col in ["Category", "Reason", "Location"]:
        df = _safe_col(df, col, pd.NA)

    return df

# ----------------------- (5) Category at Disconnect with Source -----------------------
def add_category_at_disconnect(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add:
      - Category at Disconnect
      - Category Source

    Priority per DISCONNECT row:
      1) Category on the disconnect row (if present)
      2) Most recent Category from a NEW row for that customer on/before disconnect date
      3) Last known Category from any row on/before disconnect date
      4) Unknown
    """
    if df is None or df.empty:
        return df

    work = df.copy()

    work["Category"] = work["Category"].astype(str).str.strip()
    work.loc[work["Category"].isin(["", "None", "nan", "NaN", "<NA>"]), "Category"] = pd.NA

    work = work.sort_values(["Customer Name", "Submission Date"], kind="mergesort")

    # last known category from ANY row
    work["_last_any_category"] = work.groupby("Customer Name")["Category"].ffill()

    # last known category from NEW rows only
    new_mask = work["Status"].eq("NEW")
    work["_new_category_only"] = work["Category"].where(new_mask)
    work["_last_new_category"] = work.groupby("Customer Name")["_new_category_only"].ffill()

    # default blanks
    work["Category at Disconnect"] = pd.NA
    work["Category Source"] = pd.NA

    disc_mask = work["Status"].eq("DISCONNECT")

    # 1) category on disconnect row
    has_disc_cat = disc_mask & work["Category"].notna()
    work.loc[has_disc_cat, "Category at Disconnect"] = work.loc[has_disc_cat, "Category"]
    work.loc[has_disc_cat, "Category Source"] = "Disconnect row"

    # 2) latest NEW category (only where still missing)
    missing = disc_mask & work["Category at Disconnect"].isna()
    has_last_new = missing & work["_last_new_category"].notna()
    work.loc[has_last_new, "Category at Disconnect"] = work.loc[has_last_new, "_last_new_category"]
    work.loc[has_last_new, "Category Source"] = "Last NEW"

    # 3) last known any
    missing = disc_mask & work["Category at Disconnect"].isna()
    has_last_any = missing & work["_last_any_category"].notna()
    work.loc[has_last_any, "Category at Disconnect"] = work.loc[has_last_any, "_last_any_category"]
    work.loc[has_last_any, "Category Source"] = "Last known"

    # 4) unknown
    missing = disc_mask & work["Category at Disconnect"].isna()
    work.loc[missing, "Category at Disconnect"] = "Unknown"
    work.loc[missing, "Category Source"] = "Unknown"

    # for non-disconnect rows (still useful for grouping sometimes)
    work.loc[~disc_mask, "Category at Disconnect"] = work["_last_any_category"].fillna("Unknown")
    work.loc[~disc_mask, "Category Source"] = work["Category"].notna().map(lambda x: "Row value" if x else "Last known")

    work.drop(columns=["_last_any_category", "_new_category_only", "_last_new_category"], inplace=True, errors="ignore")
    return work

# ----------------------- (4) Churn Detail + Filters -----------------------
def build_churn_detail(churn_df: pd.DataFrame) -> pd.DataFrame:
    """One row per churned customer for selected period (latest disconnect in period)."""
    if churn_df is None or churn_df.empty:
        return pd.DataFrame(columns=[
            "Customer Name", "Disconnect Date", "Category at Disconnect", "Category Source",
            "Reason", "MRC Lost", "Location"
        ])

    x = churn_df.sort_values(["Customer Name", "Submission Date"], kind="mergesort").copy()
    x = x.drop_duplicates(subset=["Customer Name"], keep="last")

    x["Disconnect Date"] = x["Submission Date"].dt.date
    x["MRC Lost"] = pd.to_numeric(x.get("MRC", 0), errors="coerce").fillna(0)

    for col in ["Category at Disconnect", "Category Source", "Reason", "Location"]:
        if col not in x.columns:
            x[col] = pd.NA

    out = x[[
        "Customer Name", "Disconnect Date", "Category at Disconnect", "Category Source",
        "Reason", "MRC Lost", "Location"
    ]].copy()

    out["Reason"] = out["Reason"].fillna("").astype(str).str.strip().replace({"": "Unknown"})
    out["Location"] = out["Location"].fillna("").astype(str).str.strip().replace({"": "Unknown"})
    out["Category at Disconnect"] = out["Category at Disconnect"].fillna("Unknown")

    out = out.sort_values(["Disconnect Date", "MRC Lost"], ascending=[False, False]).reset_index(drop=True)
    return out

# ----------------------- (8) Competitor detection -----------------------
COMPETITOR_KEYWORDS = {
    "Fidium": ["fidium", "consolidated", "csi"],
    "Spectrum": ["spectrum", "charter"],
    "Starlink": ["starlink"],
    "CCI": ["cci", "consolidated communications"],
    "GWI": ["gwi"],
    "Other Provider": ["other provider", "new provider other", "another provider", "competitor"],
}

def detect_competitor(reason_text: str) -> str:
    r = _clean_str(reason_text).lower()
    if not r:
        return ""
    for comp, keys in COMPETITOR_KEYWORDS.items():
        if any(k in r for k in keys):
            return comp
    return ""

# ----------------------- (9) Data Health -----------------------
def data_health_summary(df_period: pd.DataFrame) -> dict:
    """Returns counts/ratios for quality indicators in the selected period."""
    out = {}

    if df_period is None or df_period.empty:
        return {
            "disconnect_missing_reason_pct": 0.0,
            "disconnect_missing_category_pct": 0.0,
            "new_missing_mrc_pct": 0.0,
            "duplicate_submissions_7d": 0,
            "multi_disconnect_same_customer": 0,
        }

    disc = df_period[df_period["Status"].eq("DISCONNECT")].copy()
    new = df_period[df_period["Status"].eq("NEW")].copy()

    # Missing reason on disconnects
    if not disc.empty:
        reason_blank = disc["Reason"].fillna("").astype(str).str.strip().eq("")
        out["disconnect_missing_reason_pct"] = float(reason_blank.mean() * 100.0)
        cat_blank = disc.get("Category at Disconnect", pd.Series(["Unknown"] * len(disc))).astype(str).str.strip().isin(["", "Unknown", "nan", "NaN"])
        out["disconnect_missing_category_pct"] = float(cat_blank.mean() * 100.0)
    else:
        out["disconnect_missing_reason_pct"] = 0.0
        out["disconnect_missing_category_pct"] = 0.0

    # Missing/zero MRC on NEW
    if not new.empty:
        out["new_missing_mrc_pct"] = float((pd.to_numeric(new["MRC"], errors="coerce").fillna(0) <= 0).mean() * 100.0)
    else:
        out["new_missing_mrc_pct"] = 0.0

    # Duplicate submissions within 7 days for same Customer+Status
    tmp = df_period.sort_values(["Customer Name", "Status", "Submission Date"], kind="mergesort").copy()
    tmp["prev_date"] = tmp.groupby(["Customer Name", "Status"])["Submission Date"].shift(1)
    tmp["gap_days"] = (tmp["Submission Date"] - tmp["prev_date"]).dt.total_seconds() / 86400.0
    out["duplicate_submissions_7d"] = int((tmp["gap_days"].notna() & (tmp["gap_days"] <= 7)).sum())

    # Multiple disconnects (same customer) in period
    if not disc.empty:
        out["multi_disconnect_same_customer"] = int((disc.groupby("Customer Name").size() > 1).sum())
    else:
        out["multi_disconnect_same_customer"] = 0

    return out

# ----------------------- Main Dashboard -----------------------
def run_dashboard():
    # Header
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image("https://via.placeholder.com/140x90/1E3A8A/FFFFFF?text=TALLEY", width=140)
    with col_title:
        st.markdown('<p class="big-title">Customer Dashboard</p>', unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color:#94A3B8; margin-top:-15px;'>True Churn • Growth • Real-time Insights</p>",
            unsafe_allow_html=True,
        )

    df = get_data()
    if df.empty:
        st.error("No data.")
        st.stop()

    # (5) add improved category-at-disconnect + source
    df = add_category_at_disconnect(df)

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=89)

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input(
            "Analysis Period",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        if st.button("Refresh Now"):
            st.cache_data.clear()
            st.rerun()

    # Filter period
    period_start = pd.Timestamp(start_date)
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

    # Active base at period start
    new_before = df[(df["Status"] == "NEW") & (df["Submission Date"] <= period_start)]
    disc_before = df[(df["Status"] == "DISCONNECT") & (df["Submission Date"] <= period_start)]
    active_start = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])
    beginning_customers = len(active_start)
    beginning_mrc = new_before[new_before["Customer Name"].isin(active_start)]["MRC"].sum()

    # Period activity
    new_in = period_df[period_df["Status"] == "NEW"].copy()
    disc_in = period_df[period_df["Status"] == "DISCONNECT"].copy()

    # (1) True churn vs disconnect activity
    true_churn_in = disc_in[disc_in["Customer Name"].isin(active_start)].copy()
    disconnect_activity_in = disc_in.copy()

    new_count = new_in["Customer Name"].nunique()
    new_mrc = new_in["MRC"].sum()

    true_churn_count = true_churn_in["Customer Name"].nunique()
    true_churn_mrc = true_churn_in["MRC"].sum()

    disconnect_activity_count = disconnect_activity_in["Customer Name"].nunique()
    disconnect_activity_mrc = disconnect_activity_in["MRC"].sum()

    net_mrr_movement = new_mrc - true_churn_mrc
    net_customer_movement = new_count - true_churn_count

    # (3) Rates
    churn_rate = (true_churn_count / beginning_customers * 100.0) if beginning_customers > 0 else 0.0
    mrr_churn_rate = (true_churn_mrc / beginning_mrc * 100.0) if beginning_mrc > 0 else 0.0
    nrr_like = ((beginning_mrc + new_mrc - true_churn_mrc) / beginning_mrc * 100.0) if beginning_mrc > 0 else 0.0

    # Big Net MRR
    st.markdown(
        f"""
    <div class="net-mrr {'positive' if net_mrr_movement >= 0 else 'negative'}">
        {'+$' if net_mrr_movement >= 0 else '-$'}{abs(net_mrr_movement):,.0f}
    </div>
    <p style="text-align:center; font-size:22px; color:#E2E8F0;">Net MRR Movement (True Churn) • {start_date} to {end_date}</p>
    """,
        unsafe_allow_html=True,
    )

    st.divider()

    # (9) Data Health Panel
    with st.expander("🩺 Data Health (selected period)", expanded=False):
        dh = data_health_summary(period_df)
        cA, cB, cC, cD, cE = st.columns(5)
        cA.metric("Disconnects missing Reason", f"{dh['disconnect_missing_reason_pct']:.1f}%")
        cB.metric("Disconnects missing Category", f"{dh['disconnect_missing_category_pct']:.1f}%")
        cC.metric("NEW with MRC <= 0", f"{dh['new_missing_mrc_pct']:.1f}%")
        cD.metric("Dup submissions ≤ 7 days", f"{dh['duplicate_submissions_7d']:,}")
        cE.metric("Customers w/ 2+ disconnects", f"{dh['multi_disconnect_same_customer']:,}")

        st.markdown("<div class='tiny'>Tip: If churn looks “off”, this panel usually explains why.</div>", unsafe_allow_html=True)

    # Quick Insights
    st.markdown("### Quick Insights This Period (True Churn)")
    cards = []

    if not true_churn_in.empty and true_churn_in["Reason"].fillna("").astype(str).str.strip().ne("").any():
        top_reason = true_churn_in["Reason"].value_counts().idxmax()
        top_count = int(true_churn_in["Reason"].value_counts().max())
        top_mrc = true_churn_in[true_churn_in["Reason"] == top_reason]["MRC"].sum()
        cards.append(
            f'<div class="card flag"><h4>Most Common True Churn Reason</h4><b>{top_reason}</b><br>{top_count} customers · ${top_mrc:,.0f} lost</div>'
        )

    if not true_churn_in.empty:
        biggest = true_churn_in.loc[true_churn_in["MRC"].idxmax()]
        name = _clean_str(biggest.get("Customer Name", "Unknown"))[:35]
        reason = _clean_str(biggest.get("Reason", "—")) or "—"
        cat = _clean_str(biggest.get("Category at Disconnect", "Unknown")) or "Unknown"
        cards.append(
            f'<div class="card flag"><h4>Largest True Loss</h4><b>{name}</b><br>${float(biggest["MRC"]):,.0f} MRC<br><small>{cat} • {reason}</small></div>'
        )

    if not new_in.empty:
        best = new_in.loc[new_in["MRC"].idxmax()]
        name = _clean_str(best.get("Customer Name", "New Customer"))[:35]
        loc = _clean_str(best.get("Location", "—")) or "—"
        cards.append(
            f'<div class="card win"><h4>Biggest New Win</h4><b>{name}</b><br>+${float(best["MRC"]):,.0f} MRC<br><small>{loc}</small></div>'
        )

    if not new_in.empty and new_in["Location"].fillna("").astype(str).str.strip().ne("").any():
        top_loc = new_in["Location"].value_counts().idxmax()
        count = int(new_in["Location"].value_counts().max())
        mrc = new_in[new_in["Location"] == top_loc]["MRC"].sum()
        cards.append(
            f'<div class="card win"><h4>Fastest Growing Location</h4><b>{top_loc}</b><br>+{count} customers<br>+${mrc:,.0f} MRC</div>'
        )

    if cards:
        cols = st.columns(len(cards))
        for col, card in zip(cols, cards):
            with col:
                st.markdown(card, unsafe_allow_html=True)
    else:
        st.success("All quiet — no activity this period!")

    st.divider()

    # (1) True Churn vs Disconnect Activity KPIs
    st.markdown("### Churn Overview")
    st.caption("True Churn = customers active at period start that disconnected during the period.")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Beginning Customers", f"{beginning_customers:,}")
    k2.metric("True Churn (Customers)", f"{true_churn_count:,}", f"{-true_churn_count:,}")
    k3.metric("Disconnect Activity (Unique)", f"{disconnect_activity_count:,}", "forms/unique in period")
    k4.metric("New Customers", f"{new_count:,}", f"+{new_count:,}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Beginning MRC", f"${beginning_mrc:,.0f}")
    k6.metric("True Churn MRC", f"${true_churn_mrc:,.0f}", f"-${true_churn_mrc:,.0f}")
    k7.metric("Disconnect Activity MRC", f"${disconnect_activity_mrc:,.0f}", "forms/unique in period")
    k8.metric("New MRC", f"${new_mrc:,.0f}", f"+${new_mrc:,.0f}")

    st.divider()

    # (3) Rates
    st.markdown("### Rate Metrics (True Churn)")
    r1, r2, r3 = st.columns(3)
    r1.metric("Customer Churn Rate", f"{churn_rate:.2f}%")
    r2.metric("MRR Churn Rate", f"{mrr_churn_rate:.2f}%")
    r3.metric("NRR-ish", f"{nrr_like:.2f}%")

    st.divider()

    # Net Results
    st.markdown("### Net Results (True Churn)")
    net_cust_growth = ((new_count - true_churn_count) / beginning_customers * 100.0) if beginning_customers > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    with col1:
        color = "#16A34A" if net_customer_movement >= 0 else "#DC2626"
        sign = "+" if net_customer_movement >= 0 else "-"
        st.markdown(
            f"<div style='background:#1E293B;padding:28px;border-radius:16px;text-align:center;border-left:10px solid {color};box-shadow: 0 8px 25px rgba(0,0,0,0.5);'><p style='margin:0;color:#94A3B8;font-size:18px;font-weight:600;'>Net Customers</p><p style='margin:16px 0 10px 0;color:white;font-size:56px;font-weight:bold;'>{sign}{abs(net_customer_movement):,}</p><p style='margin:0;color:{color};font-size:28px;font-weight:bold;'>{sign}{abs(net_customer_movement):,}</p></div>",
            unsafe_allow_html=True,
        )
    with col2:
        color = "#16A34A" if net_mrr_movement >= 0 else "#DC2626"
        sign = "+" if net_mrr_movement >= 0 else "-"
        st.markdown(
            f"<div style='background:#1E293B;padding:28px;border-radius:16px;text-align:center;border-left:10px solid {color};box-shadow: 0 8px 25px rgba(0,0,0,0.5);'><p style='margin:0;color:#94A3B8;font-size:18px;font-weight:600;'>Net MRC</p><p style='margin:16px 0 10px 0;color:white;font-size:56px;font-weight:bold;'>{sign}${abs(net_mrr_movement):,.0f}</p><p style='margin:0;color:{color};font-size:28px;font-weight:bold;'>{sign}${abs(net_mrr_movement):,.0f}</p></div>",
            unsafe_allow_html=True,
        )
    with col3:
        color = "#16A34A" if net_cust_growth >= 0 else "#DC2626"
        st.markdown(
            f"<div style='background:#1E293B;padding:28px;border-radius:16px;text-align:center;border-left:10px solid {color};box-shadow: 0 8px 25px rgba(0,0,0,0.5);'><p style='margin:0;color:#94A3B8;font-size:18px;font-weight:600;'>Net Customer Growth Rate</p><p style='margin:16px 0 10px 0;color:white;font-size:56px;font-weight:bold;'>{net_cust_growth:+.2f}%</p><p style='margin:0;color:{color};font-size:28px;font-weight:bold;'>{net_cust_growth:+.2f}%</p></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # (6) Top 10 Biggest True Losses
    st.markdown("### Top 10 Biggest True Losses")
    if true_churn_in.empty:
        st.info("No true churn in this period.")
    else:
        top10 = true_churn_in.sort_values("MRC", ascending=False).head(10).copy()
        top10["Disconnect Date"] = top10["Submission Date"].dt.date
        show = top10[[
            "Customer Name", "Disconnect Date", "MRC", "Category at Disconnect", "Category Source", "Reason", "Location"
        ]].copy()
        show.rename(columns={"MRC": "MRC Lost"}, inplace=True)
        st.dataframe(show.style.format({"MRC Lost": "${:,.2f}"}), use_container_width=True, hide_index=True)

    st.divider()

    # (7) Churn Hotspots + Net by Location
    st.markdown("### Location Performance (Net by Location)")
    left, right = st.columns(2)

    with left:
        st.subheader("True Churn Hotspots (Location)")
        if true_churn_in.empty:
            st.info("No true churn this period.")
        else:
            churn_loc = (
                true_churn_in.assign(Location=true_churn_in["Location"].fillna("Unknown").astype(str).str.strip().replace({"": "Unknown"}))
                .groupby("Location")
                .agg(Customers_Lost=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values(["Customers_Lost", "MRC_Lost"], ascending=False)
            )
            st.dataframe(churn_loc.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True, hide_index=True)
            fig = px.bar(churn_loc.head(15), x="Customers_Lost", y="Location", orientation="h", color="MRC_Lost")
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Net by Location (New - True Churn)")
        # Build location net
        new_loc = (
            new_in.assign(Location=new_in["Location"].fillna("Unknown").astype(str).str.strip().replace({"": "Unknown"}))
            .groupby("Location")
            .agg(New_Customers=("Customer Name", "nunique"), New_MRC=("MRC", "sum"))
            .reset_index()
        )
        churn_loc2 = (
            true_churn_in.assign(Location=true_churn_in["Location"].fillna("Unknown").astype(str).str.strip().replace({"": "Unknown"}))
            .groupby("Location")
            .agg(Churn_Customers=("Customer Name", "nunique"), Churn_MRC=("MRC", "sum"))
            .reset_index()
        )

        net_loc = pd.merge(new_loc, churn_loc2, on="Location", how="outer").fillna(0)
        net_loc["Net_Customers"] = net_loc["New_Customers"] - net_loc["Churn_Customers"]
        net_loc["Net_MRC"] = net_loc["New_MRC"] - net_loc["Churn_MRC"]
        net_loc = net_loc.sort_values(["Net_MRC", "Net_Customers"], ascending=False)

        st.dataframe(
            net_loc.style.format({"New_MRC": "${:,.0f}", "Churn_MRC": "${:,.0f}", "Net_MRC": "${:,.0f}"}),
            use_container_width=True,
            hide_index=True,
        )
        fig2 = px.bar(net_loc.head(20), x="Net_MRC", y="Location", orientation="h")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # (True churn) Churn by Reason + Category at Disconnect
    st.markdown("### True Churn Breakdown")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("True Churn by Reason (with Category at Disconnect)")
        if true_churn_in.empty:
            st.info("No true churn this period")
        else:
            reason_df = (
                true_churn_in.groupby(["Reason", "Category at Disconnect"], dropna=False)
                .agg(Count=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values(["Count", "MRC_Lost"], ascending=False)
            )
            st.dataframe(reason_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True, hide_index=True)
            fig = px.bar(
                reason_df.head(25),
                x="Count",
                y="Reason",
                orientation="h",
                color="MRC_Lost",
                hover_data=["Category at Disconnect", "MRC_Lost", "Count"],
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### True Churn by Category (at Disconnect)")
            cat_df = (
                true_churn_in.groupby("Category at Disconnect", dropna=False)
                .agg(Customers_Lost=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values(["Customers_Lost", "MRC_Lost"], ascending=False)
            )
            st.dataframe(cat_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True, hide_index=True)
            fig_cat = px.bar(cat_df, x="Customers_Lost", y="Category at Disconnect", orientation="h", color="MRC_Lost")
            st.plotly_chart(fig_cat, use_container_width=True)

    with col_b:
        st.subheader("New Customer Acquisition")
        if new_in.empty:
            st.info("No new customers this period")
        else:
            cat_vc = (
                new_in["Category"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace({"": "Unknown"})
                .value_counts()
                .reset_index()
            )
            cat_vc.columns = ["Category", "count"]
            pie = px.pie(cat_vc, names="Category", values="count")
            st.plotly_chart(pie, use_container_width=True)

            loc_vc = (
                new_in["Location"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace({"": "Unknown"})
                .value_counts()
                .head(10)
                .reset_index()
            )
            loc_vc.columns = ["Location", "count"]
            bar = px.bar(loc_vc, x="Location", y="count", color="count")
            st.plotly_chart(bar, use_container_width=True)

            st.success(f"Added {new_count:,} new customers — +${new_mrc:,.0f} MRC")

    st.divider()

    # (4) Churned Customers Detail — actionable
    st.markdown("### Churned Customers Detail (True Churn)")
    st.caption("One row per churned customer (latest disconnect in the selected period) — filter + export.")

    churn_detail_df = build_churn_detail(true_churn_in)

    if churn_detail_df.empty:
        st.info("No true churned customers in this period.")
    else:
        f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
        with f1:
            search = st.text_input("Search customer", value="", placeholder="Type part of a name…")
        with f2:
            cat_opts = ["All"] + sorted(churn_detail_df["Category at Disconnect"].fillna("Unknown").astype(str).unique().tolist())
            cat_sel = st.selectbox("Category", cat_opts, index=0)
        with f3:
            reason_opts = ["All"] + sorted(churn_detail_df["Reason"].fillna("Unknown").astype(str).unique().tolist())
            reason_sel = st.selectbox("Reason", reason_opts, index=0)
        with f4:
            loc_opts = ["All"] + sorted(churn_detail_df["Location"].fillna("Unknown").astype(str).unique().tolist())
            loc_sel = st.selectbox("Location", loc_opts, index=0)

        filtered = churn_detail_df.copy()
        if search.strip():
            filtered = filtered[filtered["Customer Name"].astype(str).str.contains(search.strip(), case=False, na=False)]
        if cat_sel != "All":
            filtered = filtered[filtered["Category at Disconnect"].astype(str) == cat_sel]
        if reason_sel != "All":
            filtered = filtered[filtered["Reason"].astype(str) == reason_sel]
        if loc_sel != "All":
            filtered = filtered[filtered["Location"].astype(str) == loc_sel]

        st.dataframe(
            filtered.style.format({"MRC Lost": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

        d1, d2, d3 = st.columns(3)
        d1.metric("Customers (unique)", int(filtered["Customer Name"].nunique()))
        d2.metric("Total MRC Lost", _to_money(filtered["MRC Lost"].sum()))
        d3.metric("Avg MRC Lost", _to_money(filtered["MRC Lost"].mean() if len(filtered) else 0))

        csv = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("Download Churn Detail (CSV)", data=csv, file_name="churned_customers_detail.csv", mime="text/csv")

    st.divider()

    # (8) Competitor churn detection (based on true churn reasons)
    st.markdown("### Churn by Competition (True Churn)")
    st.caption("Detected using keyword matching in the Reason field (editable keyword list in code).")

    if true_churn_in.empty:
        st.info("No true churn data available")
    else:
        tmp = true_churn_in.copy()
        tmp["Competitor"] = tmp["Reason"].apply(detect_competitor)

        # Filter for rows where a competitor was actually found
        comp_df = (
            tmp[tmp["Competitor"].astype(str).str.strip().ne("")]
            .groupby("Competitor")
            .agg(Count=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
            .reset_index()
            .sort_values("MRC_Lost", ascending=False)
        )

        if comp_df.empty:
            st.info("No specific competitor keywords detected in churn reasons this period.")
        else:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.dataframe(
                    comp_df.style.format({"MRC_Lost": "${:,.0f}"}),
                    use_container_width=True,
                    hide_index=True
                )
            with c2:
                fig_comp = px.bar(
                    comp_df,
                    x="Count",
                    y="Competitor",
                    orientation="h",
                    color="MRC_Lost",
                    text="MRC_Lost"
                )
                fig_comp.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_comp, use_container_width=True)

if __name__ == "__main__":
    run_dashboard()
