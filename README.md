# epaData

## What epaData is

epaData is a Flask web application for searching, exploring, uploading, and downloading environmental emissions data from the U.S. Environmental Protection Agency (EPA).

Features include:

* Searching emissions data through the Search Database page.
* Exploring local annual and hourly emissions datasets.
* Uploading supported data files.
* Retrieving live data through the EPA CAMPD API.
* Downloading supported records as CSV files.
* Tracking dataset metadata and retrieval history.

## How to install it

### Requirements

* Python 3.11.17
* Flask and Flask-SQLAlchemy
* Flask-Migrate and SQLAlchemy
* SQLite for local development, or PostgreSQL/Supabase when configured
* WSL with Ubuntu and Git

### Set up the environment

Open WSL and navigate to the project directory.

Create and activate a virtual environment, then install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If needed, install virtual environment support:

```bash
sudo apt install python3.11-venv
```

## How to configure it

The application uses environment variables for settings such as the Flask secret key, database connection, and EPA API key.

Create a `.env` file in the project root if required by the current configuration:

```dotenv
SECRET_KEY=your-development-secret
DATABASE_URL=your-database-connection-string
CAMPD_API_KEY=your-campd-api-key
```

Use the variable names expected by `app/config.py`. `DATABASE_URL` should point to the intended database; the application may use SQLite when no database URL is configured.

For live CAMPD searches, configure `CAMPD_API_KEY` or the supported alternative `EPA_API_KEY`. Keep credentials private and never commit `.env` to Git.

## How to run it

From the project directory, activate the environment and start Flask:

```bash
source .venv/bin/activate
python run.py
```

Open the local URL printed in the terminal, commonly:

`http://127.0.0.1:5000`

Keep the terminal running while using the application. Press `Ctrl+C` to stop the server.

## How to initialize the database

Check that the application is connected to the intended database before running migrations.

If the project's Alembic configuration is set up for this command, apply migrations with:

```bash
alembic -c migrations/alembic.ini upgrade head
```

Otherwise, use the migration workflow configured for the project.

Database initialization creates the required schema; it does **not** automatically populate emissions records. Data must be imported or uploaded separately. SQLite and Supabase/PostgreSQL databases are separate, so initialize the database your environment actually uses.

## How to upload data

1. Open the Upload page.
2. Select a supported file.
3. Submit it and review the application's response.

The application validates and processes uploads according to its import logic. Supported formats and required columns depend on the implementation. Uploading a file does not necessarily populate every table used by the Data Explorer.

## How to use the Data Explorer

Open the Data Explorer at:

`http://127.0.0.1:5000/explorer/`

Choose a dataset from the **Data Source** dropdown:

* `annual_emissions_facility` — annual records by facility.
* `annual_emissions_state` — annual records by state.
* `hourly_emissions_facility` — hourly records by facility.
* `hourly_emissions_state` — hourly records by state.

Available fields can include state, facility name and ID, year, date, hour, gross load, steam load, CO₂ mass, SO₂ mass, NOₓ mass, and heat input.

Use the available filters, sorting options, and pagination to explore results. Fields and filters depend on the selected dataset. For example, fuel type, unit type, and control technology cannot be reliably filtered when that information is absent from the source table.

The Data Explorer queries **local database records**. Live CAMPD searches are separate and do not automatically save their returned emissions records locally.

## Where the data comes from

epaData uses:

* **EPA CAMPD API:** Live emissions searches performed on demand.
* **Imported emissions datasets:** Local annual facility, annual state, hourly facility, and hourly state tables.
* **User uploads:** Files imported through the Upload page.
* **Metadata and provenance:** Information about datasets and successful data retrievals.

Live CAMPD responses are not automatically imported into the local emissions tables. Dataset metadata and retrieval history are stored separately from emissions records.

## What assumptions were made

* Imported data must have compatible columns and formats.
* The Data Explorer maps recognized source columns to common display fields.
* Annual and hourly records represent different reporting periods and may use different measurement units.
* Facility-level and state-level records represent different aggregation levels.
* Filters depend on the fields available in the selected dataset.
* Live API results, local emissions records, and retrieval metadata are separate.

## Known limitations

* Local searches require the correct database and populated tables.
* Available filters depend on the selected dataset's schema.
* Uploads depend on supported formats, required columns, and file-size limits.
* Live CAMPD searches require network access and a valid API key.
* Live CAMPD results are not automatically saved as local emissions records.
* Data coverage depends on the imported files and available EPA endpoints.
* Downloads currently support CSV; invalid-upload rows do not have a downloadable report.

## Live CAMPD searches

The Search Database and Data Explorer pages support on-demand CAMPD searches for Alabama, Georgia, Kentucky, Mississippi, and Tennessee.

Choose a dataset and state, then provide a facility ID for by-facility datasets and a year or date range where required. Annual searches accept 2015–2025. Hourly searches must remain within 2015-01-01 through 2025-01-01.

Results come directly from the live API and are not saved as local emissions records. Each successful page retrieval is recorded in `datasets` and `data_provenance`, including retrieval time, non-secret query parameters, source endpoint, reporting year when applicable, and returned-record count. Each requested API page receives its own provenance entry.

Configure `CAMPD_API_KEY` or `EPA_API_KEY` in the server environment or `.env` file. The key should never appear in page markup. Local database searches work independently of the live API.

## Data downloads

The Data Download page supports CSV exports for local annual-emissions records, a selected uploaded dataset's annual records, CAMPD retrieval provenance, or one page of live CAMPD results.

Local and live filters depend on the available fields and endpoint. Live searches support state, year or hourly date range, and optional facility ID for by-facility datasets.

Invalid-upload rows are not downloadable because the application does not currently retain a downloadable invalid-record report.



## Current Reminders

### Recreate the WSL environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Push and pull changes

```bash
git pull
git add .
git commit -m "Describe your changes"
git push
```

Before committing, verify that `.env`, database credentials, and API keys are excluded from version control.
