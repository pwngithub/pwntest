# dashboard.py — UPDATED (Category at Disconnect + Churned Customers Detail)
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
</style>
""", unsafe_allow_html=True)

# ——————————————— DATA LOADER ———————————————
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
            if not data.get("content"):
                break
            for item in data["content"]:
                row = {"Submission Date": item["created_at"], "Submission ID": item["id"]}
                for ans in item.get("answers", {}).values():
                    name = ans.get("name") or ans.get("text") or "unknown"
                    answer = ans.get("answer")
                    if isinstance(answer, dict):
                        parts = [
                            str(v) if not isinstance(v, list) else ", ".join(map(str, v))
                            for v in answer.values()
                        ]
                        answer = ", ".join(filter(None, parts))
                    elif isinstance(answer, list):
                        answer = ", ".join(map(str, answer))
                    elif answer is None or str(answer).strip() == "":
                        continue
                    row[name] = str(answer).strip()
                submissions.append(row)
            if len(data["content"]) < limit:
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

    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()

    if "Status" not in df.columns:
        df["Status"] = ""
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()

    if "MRC" not in df.columns:
        df["MRC"] = 0
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)

    if "Customer Name" not in df.columns:
        df["Customer Name"] = ""
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()

    # Keep these columns if missing to avoid KeyErrors later
    for col in ["Category", "Reason", "Location"]:
        if col not in df.columns:
            df[col] = pd.NA

    return df

def add_category_at_disconnect(df: pd.DataFrame) -> pd.DataFrame:
    """Add a computed 'Category at Disconnect' column based on last known category per customer."""
    if df is None or df.empty:
        return df

    work = df.copy()

    if "Category" not in work.columns:
        work["Category"] = pd.NA

    work["Category"] = work["Category"].astype(str).str.strip()
    work.loc[work["Category"].isin(["", "None", "nan", "NaN", "<NA>"]), "Category"] = pd.NA

    work = work.sort_values(["Customer Name", "Submission Date"], kind="mergesort")
    work["_last_known_category"] = work.groupby("Customer Name")["Category"].ffill()
    work["Category at Disconnect"] = work["_last_known_category"].fillna("Unknown")
    work.drop(columns=["_last_known_category"], inplace=True)

    return work

def build_churn_detail(churn_df: pd.DataFrame) -> pd.DataFrame:
    """One row per churned customer for the selected period (latest disconnect in period)."""
    if churn_df is None or churn_df.empty:
        return pd.DataFrame(columns=[
            "Customer Name", "Disconnect Date", "Category at Disconnect", "Reason",
            "MRC Lost", "Location"
        ])

    # Latest DISCONNECT per customer within the period
    x = churn_df.sort_values(["Customer Name", "Submission Date"], kind="mergesort").copy()
    x = x.drop_duplicates(subset=["Customer Name"], keep="last")

    # Clean/standardize
    x["Disconnect Date"] = x["Submission Date"].dt.date
    x["MRC Lost"] = pd.to_numeric(x.get("MRC", 0), errors="coerce").fillna(0)

    # Pick columns safely
    cols = []
    for c in ["Customer Name", "Disconnect Date", "Category at Disconnect", "Reason", "MRC Lost", "Location"]:
        if c in x.columns:
            cols.append(c)
        else:
            x[c] = pd.NA
            cols.append(c)

    x = x[cols].sort_values(["Disconnect Date", "MRC Lost"], ascending=[False, False]).reset_index(drop=True)
    return x

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

    # Add computed churn attribute
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

    period_start = pd.Timestamp(start_date)
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

    new_before = df[(df["Status"] == "NEW") & (df["Submission Date"] <= period_start)]
    disc_before = df[(df["Status"] == "DISCONNECT") & (df["Submission Date"] <= period_start)]
    active_start = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])
    beginning_customers = len(active_start)
    beginning_mrc = new_before[new_before["Customer Name"].isin(active_start)]["MRC"].sum()

    new_in = period_df[period_df["Status"] == "NEW"]
    churn_in = period_df[period_df["Status"] == "DISCONNECT"]

    new_count = new_in["Customer Name"].nunique()
    churn_count = churn_in["Customer Name"].nunique()
    new_mrc = new_in["MRC"].sum()
    churn_mrc = churn_in["MRC"].sum()
    net_mrr_movement = new_mrc - churn_mrc
    net_customer_movement = new_count - churn_count

    # Big Net MRR
    st.markdown(
        f"""
    <div class="net-mrr {'positive' if net_mrr_movement >= 0 else 'negative'}">
        {'+$' if net_mrr_movement >= 0 else '-$'}{abs(net_mrr_movement):,.0f}
    </div>
    <p style="text-align:center; font-size:22px; color:#E2E8F0;">Net MRR Movement • {start_date} to {end_date}</p>
    """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Quick Insights
    st.markdown("### Quick Insights This Period")
    cards = []
    if not churn_in.empty and "Reason" in churn_in.columns and churn_in["Reason"].astype(str).str.strip().ne("").any():
        top_reason = churn_in["Reason"].value_counts().idxmax()
        top_count = churn_in["Reason"].value_counts().max()
        top_mrc = churn_in[churn_in["Reason"] == top_reason]["MRC"].sum()
        cards.append(
            f'<div class="card flag"><h4>Most Common Churn Reason</h4><b>{top_reason}</b><br>{top_count} customers · ${top_mrc:,.0f} lost</div>'
        )
    if not churn_in.empty:
        biggest = churn_in.loc[churn_in["MRC"].idxmax()]
        name = str(biggest.get("Customer Name", "Unknown"))[:35]
        reason = str(biggest.get("Reason", "—"))
        cards.append(
            f'<div class="card flag"><h4>Largest Single Loss</h4><b>{name}</b><br>${biggest["MRC"]:,.0f} MRC<br><small>{reason}</small></div>'
        )
    if not new_in.empty:
        best = new_in.loc[new_in["MRC"].idxmax()]
        name = str(best.get("Customer Name", "New Customer"))[:35]
        loc = str(best.get("Location", "—"))
        cards.append(
            f'<div class="card win"><h4>Biggest New Win</h4><b>{name}</b><br>+${best["MRC"]:,.0f} MRC<br><small>{loc}</small></div>'
        )
    if not new_in.empty and "Location" in new_in.columns and new_in["Location"].astype(str).str.strip().ne("").any():
        top_loc = new_in["Location"].value_counts().idxmax()
        count = new_in["Location"].value_counts().max()
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

    # True Churn & Growth
    st.markdown("### True Churn Metrics")
    st.caption("Loss from existing base only")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"<div style='background:#1E293B;padding:20px;border-radius:12px;border-left:6px solid #DC2626;'><p style='margin:0;color:#94A3B8;font-size:15px;'>Churned Customers</p><p style='margin:10px 0 6px 0;color:white;font-size:42px;font-weight:bold;'>{churn_count:,}</p><p style='margin:0;color:#DC2626;font-size:24px;font-weight:bold;'>Down -{churn_count}</p></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div style='background:#1E293B;padding:20px;border-radius:12px;border-left:6px solid #DC2626;'><p style='margin:0;color:#94A3B8;font-size:15px;'>Lost MRC</p><p style='margin:10px 0 6px 0;color:white;font-size:42px;font-weight:bold;'>${churn_mrc:,.0f}</p><p style='margin:0;color:#DC2626;font-size:24px;font-weight:bold;'>Down -${churn_mrc:,.0f}</p></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### True Growth Metrics")
    st.caption("New wins only")
    g1, g2 = st.columns(2)
    with g1:
        st.markdown(
            f"<div style='background:#1E293B;padding:20px;border-radius:12px;border-left:6px solid #16A34A;'><p style='margin:0;color:#94A3B8;font-size:15px;'>New Customers</p><p style='margin:10px 0 6px 0;color:white;font-size:42px;font-weight:bold;'>{new_count:,}</p><p style='margin:0;color:#16A34A;font-size:24px;font-weight:bold;'>Up +{new_count}</p></div>",
            unsafe_allow_html=True,
        )
    with g2:
        st.markdown(
            f"<div style='background:#1E293B;padding:20px;border-radius:12px;border-left:6px solid #16A34A;'><p style='margin:0;color:#94A3B8;font-size:15px;'>New MRC Added</p><p style='margin:10px 0 6px 0;color:white;font-size:42px;font-weight:bold;'>${new_mrc:,.0f}</p><p style='margin:0;color:#16A34A;font-size:24px;font-weight:bold;'>Up +${new_mrc:,.0f}</p></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Net Results
    st.markdown("### Net Results")
    st.caption("True performance after churn & growth")
    net_cust_growth = ((new_count - churn_count) / beginning_customers * 100) if beginning_customers > 0 else 0

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

    # CHURN BY REASON + NEW CUSTOMER ACQUISITION (side by side)
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Churn by Reason")
        if not churn_in.empty:
            reason_df = (
                churn_in.groupby(["Reason", "Category at Disconnect"], dropna=False)
                .agg(Count=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values(["Count", "MRC_Lost"], ascending=False)
            )

            st.dataframe(reason_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True)

            fig = px.bar(
                reason_df,
                x="Count",
                y="Reason",
                orientation="h",
                color="MRC_Lost",
                hover_data=["Category at Disconnect", "MRC_Lost", "Count"],
                color_continuous_scale="Reds",
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Churn by Category (at Disconnect)")
            cat_df = (
                churn_in.groupby("Category at Disconnect", dropna=False)
                .agg(Customers_Lost=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values(["Customers_Lost", "MRC_Lost"], ascending=False)
            )
            st.dataframe(cat_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True)
            fig_cat = px.bar(
                cat_df,
                x="Customers_Lost",
                y="Category at Disconnect",
                orientation="h",
                color="MRC_Lost",
                color_continuous_scale="Reds",
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No churn this period")

    with col_b:
        st.subheader("New Customer Acquisition")
        if not new_in.empty:
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
            pie = px.pie(cat_vc, names="Category", values="count", color_discrete_sequence=px.colors.sequential.Greens)
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
            bar = px.bar(loc_vc, x="Location", y="count", color="count", color_continuous_scale="Greens")
            st.plotly_chart(bar, use_container_width=True)

            st.success(f"Added {new_count:,} new customers — +${new_mrc:,.0f} MRC")
        else:
            st.info("No new customers this period")

    st.divider()

    # ✅ NEW: CHURNED CUSTOMERS DETAIL
    st.markdown("### Churned Customers Detail")
    st.caption("One row per churned customer (latest disconnect in the selected period).")

    churn_detail_df = build_churn_detail(churn_in)

    if churn_detail_df.empty:
        st.info("No churned customers in this period.")
    else:
        st.dataframe(
            churn_detail_df.style.format({"MRC Lost": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

        # Quick totals for the detail view
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Customers (unique)", int(churn_detail_df["Customer Name"].nunique()))
        with d2:
            st.metric("Total MRC Lost", f"${churn_detail_df['MRC Lost'].sum():,.2f}")
        with d3:
            st.metric("Avg MRC Lost", f"${churn_detail_df['MRC Lost'].mean():,.2f}")

    st.divider()

    # CHURN BY COMPETITION — STANDS ALONE
    st.markdown("### Churn by Competition")
    st.caption("Customers lost to named competitors this period")

    if not churn_in.empty:
        competitors = {
            "Fidium": "New Provider Fidium",
            "Spectrum": "New Provider Spectrum",
            "Starlink": "New Provider Starlink",
            "CCI": "New Provider CCI",
            "GWI": "New Provider GWI",
            "Other Provider": "New Provider Other",
        }
        comp_data = []
        for label, keyword in competitors.items():
            mask = churn_in["Reason"].astype(str).str.contains(keyword, case=False, na=False)
            count = int(mask.sum())
            mrc = churn_in.loc[mask, "MRC"].sum()
            if count > 0:
                comp_data.append({"Competitor": label, "Customers Lost": count, "MRC Lost": mrc})

        if comp_data:
            comp_df = pd.DataFrame(comp_data)

            pie_col, total_col = st.columns([1.8, 1])
            with pie_col:
                fig_pie = px.pie(
                    comp_df,
                    names="Competitor",
                    values="Customers Lost",
                    color_discrete_sequence=px.colors.sequential.Reds_r,
                    hole=0.45,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                fig_pie.update_layout(showlegend=False, margin=dict(t=40, b=40, l=10, r=10))
                st.plotly_chart(fig_pie, use_container_width=True)

            with total_col:
                total_cust = int(comp_df["Customers Lost"].sum())
                total_mrc = comp_df["MRC Lost"].sum()
                st.markdown(
                    f"""
                <div style="background:#1E293B; padding:30px; border-radius:16px; border-left:10px solid #DC2626; text-align:center; height:100%;">
                    <p style="margin:0; color:#94A3B8; font-size:18px; font-weight:600;">Total Lost to Competitors</p>
                    <p style="margin:20px 0 10px 0; color:white; font-size:58px; font-weight:bold;">{total_cust:,}</p>
                    <p style="margin:0; color:#DC2626; font-size:32px; font-weight:bold;">-${total_mrc:,.0f} MRC</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.success("No customers lost to named competitors this period!")
    else:
        st.info("No churn data available")

    st.divider()

    # Export (now includes churn detail too)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Period": f"{start_date} to {end_date}",
            "Beginning Customers": beginning_customers,
            "Beginning MRC": beginning_mrc,
            "New Customers": new_count,
            "New MRC": new_mrc,
            "Churned Customers": churn_count,
            "Churned MRC": churn_mrc,
            "Net MRC": net_mrr_movement,
            "Net Customers": net_customer_movement,
        }]).to_excel(writer, sheet_name="Summary", index=False)

        churn_detail_df.to_excel(writer, sheet_name="Churned Customers Detail", index=False)

        # Optional: export raw filtered activity if you want it
        period_df.to_excel(writer, sheet_name="Period Activity (Raw)", index=False)

    st.download_button(
        "Download Report (Excel)",
        data=buffer.getvalue(),
        file_name=f"Talley_Report_{start_date}_to_{end_date}.xlsx",
    )

    st.caption("Auto-refreshes every 5 minutes • Real-time from JotForm")

if __name__ == "__main__":
    run_dashboard()
