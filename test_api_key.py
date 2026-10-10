import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("CAMPD_API_KEY") or os.getenv("EPA_API_KEY")

if not api_key:
    print("FAIL: API key was not found in .env")
    raise SystemExit(1)

url = (
    "https://api.epa.gov/easey/"
    "emissions-mgmt/emissions/apportioned/hourly/by-facility"
)

params = {
    "api_key": api_key,
    "stateCode": "AL|GA|KY|MI",
    "beginDate": "2015-01-01",
    "endDate": "2025-01-02",
    "page": 1,
    "perPage": 30,
}

try:
    response = requests.get(url, params=params, timeout=30)

    print("HTTP status:", response.status_code)

    if response.status_code == 200:
        print("SUCCESS: The request was accepted.")
        print("Response preview:", response.text[:500])
    elif response.status_code in (401, 403):
        print("AUTHENTICATION FAILED: Check your API key.")
        print("Response:", response.text[:300])
    else:
        print("Request failed. Check the endpoint and parameters.")
        print("Response:", response.text[:500])

except requests.RequestException as exc:
    print("CONNECTION ERROR:", exc)