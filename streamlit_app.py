import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
        driver = None
        try:
            # Setup Chrome options for headless mode
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            driver = webdriver.Chrome(options=chrome_options)
            print(f"🌐 Attempt {attempt}: {url}")
            
            driver.get(url)
            time.sleep(8)  # let JS render
            
            # Find all div elements with flex flex-row class
            rows = driver.find_elements(By.CSS_SELECTOR, 'div.flex.flex-row')
            
            for row in rows:
                spans = row.find_elements(By.TAG_NAME, 'span')
                if len(spans) < 4:
                    continue
                
                label = spans[0].text.strip()
                if label.lower() == "average":
                    avg_7 = spans[1].text.strip()
                    avg_30 = spans[2].text.strip()
                    avg_90 = spans[3].text.strip()
                    driver.quit()
                    return avg_7, avg_30, avg_90
            
            driver.quit()
        except Exception as e:
            print(f"⚠️ Error on attempt {attempt} for {url}: {e}")
            if driver:
                driver.quit()
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
if st.button("🚀 Run Exchange Rate Analysis", type="primary"):
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

st.markdown("---")
st.markdown("*Note: This tool scrapes live exchange rate data and may take a few minutes to complete.*")