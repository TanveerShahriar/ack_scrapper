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

extracted_tenders = []

for row in unique_rows:
    cells = row.find_all("td")

    # Skip malformed rows
    if len(cells) < 6:
        continue

    # -----------------------------------------
    # Name
    # -----------------------------------------
    tender_type = cells[2].get_text(" ", strip=True).split(",")[0]

    brief_span = cells[2].find("span", id=lambda x: x and x.startswith("tenderBrief_"))

    if brief_span:
        tender_brief = brief_span.get_text(" ", strip=True)
    else:
        tender_brief = ""

    name = f"{tender_type}, {tender_brief}"


    # -----------------------------------------
    # Publish date + Closing date
    # -----------------------------------------
    date_text = list(cells[5].stripped_strings)

    publish_date = date_text[0] if len(date_text) > 0 else None
    closing_date = date_text[1] if len(date_text) > 1 else None


    # -----------------------------------------
    # Tender link
    # -----------------------------------------
    id_input = cells[2].find("input", {"name": "id"})

    if id_input and id_input.get("value"):
        tender_id = id_input["value"]

        link = (
            f"https://www.eprocure.gov.bd/"
            f"resources/common/ViewTender.jsp?id={tender_id}&h=t"
        )
    else:
        link = None


    # -----------------------------------------
    # Store result
    # -----------------------------------------
    tender = {
        "name": name,
        "publish_date": publish_date,
        "closing_date": closing_date,
        "link": link,
    }

    extracted_tenders.append(tender)


# -----------------------------------------
# Print results
# -----------------------------------------

print(extracted_tenders[-2])  # Print last 9 columns of each row