# extract.py  -- AtmosTrack Air Quality ETL (Extract Step)
import json
import time
import logging
from pathlib import Path
from datetime import datetime
import requests

# -------------------------
# Directory Setup
# -------------------------
BASE_DIR = Path(__file__).resolve().parents[0]
RAW_DIR = BASE_DIR / "data" / "raw"
LOG_DIR = BASE_DIR / "data" / "logs"
RAW_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "extract.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# -------------------------
# API CONFIG
# -------------------------
API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
HOURLY_FIELDS = (
    "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,"
    "sulphur_dioxide,uv_index"
)

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.5

# -------------------------
# City Coordinates
# -------------------------
CITIES = {
    "Delhi": (28.7041, 77.1025),
    "Mumbai": (19.0760, 72.8777),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Kolkata": (22.5726, 88.3639),
}


# -------------------------
# Utility Functions
# -------------------------

def _timestamped_filename(city: str) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe = city.lower().replace(" ", "_")
    return RAW_DIR / f"{safe}_raw_{ts}.json"


def _save_json(data, filepath: Path):
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _call_api_with_retries(url, params):
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Requesting {params['latitude']}, {params['longitude']} (attempt {attempt}/{MAX_RETRIES})")
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            logging.info(f"Status code: {resp.status_code}")

            resp.raise_for_status()
            return resp.json()

        except Exception as exc:
            last_exc = exc
            wait = BACKOFF_FACTOR ** attempt
            logging.warning(f"API attempt {attempt} failed: {exc} | retrying in {wait:.1f}s")
            time.sleep(wait)

    logging.error(f"FAILED after {MAX_RETRIES} attempts — params={params}")
    raise last_exc


# -------------------------
# Extract Function
# -------------------------

def fetch_air_quality():
    """Fetch hourly air quality data for all cities and save raw JSON."""
    saved_files = []

    for city, (lat, lon) in CITIES.items():
        logging.info(f"Fetching data for {city}...")

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": HOURLY_FIELDS,
        }

        try:
            data = _call_api_with_retries(API_URL, params)
        except Exception as exc:
            logging.error(f"[{city}] FAILED to fetch after retries: {exc}")
            continue  # move to next city

        # save raw JSON
        filepath = _timestamped_filename(city)
        try:
            _save_json(data, filepath)
            saved_files.append(filepath)
            logging.info(f"[{city}] Saved → {filepath}")
        except Exception as exc:
            logging.error(f"[{city}] ERROR saving file: {exc}")

    logging.info(f"Extraction completed. Total files saved: {len(saved_files)}")
    return saved_files


# -------------------------
# Run directly
# -------------------------
if __name__ == "__main__":
    print("Running Air Quality Extractor...")
    paths = fetch_air_quality()
    print("Saved files:")
    for p in paths:
        print(" -", p)
