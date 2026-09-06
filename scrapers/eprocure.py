import requests
from bs4 import BeautifulSoup

session = requests.Session()

url = "https://www.eprocure.gov.bd/TenderDetailsServlet"

all_rows = []

size = 200
page = 1

while True:
    payload = {
        "funName": "AllTenders",
        "keyword": "audit ",
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
    print(rows[-1])


    print(f"Page {page}: {len(rows)} rows")

    for row in rows:
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all("td")
        ]

        if cells:
            all_rows.append(cells)

    page += 1

    if len(rows) < size:
        break

print("Total rows:", len(all_rows))