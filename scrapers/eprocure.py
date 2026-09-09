import requests
from bs4 import BeautifulSoup

session = requests.Session()

url = "https://www.eprocure.gov.bd/TenderDetailsServlet"

all_rows = []

size = 200

# Search both separately
keywords = ["audit ", "auditor ", "accountant ", "auditing "]

for keyword in keywords:

    page = 1

    while True:
        payload = {
            "funName": "AllTenders",
            "keyword": keyword,
            "pageNo": str(page),
            "size": str(size),
            "homeWSearch": "homeWSearch",
            "approve": "false",
            "h": "t",
        }

        response = session.post(url, data=payload)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        rows = soup.find_all("tr")

        print(f'Searching "{keyword}" - Page {page}: {len(rows)} rows')

        for row in rows:
            all_rows.append(row)

        page += 1

        # No more pages
        if len(rows) < size:
            break


# -----------------------------------------
# Remove duplicates
# -----------------------------------------

unique_rows = []
seen = set()

for row in all_rows:

    row_key = tuple(row)

    if row_key not in seen:
        seen.add(row_key)
        unique_rows.append(row)


print("\nTotal rows found:", len(all_rows))
print("Total unique rows:", len(unique_rows))


# -----------------------------------------
# Print results
# -----------------------------------------

# for row in unique_rows:
print(unique_rows[-1])  # Print last 9 columns of each row