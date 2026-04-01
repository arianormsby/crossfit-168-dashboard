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

# ---------------- WORLDWIDE ----------------
world_limit = None
if selected_region == "Worldwide":
    st.warning("⚠️ Worldwide can take time")

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
                    "name": entrant.get("competitorName"),
                    "global_rank": int(row.get("overallRank")),
                    "division": "Male" if division == 1 else "Female",
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

# ---------------- PERCENTILE ----------------
df["percentile"] = (1 - (df["global_rank"] / df["global_rank"].max())) * 100

# ---------------- PROFILE ----------------
def profile(row):
    ranks = [row[f"w{i}_rank"] for i in range(1,5)]
    var = pd.Series(ranks).var()

    if var < 50:
        return "Balanced"
    elif min(ranks) < 50:
        return "Specialist"
    else:
        return "Inconsistent"

df["profile"] = df.apply(profile, axis=1)

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
        "Top Overall Athletes",
        "Affiliate Leaderboard",
        "Top Affiliate per Workout"  
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

filtered_df.insert(0, "position", range(1, len(filtered_df)+1))

# ---------------- TABLE ----------------
st.subheader("Leaderboard")

event = st.dataframe(
    filtered_df,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row"
)

# ---------------- DRILLDOWN ----------------
if event.selection.rows:
    athlete = filtered_df.iloc[event.selection.rows[0]]

    st.divider()
    st.subheader(f"🔍 {athlete['name']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Rank", athlete["global_rank"])
    col2.metric("Percentile", f"{athlete['percentile']:.1f}%")
    col3.metric("Profile", athlete["profile"])

    st.markdown(f"🏢 {athlete['affiliate']} | 🌍 {athlete['country']}")

    cols = st.columns(4)
    for i in range(1,5):
        with cols[i-1]:
            st.markdown(f"### W{i}")
            st.metric("Rank", athlete[f"w{i}_rank"])
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

                top4 = subset.nsmallest(4,f"w{i}_rank")

                for k, (_, row) in enumerate(top4.iterrows()):
                    st.write(f"{medals[k]} {row['name']} (#{row[f'w{i}_rank']})")

elif visual_option == "Top Overall Athletes":
    st.dataframe(filtered_df.head(20), use_container_width=True)

elif visual_option == "Affiliate Leaderboard":

    aff = (
        filtered_df.groupby("affiliate")
        .agg(
            athletes=("name","count"),
            avg_rank=("global_rank","mean")
        )
        .sort_values("avg_rank")
        .reset_index()
    )

    st.subheader("🏢 Affiliate Leaderboard")
    st.dataframe(aff, use_container_width=True)
    
elif visual_option == "Top Affiliate per Workout":

    st.subheader("🏢 Top Affiliate per Workout")

    workouts = [1, 2, 3, 4]

    for i in workouts:
        st.markdown(f"### Workout {i}")

        col1, col2 = st.columns(2)

        for j, div in enumerate(["Male", "Female"]):
            with [col1, col2][j]:

                st.markdown(f"#### {div}")

                subset = filtered_df[filtered_df["division"] == div]

                if subset.empty:
                    st.write("No data")
                    continue

                # group by affiliate
                aff = (
                    subset.groupby("affiliate")
                    .agg(
                        avg_rank=(f"w{i}_rank", "mean"),
                        athletes=("name", "count")
                    )
                    .sort_values("avg_rank")
                    .reset_index()
                )

                if not aff.empty:
                    top = aff.iloc[0]

                    st.metric("Top Affiliate", top["affiliate"])
                    st.metric("Avg Rank", round(top["avg_rank"], 1))
                    st.metric("Athletes", top["athletes"])

                else:
                    st.write("No data")

        st.divider()
    