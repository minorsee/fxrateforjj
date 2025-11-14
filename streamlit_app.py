import json
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import streamlit as st
import io
import subprocess

# Install Playwright browsers on first run
@st.cache_resource
def install_playwright():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True, capture_output=True)
        return True
    except:
        return False

# Install browsers
install_playwright()

st.title("📊 SGD Exchange Rate Averages")
st.write("Process currency exchange rates in batches of 10 to ensure reliability.")

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

def run_analysis_batch(currency_batch, batch_num, total_batches):
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Collect results into a matrix-style dictionary
    all_data = {}
    total_currencies = len(currency_batch)

    status_text.text(f"🔄 Processing batch {batch_num}/{total_batches}")

    for idx, item in enumerate(currency_batch):
        from_curr = item["from_currency"]
        to_curr = item["to_currency"]
        currency = to_curr
        url = item["url"]

        status_text.text(f"📈 Extracting {from_curr}/{to_curr}... ({idx+1}/{total_currencies} in batch {batch_num})")
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

    status_text.text(f"✅ Batch {batch_num} complete!")
    progress_bar.progress(1.0)

    return excel_buffer.getvalue(), all_data

# Initialize session state
if "current_batch" not in st.session_state:
    st.session_state.current_batch = 0
if "all_results" not in st.session_state:
    st.session_state.all_results = {}
if "last_batch_data" not in st.session_state:
    st.session_state.last_batch_data = None
if "last_batch_number" not in st.session_state:
    st.session_state.last_batch_number = 0

# Load currency data
currency_data = load_currency_data()
BATCH_SIZE = 10
total_currencies = len(currency_data)
total_batches = (total_currencies + BATCH_SIZE - 1) // BATCH_SIZE

# Display progress
st.write(f"**Total currencies:** {total_currencies}")
st.write(f"**Batches of {BATCH_SIZE}:** {total_batches} batches")
st.write(f"**Current progress:** {len(st.session_state.all_results)}/{total_currencies} currencies processed")

# Show which currencies are in the next batch
if st.session_state.current_batch < total_batches:
    start_idx = st.session_state.current_batch * BATCH_SIZE
    end_idx = min(start_idx + BATCH_SIZE, total_currencies)
    next_batch = currency_data[start_idx:end_idx]

    with st.expander(f"🔍 Batch {st.session_state.current_batch + 1} currencies ({len(next_batch)} items)"):
        currencies_list = ", ".join([item["to_currency"] for item in next_batch])
        st.write(currencies_list)

st.markdown("---")

# Show download button for last completed batch (if any)
if st.session_state.last_batch_data is not None:
    st.info(f"✅ Batch {st.session_state.last_batch_number} completed and ready for download!")
    st.download_button(
        label=f"📥 Download Batch {st.session_state.last_batch_number} Excel",
        data=st.session_state.last_batch_data,
        file_name=f"xe_sgd_batch_{st.session_state.last_batch_number}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_batch_{st.session_state.last_batch_number}"
    )
    st.markdown("---")

# Process next batch button
if st.session_state.current_batch < total_batches:
    if st.button(f"🚀 Process Batch {st.session_state.current_batch + 1}/{total_batches}", type="primary"):
        start_idx = st.session_state.current_batch * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_currencies)
        batch_data = currency_data[start_idx:end_idx]

        try:
            excel_data, batch_results = run_analysis_batch(
                batch_data,
                st.session_state.current_batch + 1,
                total_batches
            )

            # Store results and batch data for download
            st.session_state.all_results.update(batch_results)
            st.session_state.last_batch_data = excel_data
            st.session_state.last_batch_number = st.session_state.current_batch + 1

            # Move to next batch
            st.session_state.current_batch += 1

            st.success(f"✅ Batch {st.session_state.last_batch_number} completed! ({len(batch_results)} currencies)")
            st.rerun()

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
else:
    st.success("🎉 All batches completed!")

# Download all results button (if any data collected)
if len(st.session_state.all_results) > 0:
    st.markdown("---")
    st.subheader("📦 Combined Results")
    st.write(f"Total currencies collected: {len(st.session_state.all_results)}")

    # Create combined Excel
    matrix_data = {
        "7days": {},
        "30days": {},
        "90days": {}
    }

    for currency, values in st.session_state.all_results.items():
        matrix_data["7days"][currency] = values.get("avg_7")
        matrix_data["30days"][currency] = values.get("avg_30")
        matrix_data["90days"][currency] = values.get("avg_90")

    df_combined = pd.DataFrame.from_dict(matrix_data, orient="index")
    excel_buffer_combined = io.BytesIO()
    df_combined.to_excel(excel_buffer_combined, index=True, engine='openpyxl')
    excel_buffer_combined.seek(0)

    st.download_button(
        label="📥 Download All Results (Combined Excel)",
        data=excel_buffer_combined.getvalue(),
        file_name="xe_sgd_all_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="combined_download"
    )

    # Reset button
    if st.button("🔄 Reset and Start Over"):
        st.session_state.current_batch = 0
        st.session_state.all_results = {}
        st.session_state.last_batch_data = None
        st.session_state.last_batch_number = 0
        st.rerun()

st.markdown("---")
st.markdown("*Note: Process each batch one at a time. Download results after each batch for safety.*")