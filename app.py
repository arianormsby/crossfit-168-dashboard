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

# ---------------- WORLDWIDE CONTROL ----------------
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

            for row in rows:
                entrant = row.get("entrant", {})

                try:
                    age = int(entrant.get("age"))
                except:
                    age = None

                record = {
                    "division": "Male" if division == 1 else "Female",
                    "global_rank": int(row.get("overallRank")),
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

            if page >= data["pagination"]["totalPages"]:
                break

            page += 1

    return pd.DataFrame(all_rows)

with st.spinner("Loading leaderboard..."):
    df = fetch_data(region_value, world_limit)

df = df.convert_dtypes()
df["age"] = pd.to_numeric(df["age"], errors="coerce")

st.success(f"Loaded {len(df)} athletes")

# ---------------- AGE GROUP ----------------
def age_bucket(age):
    if pd.isna(age):
        return None
    age = int(age)

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

filtered_df = filtered_df.sort_values("global_rank")

# ---------------- LOCAL RANKS ----------------
for i in range(1, 5):
    col = f"w{i}_rank"
    if col in filtered_df:
        filtered_df[f"w{i}_rank_local"] = filtered_df[col].rank(method="min").astype(int)
        filtered_df[f"w{i}_delta"] = filtered_df[col] - filtered_df[f"w{i}_rank_local"]

# ---------------- POSITION COLUMN ----------------
filtered_df.insert(0, "position", range(1, len(filtered_df) + 1))

# ---------------- LEADERBOARD ----------------
st.subheader("Leaderboard")

st.dataframe(filtered_df, use_container_width=True)

# ---------------- DRILLDOWN ----------------
st.subheader("🔍 Athlete Breakdown")

selected = st.selectbox("Select Athlete", filtered_df["name"].unique())

athlete = filtered_df[filtered_df["name"] == selected].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Global Rank", athlete["global_rank"])
col2.metric("Age", athlete["age"])
col3.metric("Division", athlete["division"])

st.markdown(f"🏢 {athlete['affiliate']} | 🌍 {athlete['country']}")

# insights
ranks = [athlete[f"w{i}_rank_local"] for i in range(1,5)]
best = min(ranks)
worst = max(ranks)

st.write(f"Best Workout Rank: {best}")
st.write(f"Worst Workout Rank: {worst}")

# workouts
cols = st.columns(4)
for i in range(1,5):
    with cols[i-1]:
        st.markdown(f"### W{i}")
        st.metric("Local", athlete[f"w{i}_rank_local"])
        st.caption(f"Global: {athlete[f'w{i}_rank']}")
        st.write(athlete[f"w{i}_score"])

st.divider()

# ---------------- VISUALS ----------------
if visual_option == "Top 4 per Workout":

    medals = ["🥇","🥈","🥉","4️⃣"]

    for i in range(1,5):
        st.markdown(f"### Workout {i}")

        col1, col2 = st.columns(2)

        for j, div in enumerate(["Male","Female"]):
            with [col1,col2][j]:
                st.markdown(div)
                subset = filtered_df[filtered_df["division"]==div]

                top4 = subset.nsmallest(4,f"w{i}_rank_local")

                for k, (_, row) in enumerate(top4.iterrows()):
                    st.write(
                        f"{medals[k]} {row['name']} "
                        f"(L:{row[f'w{i}_rank_local']} / G:{row[f'w{i}_rank']})"
                    )

elif visual_option == "Average Workout Rank":

    avg = {f"W{i}": filtered_df[f"w{i}_rank_local"].mean() for i in range(1,5)}
    st.bar_chart(pd.DataFrame.from_dict(avg, orient="index"))

elif visual_option == "Rank Distribution":
    st.bar_chart(filtered_df["global_rank"])

elif visual_option == "Top Overall Athletes":
    st.dataframe(filtered_df.head(20), use_container_width=True)