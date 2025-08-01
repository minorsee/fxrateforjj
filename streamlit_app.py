import json
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import streamlit as st
import io

st.title("📊 SGD Exchange Rate Averages")
st.write("Click the button below to fetch currency exchange rate averages and download the Excel file.")

# Load currency pair data from file
@st.cache_data
def load_currency_data():
    with open("sgd_exchange_rates.json") as f:
        return json.load(f)

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

                rows = page.locator('div.flex.flex-row')
                for i in range(rows.count()):
                    row = rows.nth(i)
                    spans = row.locator('span')
                    if spans.count() < 4:
                        continue

                    label = spans.nth(0).inner_text().strip()
                    if label.lower() == "average":
                        avg_7 = spans.nth(1).inner_text().strip()
                        avg_30 = spans.nth(2).inner_text().strip()
                        avg_90 = spans.nth(3).inner_text().strip()
                        browser.close()
                        return avg_7, avg_30, avg_90

                browser.close()
        except Exception as e:
            print(f"⚠️ Error on attempt {attempt} for {url}: {e}")
            time.sleep(2)  # wait before retry

    print(f"❌ Failed to fetch data from {url} after {max_retries} attempts.")
    return None, None, None

def run_analysis():
    currency_data = load_currency_data()
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Collect results into a matrix-style dictionary
    all_data = {}
    total_currencies = len(currency_data)
    
    for idx, item in enumerate(currency_data):
        from_curr = item["from_currency"]
        to_curr = item["to_currency"]
        currency = to_curr
        url = item["url"]

        status_text.text(f"📈 Extracting {from_curr}/{to_curr}... ({idx+1}/{total_currencies})")
        avg_7, avg_30, avg_90 = extract_averages_from_url(url)

        all_data[currency] = {
            "avg_7": avg_7,
            "avg_30": avg_30,
            "avg_90": avg_90
        }
        
        # Update progress
        progress_bar.progress((idx + 1) / total_currencies)

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

    # Create Excel file in memory
    df = pd.DataFrame.from_dict(matrix_data, orient="index")
    
    # Create a BytesIO buffer
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=True, engine='openpyxl')
    excel_buffer.seek(0)
    
    status_text.text("✅ Analysis complete!")
    progress_bar.progress(1.0)
    
    return excel_buffer.getvalue()

# Main interface
if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False

if st.button("🚀 Run Exchange Rate Analysis", type="primary", disabled=st.session_state.analysis_running):
    st.session_state.analysis_running = True
    with st.spinner("Fetching exchange rate data..."):
        try:
            excel_data = run_analysis()
            
            st.success("Analysis completed successfully!")
            
            # Download button
            st.download_button(
                label="📥 Download Excel File",
                data=excel_data,
                file_name="xe_sgd_currency_averages_matrix.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
        finally:
            st.session_state.analysis_running = False

st.markdown("---")
st.markdown("*Note: This tool scrapes live exchange rate data and may take a few minutes to complete.*")