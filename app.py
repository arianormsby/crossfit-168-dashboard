import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="CrossFit Leaderboard", layout="wide")

BASE_URL = "https://c3po.crossfit.com/api/leaderboards/v2/competitions/quarterfinals/2026/leaderboards"

headers = {
    "accept": "*/*",
    "origin": "https://games.crossfit.com",
    "referer": "https://games.crossfit.com/",
    "user-agent": "Mozilla/5.0"
}

st.title("🏋️ CrossFit 168 – Performance Dashboard")
st.caption("Auto-refreshes every 60 seconds")

@st.cache_data(ttl=60)
def fetch_data():
    all_rows = []

    for division in [1, 2]:
        page = 1

        while True:
            params = {
                "quarterfinal": 263,
                "division": division,
                "region": 32,
                "sort": 0,
                "page": page
            }

            r = requests.get(BASE_URL, headers=headers, params=params)
            data = r.json()

            rows = data.get("leaderboardRows", [])
            if not rows:
                break

            for row in rows:
                entrant = row.get("entrant", {})
                affiliate = entrant.get("affiliateName", "")

                if affiliate and "crossfit 168" in affiliate.lower():
                    record = {
                        "division": "Male" if division == 1 else "Female",
                        "rank": int(row.get("overallRank")),
                        "name": entrant.get("competitorName"),
                        "affiliate": affiliate,
                        "score": row.get("overallScore")
                    }

                    # Add workouts
                    for s in row.get("scores", []):
                        i = s.get("ordinal")
                        record[f"w{i}_rank"] = int(s.get("rank"))
                        record[f"w{i}_score"] = s.get("scoreDisplay")

                    all_rows.append(record)

            if page >= data["pagination"]["totalPages"]:
                break

            page += 1

    return pd.DataFrame(all_rows)

df = fetch_data()

# ---------------- FILTERS ----------------
st.sidebar.header("Filters")

division = st.sidebar.selectbox("Division", ["All", "Male", "Female"])
affiliate = st.sidebar.selectbox(
    "Affiliate",
    ["All"] + sorted(df["affiliate"].dropna().unique().tolist())
)
workout = st.sidebar.selectbox(
    "Workout Focus",
    ["All", "Workout 1", "Workout 2", "Workout 3", "Workout 4"]
)

filtered_df = df.copy()

if division != "All":
    filtered_df = filtered_df[filtered_df["division"] == division]

if affiliate != "All":
    filtered_df = filtered_df[filtered_df["affiliate"] == affiliate]

filtered_df = filtered_df.sort_values("rank")

# ---------------- METRICS ----------------
col1, col2 = st.columns(2)
col1.metric("Athletes", len(filtered_df))
col2.metric("Best Rank", filtered_df["rank"].min() if not filtered_df.empty else "-")

st.divider()

# ---------------- LEADERBOARD ----------------
st.subheader("Leaderboard")

display_cols = [
    "rank", "name", "division", "affiliate",
    "w1_rank", "w1_score",
    "w2_rank", "w2_score",
    "w3_rank", "w3_score",
    "w4_rank", "w4_score"
]

existing_cols = [col for col in display_cols if col in filtered_df.columns]

st.dataframe(filtered_df[existing_cols], use_container_width=True)

st.divider()

# ---------------- TOP 4 PER WORKOUT (MALE + FEMALE) ----------------
st.subheader("🏆 Top 4 Performers Per Workout (Male & Female)")

workouts = [
    ("Workout 1", "w1_rank"),
    ("Workout 2", "w2_rank"),
    ("Workout 3", "w3_rank"),
    ("Workout 4", "w4_rank"),
]

for label, col_name in workouts:
    st.markdown(f"## {label}")

    col1, col2 = st.columns(2)

    # ---------------- MALE ----------------
    with col1:
        st.markdown("### 👨 Male")

        male_df = filtered_df[filtered_df["division"] == "Male"]

        if col_name in male_df.columns and not male_df.empty:
            top4_male = male_df.nsmallest(4, col_name)

            for _, row in top4_male.iterrows():
                st.markdown(
                    f"""
                    **#{row[col_name]}**  
                    {row['name']}  
                    *{row['affiliate']}*
                    """
                )
        else:
            st.write("No data")

    # ---------------- FEMALE ----------------
    with col2:
        st.markdown("### 👩 Female")

        female_df = filtered_df[filtered_df["division"] == "Female"]

        if col_name in female_df.columns and not female_df.empty:
            top4_female = female_df.nsmallest(4, col_name)

            for _, row in top4_female.iterrows():
                st.markdown(
                    f"""
                    **#{row[col_name]}**  
                    {row['name']}  
                    *{row['affiliate']}*
                    """
                )
        else:
            st.write("No data")

    st.divider()
# ---------------- AUTO REFRESH ----------------
time.sleep(60)
st.rerun()