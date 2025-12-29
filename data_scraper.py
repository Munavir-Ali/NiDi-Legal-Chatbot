# data_scraper.py

import requests
from bs4 import BeautifulSoup
import pandas as pd
from pymongo import MongoClient
import urllib.parse
import io

# === DATABASE CONFIGURATION ===
MONGO_PASSWORD = "nidi@2022-2026"
ENCODED_PASSWORD = urllib.parse.quote_plus(MONGO_PASSWORD)

# MongoDB Atlas Connection URI
MONGO_URI = f"mongodb+srv://nidi_user0:{ENCODED_PASSWORD}@nidi.qkiysav.mongodb.net/?appName=NiDi"
DATABASE_NAME = "NiDi_DB"

# === DATA TARGETS ===
SCRAPING_TARGETS = {
    "total_cases": "https://keralapolice.gov.in/crime/total-cases",
    "ipc_cases": "https://keralapolice.gov.in/crime-statistics/ipc-cases",
    "sll_cases": "https://keralapolice.gov.in/crime-statistics/sll-cases",
    "crime_against_children": "https://keralapolice.gov.in/crime-statistics/crime-against-children",
    "crime_against_woman": "https://keralapolice.gov.in/crime-statistics/crime-against-woman",
    "sc_st_atrocities": "https://keralapolice.gov.in/crime-statistics/sc-st-atrocities-act-cases",
    "cyber_cases": "https://keralapolice.gov.in/crime-statistics/cyber-cases",
    "missing_cases": "https://keralapolice.gov.in/crime-statistics/missing-cases",
    "road_accidents": "https://keralapolice.gov.in/crime/road-accidents",
    "cotpa_cases": "https://keralapolice.gov.in/crime/cotpa",
    "pocso_cases": "https://keralapolice.gov.in/crime/pocso",
}


def clean_dataframe(df):
    """Standardizes column names, removes Sl. No. column, and ensures primary index is numeric."""
    df.columns = [col.replace('.', '_').strip().replace(' ', '_') for col in df.columns]

    if 'Sl_No_' in df.columns:
        df = df.drop(columns=['Sl_No_'])

    if not df.empty:
        index_col_name = df.columns[0]
        numeric_index = pd.to_numeric(df[index_col_name], errors='coerce')

        df = df.dropna(subset=[index_col_name])

        df[index_col_name] = numeric_index.dropna().astype(int, errors='ignore')

        df = df.astype(int, errors='ignore')

    return df


def scrape_crime_chart_data(url):
    """Fetches, parses, and extracts the primary data table from the given URL."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        crime_table = soup.find('table')

        if crime_table:
            df_list = pd.read_html(io.StringIO(str(crime_table)))
            crime_df = df_list[0]

            crime_df = clean_dataframe(crime_df)

            return crime_df
        else:
            return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def connect_and_insert(data_df, collection_override):
    """Converts DataFrame to dicts and inserts them into the specified MongoDB collection."""
    if data_df.empty:
        print(f"Data is empty. Skipping insertion for {collection_override}.")
        return

    data_dict = data_df.to_dict('records')

    try:
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        collection = db[collection_override]

        client.admin.command('ping')

        collection.delete_many({})
        result = collection.insert_many(data_dict)

        print(f"   Success: Inserted {len(result.inserted_ids)} documents into '{collection_override}'.")
        client.close()

    except Exception as e:
        print(f"   Error during MongoDB operation for {collection_override}: {e}")


def run_all_scrapers():
    """Master function to iterate through all targets and execute scraping/insertion."""
    print("\n--- Starting Comprehensive Data Indexing ---")

    for collection_name, url in SCRAPING_TARGETS.items():
        print(f"\n[Task] Processing: {collection_name}")

        data_df = scrape_crime_chart_data(url=url)

        if data_df is not None and not data_df.empty:
            print(f"   Data Head ({collection_name}):\n{data_df.head(2).to_string()}")
            connect_and_insert(data_df, collection_override=collection_name)
        else:
            print(f"   Skipping insertion for {collection_name}. Scraping failed.")


if __name__ == '__main__':
    run_all_scrapers()
    print("\n✅ All Core Data Acquisition and Indexing Complete.")