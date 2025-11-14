import json
from playwright.sync_api import sync_playwright
import pandas as pd
import time

# Load currency pair data from file
with open("sgd_exchange_rates.json") as f:
    currency_data = json.load(f)

# Function to extract average rates (7, 30, 90 days) with retry
def extract_averages_from_url(url, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                print(f"🌐 Attempt {attempt}: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)  # let JS render

                # Look for the Average row in the statistics table
                average_elements = page.get_by_text("Average").all()
                for elem in average_elements:
                    parent = elem.locator('..')
                    parent_text = parent.inner_text()
                    
                    # Split the text and extract the three average values
                    parts = parent_text.split('\t')
                    if len(parts) >= 4 and parts[0].strip().lower() == "average":
                        avg_7 = parts[1].strip()
                        avg_30 = parts[2].strip() 
                        avg_90 = parts[3].strip()
                        browser.close()
                        return avg_7, avg_30, avg_90

                browser.close()
        except Exception as e:
            print(f"⚠️ Error on attempt {attempt} for {url}: {e}")
            time.sleep(2)  # wait before retry

    print(f"❌ Failed to fetch data from {url} after {max_retries} attempts.")
    return None, None, None

# Collect results into a matrix-style dictionary
all_data = {}

for item in currency_data:
    from_curr = item["from_currency"]
    to_curr = item["to_currency"]
    currency = to_curr
    url = item["url"]

    print(f"📈 Extracting {from_curr}/{to_curr} from {url}...")
    avg_7, avg_30, avg_90 = extract_averages_from_url(url)

    all_data[currency] = {
        "avg_7": avg_7,
        "avg_30": avg_30,
        "avg_90": avg_90
    }

# Create matrix for Excel
matrix_data = {
    "7days": {},
    "30days": {},
    "90days": {}
}

for currency, values in all_data.items():
    matrix_data["7days"][currency] = values.get("avg_7")
    matrix_data["30days"][currency] = values.get("avg_30")
    matrix_data["90days"][currency] = values.get("avg_90")

# Export to Excel
df = pd.DataFrame.from_dict(matrix_data, orient="index")
output_file = "xe_sgd_currency_averages_matrix.xlsx"
df.to_excel(output_file, index=True)

print(f"\n✅ Excel file saved as: {output_file}")
