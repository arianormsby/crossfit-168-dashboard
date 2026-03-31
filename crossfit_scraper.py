import requests
import pandas as pd
import time

BASE_URL = "https://c3po.crossfit.com/api/leaderboards/v2/competitions/quarterfinals/2026/leaderboards"

headers = {
    "accept": "*/*",
    "origin": "https://games.crossfit.com",
    "referer": "https://games.crossfit.com/",
    "user-agent": "Mozilla/5.0"
}

all_rows = []

print("Fetching CrossFit 168 athletes (Male + Female)...\n")

# Loop through divisions: 1 = Male, 2 = Female
for division in [1, 2]:
    page = 1

    print(f"\n--- Processing {'Male' if division == 1 else 'Female'} Division ---\n")

    while True:
        params = {
            "quarterfinal": 263,
            "division": division,
            "region": 32,
            "sort": 0,
            "page": page
        }

        response = requests.get(BASE_URL, headers=headers, params=params)

        if response.status_code != 200:
            print(f"❌ Request failed: {response.status_code}")
            print(response.text[:300])
            break

        data = response.json()

        rows = data.get("leaderboardRows", [])
        if not rows:
            print("No more data.")
            break

        total_pages = data["pagination"]["totalPages"]

        print(f"Division {division} | Page {page}/{total_pages} ({len(rows)} athletes)")

        for row in rows:
            entrant = row.get("entrant", {})
            affiliate = entrant.get("affiliateName", "")

            # Filter for CrossFit 168
            if affiliate and "crossfit 168" in affiliate.lower():
                scores = row.get("scores", [])

                record = {
                    "division": "Male" if division == 1 else "Female",
                    "overallRank": row.get("overallRank"),
                    "overallScore": row.get("overallScore"),
                    "competitorName": entrant.get("competitorName"),
                    "firstName": entrant.get("firstName"),
                    "lastName": entrant.get("lastName"),
                    "gender": entrant.get("gender"),
                    "age": entrant.get("age"),
                    "height": entrant.get("height"),
                    "weight": entrant.get("weight"),
                    "country": entrant.get("countryOfOriginName"),
                    "affiliate": affiliate,
                }

                # Add workout scores dynamically
                for s in scores:
                    i = s.get("ordinal")
                    record[f"w{i}_rank"] = s.get("rank")
                    record[f"w{i}_score"] = s.get("scoreDisplay")

                all_rows.append(record)

        if page >= total_pages:
            break

        page += 1
        time.sleep(0.5)

print(f"\n✅ Found {len(all_rows)} athletes from CrossFit 168")

# Create DataFrame
df = pd.DataFrame(all_rows)

if not df.empty:
    df["overallRank"] = df["overallRank"].astype(int)
    df = df.sort_values(by=["division", "overallRank"])

    output_file = "crossfit_168_region32_2026.csv"
    df.to_csv(output_file, index=False)

    print(f"📁 CSV saved as: {output_file}")
else:
    print("⚠️ No matching athletes found.")