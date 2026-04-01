import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

st.set_page_config(page_title="CrossFit Dashboard", layout="wide")

BASE_URL = "https://c3po.crossfit.com/api/leaderboards/v2/competitions/quarterfinals/2026/leaderboards"

headers = {
    "accept": "*/*",
    "origin": "https://games.crossfit.com",
    "referer": "https://games.crossfit.com/",
    "user-agent": "Mozilla/5.0"
}

st.title("🌍 CrossFit Quarterfinals – Performance Dashboard")

# ---------------- REGION ----------------
st.sidebar.header("Data Scope")

region_options = {
    "Worldwide": None,
    "Oceania": 32,
    "North America East": 1,
    "North America West": 2,
    "Europe": 3,
    "Asia": 4,
    "South America": 5,
    "Africa": 6
}

selected_region = st.sidebar.selectbox("Region", list(region_options.keys()))
region_value = region_options[selected_region]

# ---------------- REFRESH ----------------
st.markdown("### 🔄 Data Controls")

col1, col2 = st.columns([1, 3])

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

with col1:
    if st.button("🔄 Refresh Now"):
        st.session_state.last_refresh = time.time()
        st.rerun()

last_updated = datetime.fromtimestamp(st.session_state.last_refresh).strftime("%H:%M:%S")

with col2:
    st.markdown(f"**Last updated:** {last_updated}")

if time.time() - st.session_state.last_refresh > 1800:
    st.session_state.last_refresh = time.time()
    st.rerun()

# ---------------- DATA ----------------
@st.cache_data(ttl=1800)
def fetch_data(region):
    all_rows = []

    for division in [1, 2]:
        page = 1

        while True:
            params = {
                "quarterfinal": 263,
                "division": division,
                "sort": 0,
                "page": page
            }

            if region is not None:
                params["region"] = region

            r = requests.get(BASE_URL, headers=headers, params=params)
            data = r.json()

            rows = data.get("leaderboardRows", [])
            if not rows:
                break

            for row in rows:
                entrant = row.get("entrant", {})

                record = {
                    "competitor_id": entrant.get("competitorId"),
                    "division": "Male" if division == 1 else "Female",
                    "region_rank": int(row.get("overallRank")),
                    "name": entrant.get("competitorName"),
                    "affiliate": entrant.get("affiliateName"),
                    "country": entrant.get("countryOfOriginName"),
                    "age": entrant.get("age"),
                }

                for s in row.get("scores", []):
                    i = s.get("ordinal")
                    record[f"w{i}_rank"] = int(s.get("rank"))
                    record[f"w{i}_score"] = s.get("scoreDisplay")

                all_rows.append(record)

            if page >= data["pagination"]["totalPages"]:
                break

            page += 1

    return pd.DataFrame(all_rows)

# ⚡ FAST worldwide (only top pages)
@st.cache_data(ttl=1800)
def fetch_worldwide_top(limit_pages=3):
    all_rows = []

    for division in [1, 2]:
        for page in range(1, limit_pages + 1):

            params = {
                "quarterfinal": 263,
                "division": division,
                "sort": 0,
                "page": page
            }

            r = requests.get(BASE_URL, headers=headers, params=params)
            data = r.json()

            rows = data.get("leaderboardRows", [])

            for row in rows:
                entrant = row.get("entrant", {})

                all_rows.append({
                    "competitor_id": entrant.get("competitorId"),
                    "world_rank": int(row.get("overallRank"))
                })

    return pd.DataFrame(all_rows)

# Load data
region_df = fetch_data(region_value)
world_df = fetch_worldwide_top()

# Merge correctly using ID
df = pd.merge(
    region_df,
    world_df,
    on="competitor_id",
    how="left"
)

# ---------------- FILTERS ----------------
st.sidebar.header("Filters")

division = st.sidebar.multiselect("Division", ["Male", "Female"], default=["Male", "Female"])

affiliate = st.sidebar.multiselect(
    "Affiliate",
    sorted(df["affiliate"].dropna().unique()) if not df.empty else []
)

country = st.sidebar.multiselect(
    "Country",
    sorted(df["country"].dropna().unique()) if not df.empty else []
)

search = st.sidebar.text_input("Search Athlete")

filtered_df = df.copy()

if division:
    filtered_df = filtered_df[filtered_df["division"].isin(division)]

if affiliate:
    filtered_df = filtered_df[filtered_df["affiliate"].isin(affiliate)]

if country:
    filtered_df = filtered_df[filtered_df["country"].isin(country)]

if search:
    filtered_df = filtered_df[
        filtered_df["name"].str.contains(search, case=False)
    ]

filtered_df = filtered_df.sort_values("region_rank")

# ---------------- METRICS ----------------
col1, col2 = st.columns(2)

col1.metric("Athletes", len(filtered_df))
col2.metric("Best Region Rank", filtered_df["region_rank"].min() if not filtered_df.empty else "-")

st.divider()

# ---------------- LEADERBOARD ----------------
st.subheader("Leaderboard (Region vs World)")

display_cols = [
    "region_rank", "world_rank", "name", "age", "division",
    "affiliate", "country",
    "w1_rank", "w1_score",
    "w2_rank", "w2_score",
    "w3_rank", "w3_score",
    "w4_rank", "w4_score"
]

existing_cols = [c for c in display_cols if c in filtered_df.columns]

st.dataframe(filtered_df[existing_cols], use_container_width=True)

st.divider()

# ---------------- TOP 4 ----------------
st.subheader("🏆 Top 4 Performers Per Workout")

workouts = [
    ("Workout 1", "w1_rank", "w1_score"),
    ("Workout 2", "w2_rank", "w2_score"),
    ("Workout 3", "w3_rank", "w3_score"),
    ("Workout 4", "w4_rank", "w4_score"),
]

medals = ["🥇", "🥈", "🥉", "4️⃣"]

for label, rank_col, score_col in workouts:
    st.markdown(f"## {label}")

    col1, col2 = st.columns(2)

    for i, div in enumerate(["Male", "Female"]):
        with [col1, col2][i]:
            st.markdown(f"### {div}")

            subset = filtered_df[filtered_df["division"] == div]

            if rank_col in subset.columns and not subset.empty:
                top4 = subset.nsmallest(4, rank_col).reset_index(drop=True)

                for j, row in top4.iterrows():
                    st.markdown(
                        f"""
                        {medals[j]} **#{row[rank_col]} – {row['name']} ({row['age']})**  
                        🏢 {row['affiliate']}  
                        🌍 {row['country']}  
                        ⏱ {row.get(score_col, '')}  
                        🌏 World: #{row.get('world_rank', '-')}
                        """
                    )
            else:
                st.write("No data")

    st.divider()