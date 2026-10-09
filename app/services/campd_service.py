import os
import requests

api_key = os.getenv("EPA_API_KEY")

if not api_key:
    raise RuntimeError("EPA_API_KEY is not configured.")

response = requests.get("https://api.epa.gov/easey/streaming-services/facilities",
                        params={"api_key": api_key},
                        timeout=30,
)
response.raise_for_status()  
date = response.json()
