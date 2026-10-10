import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = (
    "https://api.epa.gov/easey/"
    "facilities-mgmt/facilities"
)

headers = {
    "x-api-key": os.environ["CAMPD_API_KEY"],
    "Accept": "application/json",
}

# Start with no optional filters.
response = requests.get(
    url,
    headers=headers,
    timeout=30,
)

print("Status:", response.status_code)
print("Response:", response.text[:3000])

response.raise_for_status()