# Cleans data after reading it.
import os
import pandas as pd
from datetime import datetime

# GitHub CSV
GITHUB_CSV_URL = 'https://github.com/ellianag03/CS396/blob/da4e456bde9f1707f6eb6abc5fced64d851de0f1/NewestData/annual-emissions-ea283976-e42d-46c6-85e5-87775e3b0bc5.csv'


# Where processed data will be saved
OUTPUT_DIR = "data/seed"


def clean_epa_pipeline():

    # Create output folder
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load CSV directly from GitHub
    print("Loading data from GitHub...")

    df = pd.read_csv(GITHUB_CSV_URL)

    # Fill missing numerical values with 0
    numeric_columns = [
        "Gross Load (MWh)",
        "Steam Load (1000 lb)",
        "SO2 Mass (short tons)",
        "SO2 Rate (lbs/mmBtu)",
        "CO2 Mass (short tons)",
        "CO2 Rate (short tons/mmBtu)",
        "NOx Mass (short tons)",
        "NOx Rate (lbs/mmBtu)",
        "Heat Input (mmBtu)"
    ]

    for col in numeric_columns:
     df[col] = df[col].fillna(0)

    # Fill missing text values with "None"
    text_columns = [
        "Associated Stacks",
        "Secondary Fuel Type",
        "SO2 Controls",
        "NOx Controls",
        "PM Controls",
     "Hg Controls"
    ]

    for col in text_columns:
        df[col] = df[col].fillna("None")


    print("Data loaded successfully!")
    print("Rows:", len(df))
    print("Columns:", len(df.columns))

    # Clean column names
    df.columns = df.columns.str.strip()

    # Display the columns
    print("\nColumns:")
    print(df.columns.tolist())

    # Save a copy of the data
    output_path = os.path.join(
        OUTPUT_DIR,
        "clean_annual_emissions.csv"
    )

    df.to_csv(output_path, index=False)

    print("\nCleaned data saved to:")
    print(output_path)


if __name__ == "__main__":
    clean_epa_pipeline()