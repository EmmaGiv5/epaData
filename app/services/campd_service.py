import os
import requests # allows us to connect to the API websites

api_key = os.getenv("EPA_API_KEY")

if not api_key: # in case the key doesn't exist 
    raise RuntimeError("EPA_API_KEY is not configured.")

response = requests.get("https://api.epa.gov/easey/streaming-services/facilities",
                        params={"api_key": api_key},
                        timeout=30,
)

response.raise_for_status()  
date = response.json()
