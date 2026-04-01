import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="CrossFit Dashboard", layout="wide")

BASE_URL = "https://c3po.crossfit.com/api/leaderboards/v2/competitions/quarterfinals/2026/leaderboards"

headers = {
    "accept": "*/*",
    "origin": "https://games.crossfit.com",
    "referer": "https://games.crossfit.com/",
    "user-agent": "Mozilla/5.0"
}

st.title("🏋️ CrossFit Quarterfinals – Performance Dashboard")

# ---------------- REGION ----------------
st.sidebar.header("Data Scope")

region_options = {
    "Oceania": 32,
    "Worldwide": None,
    "North America East": 1,
    "North America West": 2,
    "Europe": 3,
    "Asia": 4,
    "South America": 5,
    "Africa": 6
}

selected_region = st.sidebar.selectbox("Region", list(region_options.keys()), index=0)
region_value = region_options[selected_region]

# ---------------- WORLDWIDE OPTIONS ----------------
world_limit = None
if selected_region == "Worldwide":
    st.warning("⚠️ Worldwide can take time to load")

    world_limit = st.selectbox(
        "Load size",
        ["Top 500", "Top 1000", "Full dataset"],
        index=0
    )

    limit_map = {
        "Top 500": 10,
        "Top 1000": 20,
        "Full dataset": None
    }

    world_limit = limit_map[world_limit]

    if not st.button("Load Worldwide Data"):
        st.stop()

# ---------------- REFRESH ----------------
col1, col2 = st.columns([1, 3])

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

with col1:
    if st.button("🔄 Refresh"):
        st.session_state.last_refresh = time.time()
        st.cache_data.clear()
        st.rerun()

# AEDT time using zoneinfo
aedt_time = datetime.fromtimestamp(
    st.session_state.last_refresh,
    tz=ZoneInfo("Australia/Sydney")
).strftime("%Y-%m-%d %H:%M:%S")

with col2:
    st.markdown(f"**Last updated (AEDT):** {aedt_time}")

# ---------------- DATA FETCH ----------------
@st.cache_data(ttl=1800)
def fetch_data(region, max_pages=None):

    progress = st.progress(0)
    status = st.empty()

    all_rows = []

    for division in [1, 2]:
        page = 1

        while True:

            if max_pages and page > max_pages:
                break

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

            total_pages = data["pagination"]["totalPages"]

            # progress %
            progress_val = min(page / total_pages, 1.0)
            progress.progress(progress_val)
            status.text(f"Loading page {page}/{total_pages}")

            for row in rows:
                entrant = row.get("entrant", {})

                try:
                    age = int(entrant.get("age"))
                except:
                    age = None

                record = {
                    "division": "Male" if division == 1 else "Female",
                    "rank": int(row.get("overallRank")),
                    "name": entrant.get("competitorName"),
                    "affiliate": entrant.get("affiliateName"),
                    "country": entrant.get("countryOfOriginName"),
                    "age": age,
                }

                for s in row.get("scores", []):
                    i = s.get("ordinal")
                    record[f"w{i}_rank"] = int(s.get("rank"))
                    record[f"w{i}_score"] = s.get("scoreDisplay")

                all_rows.append(record)

            if page >= total_pages:
                break

            page += 1

    progress.empty()
    status.empty()

    return pd.DataFrame(all_rows)

# ---------------- LOAD DATA ----------------
with st.spinner("Loading leaderboard..."):
    df = fetch_data(region_value, world_limit)

st.success(f"Loaded {len(df)} athletes")

# ---------------- AGE BUCKET ----------------
def age_bucket(age):
    if age is None:
        return None
    if 35 <= age <= 39:
        return "35-39"
    elif 40 <= age <= 44:
        return "40-44"
    elif 45 <= age <= 49:
        return "45-49"
    elif 50 <= age <= 54:
        return "50-54"
    elif age >= 55:
        return "55+"
    else:
        return "Under 35"

df["age_group"] = df["age"].apply(age_bucket)

# ---------------- FILTERS ----------------
st.sidebar.header("Filters")

division = st.sidebar.multiselect("Division", ["Male", "Female"], default=["Male", "Female"])

affiliate = st.sidebar.multiselect("Affiliate", sorted(df["affiliate"].dropna().unique()))
country = st.sidebar.multiselect("Country", sorted(df["country"].dropna().unique()))
age_group = st.sidebar.multiselect("Age Group", ["Under 35", "35-39", "40-44", "45-49", "50-54", "55+"])
search = st.sidebar.text_input("Search Athlete")

visual_option = st.sidebar.selectbox(
    "View",
    [
        "Leaderboard + Athlete Drilldown",
        "Top 4 per Workout",
        "Average Workout Rank",
        "Rank Distribution",
        "Top Overall Athletes"
    ]
)

filtered_df = df.copy()

if division:
    filtered_df = filtered_df[filtered_df["division"].isin(division)]
if affiliate:
    filtered_df = filtered_df[filtered_df["affiliate"].isin(affiliate)]
if country:
    filtered_df = filtered_df[filtered_df["country"].isin(country)]
if age_group:
    filtered_df = filtered_df[filtered_df["age_group"].isin(age_group)]
if search:
    filtered_df = filtered_df[filtered_df["name"].str.contains(search, case=False)]

filtered_df = filtered_df.sort_values("rank")

# ---------------- MAIN VIEW ----------------
if visual_option == "Leaderboard + Athlete Drilldown":

    event = st.dataframe(
        filtered_df,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row"
    )

    if event.selection.rows:
        athlete = filtered_df.iloc[event.selection.rows[0]]

        st.divider()
        st.subheader("🔍 Athlete Breakdown")

        st.write(athlete)

elif visual_option == "Top Overall Athletes":
    st.dataframe(filtered_df.head(10), width="stretch")