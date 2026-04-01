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

    option = st.selectbox("Load size", ["Top 500", "Top 1000", "Full dataset"])

    limit_map = {"Top 500": 10, "Top 1000": 20, "Full dataset": None}
    world_limit = limit_map[option]

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

aedt_time = datetime.fromtimestamp(
    st.session_state.last_refresh,
    tz=ZoneInfo("Australia/Sydney")
).strftime("%Y-%m-%d %H:%M:%S")

with col2:
    st.markdown(f"**Last updated (AEDT):** {aedt_time}")

# ---------------- DATA ----------------
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

            progress.progress(min(page / total_pages, 1.0))
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
age_group = st.sidebar.multiselect("Age Group", ["Under 35","35-39","40-44","45-49","50-54","55+"])
search = st.sidebar.text_input("Search Athlete")

# ---------------- VIEW SELECTOR ----------------
visual_option = st.sidebar.selectbox(
    "Visualisation",
    [
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

# ---------------- ADD POSITION COLUMN ----------------
filtered_df.insert(0, "position", range(1, len(filtered_df) + 1))

# ---------------- LEADERBOARD ----------------
st.subheader("Leaderboard")

event = st.dataframe(
    filtered_df,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row"
)

# ---------------- ATHLETE DRILLDOWN ----------------
if event.selection.rows:
    athlete = filtered_df.iloc[event.selection.rows[0]]

    st.divider()
    st.subheader(f"🔍 {athlete['name']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Rank", athlete["rank"])
    col2.metric("Age", athlete["age"])
    col3.metric("Division", athlete["division"])

    st.markdown(f"🏢 {athlete['affiliate']} | 🌍 {athlete['country']}")

    st.subheader("Workout Breakdown")

    cols = st.columns(4)

    for i in range(1, 5):
        with cols[i-1]:
            st.markdown(f"### W{i}")
            st.metric("Rank", athlete.get(f"w{i}_rank"))
            st.write(athlete.get(f"w{i}_score"))

st.divider()

# ---------------- VISUALS ----------------

if visual_option == "Top 4 per Workout":

    st.subheader("🏆 Top 4 Performers Per Workout")

    medals = ["🥇", "🥈", "🥉", "4️⃣"]

    for w in ["w1_rank","w2_rank","w3_rank","w4_rank"]:
        st.markdown(f"### {w.upper()}")

        top4 = filtered_df.nsmallest(4, w)

        for i, (_, row) in enumerate(top4.iterrows()):
            st.markdown(f"{medals[i]} {row['name']} (#{row[w]})")

elif visual_option == "Average Workout Rank":

    st.subheader("📊 Average Rank Per Workout")

    avg = {w: filtered_df[w].mean() for w in ["w1_rank","w2_rank","w3_rank","w4_rank"]}
    st.bar_chart(pd.DataFrame.from_dict(avg, orient="index"))

elif visual_option == "Rank Distribution":

    st.subheader("📈 Rank Distribution")
    st.bar_chart(filtered_df["rank"])

elif visual_option == "Top Overall Athletes":

    st.subheader("🏆 Top Overall Athletes")
    st.dataframe(filtered_df.head(10), width="stretch")