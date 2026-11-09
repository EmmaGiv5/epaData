import os
import os.makedirs
import os.path.join
import os.path.exists 
import panddas as pd
from datetime import datetime

#Define relative directories
RAW_DIR = "data/raw"
SEED_DIR = "data/seed"

def clean_epa_pipeline():
    os.makedirs(SEED_DIR, exist_ok=True)
    
    #Track invalid records for data quality reporting
    rejected_records = []
    datasets_metadata = []

    #PROCESS FACILITIES & UNITS
    fac_path = os.path.join(RAW_DIR, "facility-2025.csv")
    if os.path.exists(fac_path):
        df_fac = pd.read_csv(fac_path)
        total_raw_fac = len(df_fac)
        df_fac.columns = df_fac.columns.str.strip().str.lower().str.replace(' ', '_')

        #Validate facilities (Facility ID and State are required)
        fac_invalid_mask = df_fac['facility_id'].isna() | df_fac['state'].isna()
        if fac_invalid_mask.any():
            bad_fac = df_fac[fac_invalid_mask].copy()
            bad_fac['rejection_reason'] = 'Missing Facility ID or State'
            rejected_records.append(bad_fac)
        
        df_fac_clean = df_fac[~fac_invalid_mask].copy()

        #Clean basic text fields
        df_fac_clean['state'] = df_fac_clean['state'].astype(str).str.upper().str.strip()
        df_fac_clean['facility_name'] = df_fac_clean['facility_name'].astype(str).str.strip()

        # --- A. Extract Clean Facilities Table ---
        facilities_cols = [
            'facility_id', 'facility_name', 'state', 'county', 
            'latitude', 'longitude', 'source_category'
        ]
        facilities_cols = [c for c in facilities_cols if c in df_fac_clean.columns]
        facilities_df = df_fac_clean[facilities_cols].drop_duplicates(subset=['facility_id'])
        facilities_df.to_csv(os.path.join(SEED_DIR, 'clean_facilities.csv'), index=False)

        # --- B. Extract Clean Units Table ---
        units_cols = [
            'facility_id', 'unit_id', 'unit_type', 
            'primary_fuel_info', 'secondary_fuel_info',
            'so2_controls', 'nox_controls', 'pm_controls',
            'operating_date', 'retirement_date'
        ]
        units_cols = [c for c in units_cols if c in df_fac_clean.columns]
        units_df = df_fac_clean[units_cols].drop_duplicates(subset=['facility_id', 'unit_id'])
        
        #Clean text & fill defaults for null controls/fuels
        text_cols_to_fill = ['primary_fuel_info', 'secondary_fuel_info', 'so2_controls', 'nox_controls', 'pm_controls']
        for col in text_cols_to_fill:
            if col in units_df.columns:
                units_df[col] = units_df[col].fillna('None').astype(str).str.strip()

        units_df.to_csv(os.path.join(SEED_DIR, 'clean_units.csv'), index=False)

        #Record Facility Dataset Metadata
        datasets_metadata.append({
            'dataset_name': 'CAMPD Facility & Unit Attributes',
            'data_source': 'EPA CAMPD',
            'reporting_year': 2025,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'facility-2025.csv',
            'raw_records_count': total_raw_fac,
            'accepted_records_count': len(df_fac_clean),
            'rejected_records_count': fac_invalid_mask.sum(),
            'notes': 'Facilities and unit capacity attributes processed successfully.'
        })


    #PROCESS ANNUAL EMISSIONS RECORDS
    emiss_path = os.path.join(RAW_DIR, "emissions-2025.csv")
    if os.path.exists(emiss_path):
        df_emiss = pd.read_csv(emiss_path)
        total_raw_emiss = len(df_emiss)
        df_emiss.columns = df_emiss.columns.str.strip().str.lower().str.replace(' ', '_')

        #Map column name variants
        if 'year' in df_emiss.columns and 'reporting_year' not in df_emiss.columns:
            df_emiss.rename(columns={'year': 'reporting_year'}, inplace=True)

        #Validate annual records (Facility ID and Unit ID are required keys)
        emiss_invalid_mask = df_emiss['facility_id'].isna() | df_emiss['unit_id'].isna()
        if emiss_invalid_mask.any():
            bad_emiss = df_emiss[emiss_invalid_mask].copy()
            bad_emiss['rejection_reason'] = 'Missing Facility ID or Unit ID'
            rejected_records.append(bad_emiss)
            
        df_emiss_clean = df_emiss[~emiss_invalid_mask].copy()

        #Standardize and clean numerical values
        numeric_targets = [
            'operating_time', 'gross_load', 'steam_load', 'heat_input',
            'co2_mass', 'so2_mass', 'nox_mass'
        ]
        
        for col in df_emiss_clean.columns:
            for target in numeric_targets:
                if target in col:
                    df_emiss_clean[col] = pd.to_numeric(df_emiss_clean[col], errors='coerce').fillna(0.0)

        df_emiss_clean.to_csv(os.path.join(SEED_DIR, 'clean_annual_records.csv'), index=False)

        #Record Emissions Dataset Metadata
        datasets_metadata.append({
            'dataset_name': 'CAMPD Annual Emissions & Operating Data',
            'data_source': 'EPA CAMPD',
            'reporting_year': 2025,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'emissions-2025.csv',
            'raw_records_count': total_raw_emiss,
            'accepted_records_count': len(df_emiss_clean),
            'rejected_records_count': emiss_invalid_mask.sum(),
            'notes': 'Annual emissions, operating hours, and generation processed successfully.'
        })


    #PROCESS TRACI FACTORS
    traci_path = os.path.join(RAW_DIR, "traci_2_2.xlsx")
    if os.path.exists(traci_path):
        df_traci = pd.read_excel(traci_path)
        df_traci.columns = df_traci.columns.str.strip().str.lower().str.replace(' ', '_')
        df_traci.to_csv(os.path.join(SEED_DIR, 'clean_traci_factors.csv'), index=False)


    #Export Dataset Provenance Metadata Table
    if datasets_metadata:
        metadata_df = pd.DataFrame(datasets_metadata)
        metadata_df.to_csv(os.path.join(SEED_DIR, 'clean_datasets_metadata.csv'), index=False)

    #Export Quality & Rejection Report
    if rejected_records:
        report_df = pd.concat(rejected_records, ignore_index=True)
        report_df.to_csv(os.path.join(SEED_DIR, 'rejected_records_report.csv'), index=False)
    else:
        pd.DataFrame(columns=['facility_id', 'unit_id', 'rejection_reason']).to_csv(
            os.path.join(SEED_DIR, 'rejected_records_report.csv'), index=False
        )

    print("Data cleaning pipeline complete! Generated seed CSVs and provenance metadata in data/seed/")

if __name__ == "__main__":
    clean_epa_pipeline()
