import os
import pandas as pd

# GitHub CSV
GITHUB_CSV_URL = "https://raw.githubusercontent.com/EmmaGiv5/epaData/main/CAMPD_Data_NEW/traci_2_2.csv"

# Output location
OUTPUT_DIR = "data/seed"


def clean_epa_pipeline():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading TRACI data from GitHub...")

    try:
        df = pd.read_csv(GITHUB_CSV_URL, low_memory=False)

        # 1. Clean column names
        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )

        # 2. Remove completely empty rows and columns
        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")

        # 3. Remove duplicate records
        df = df.drop_duplicates()

        # 4. Clean text values
        text_columns = df.select_dtypes(
            include=["object", "string"]
        ).columns

        for col in text_columns:
            df[col] = df[col].astype("string").str.strip()

            # Replace empty strings with missing values
            df[col] = df[col].replace(
                ["", "NA", "N/A", "NULL", "null"],
                pd.NA
            )

        # 5. Convert columns that contain numeric data
        for col in df.columns:
            if df[col].dtype == "object":
                converted = pd.to_numeric(
                    df[col].str.replace(",", "", regex=False),
                    errors="coerce"
                )

                # Only convert if every nonmissing value is numeric
                if df[col].notna().sum() > 0 and (
                    converted.notna().sum() == df[col].notna().sum()
                ):
                    df[col] = converted

        # 6. Remove columns that contain only missing values
        df = df.dropna(axis=1, how="all")

        # 7. Reset row numbering
        df = df.reset_index(drop=True)

        # 8. Save cleaned dataset
        output_path = os.path.join(
            OUTPUT_DIR,
            "clean_traci_2_2.csv"
        )

        df.to_csv(output_path, index=False)

        print("\nTRACI data cleaned successfully!")
        print("Rows:", len(df))
        print("Columns:", len(df.columns))
        print("Duplicates removed.")
        print("Empty rows and columns removed.")

        print("\nFinal columns:")
        print(df.columns.tolist())

        print("\nSaved to:", output_path)

    except Exception as e:
        print("Error processing TRACI data:", e)


if __name__ == "__main__":
    clean_epa_pipeline()