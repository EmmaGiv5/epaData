# What epaData is
# How to install it
# How to configure it
# How to run it
# How to initialize the database
# How to upload data
# How to use the Data Explorer
# Where the data comes from
# What assumptions were made
# Known limitations

## Live CAMPD searches

The existing Search Database and Data Explorer pages can make on-demand,
single-page searches against EPA CAMPD for any U.S. state or the District of
Columbia. Choose a CAMPD dataset, state, optional facility ID for a
by-facility dataset, and (where required) year or date range. Annual searches
are limited to 2015–2024; hourly searches must remain
within 2015-01-01 through 2025-01-01. Results are displayed from the live API
response and are not imported into or saved in the local database. Each
successful page retrieval is recorded in `datasets` and `data_provenance`
with its retrieval time, non-secret query parameters, source endpoint,
reporting year (when applicable), and returned-record count. Use the page
controls to request additional API pages; each page request has its own
provenance entry.

Configure the EPA CAMPD key on the server as `CAMPD_API_KEY` (or
`EPA_API_KEY`) in the environment or `.env` file. The key is sent only from
the server to EPA and is never included in page markup. The live search needs
network access and a valid key; normal local database searches continue to
work independently.

# Requirements

- Python 3.11.17
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- SQLite




# Current Reminders

Have python 3.11 installed on wsl
Open wsl...

## Run to recreate the environment:

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

If needed…
sudo apt install python3.11-venv

	
## To push and pull:
git add .
git commit -m “description”
git push
