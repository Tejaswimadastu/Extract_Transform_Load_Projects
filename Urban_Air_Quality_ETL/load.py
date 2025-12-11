#!/usr/bin/env python3
"""
Load transformed air-quality CSV into Supabase.
"""

import os
import time
import argparse
import logging
from typing import List, Dict, Any, Iterable
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

# ---------------- CONFIG ----------------
DEFAULT_INPUT = "data/staged/air_quality_transformed.csv"
BATCH_SIZE = 200
RETRY_ATTEMPTS = 2
RETRY_BACKOFF = 2.0  # exponential

logger = logging.getLogger("load")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- HELPERS ----------------
def chunks(lst, n):
    """Yield successive n-sized chunks."""
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def sanitize_value(v):
    """None, NaN, numpy types → JSON friendly."""
    try:
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
    except:
        pass
    # pandas NA
    import pandas as pd
    if pd.isna(v):
        return None
    # numpy scalar → python scalar
    try:
        if hasattr(v, "item"):
            return v.item()
    except:
        pass
    return v

def row_to_insertable(row: dict) -> dict:
    """Convert row to Supabase JSON-compatible dict."""
    out = {}
    for k, v in row.items():
        if pd.isna(v):
            out[k] = None
        else:
            # Convert Timestamp → ISO
            if hasattr(v, "isoformat"):
                out[k] = v.isoformat()
            else:
                out[k] = sanitize_value(v)
    return out

# ---------------- MAIN LOADER ----------------
def load_csv_to_supabase(input_csv: str,
                         batch_size: int = BATCH_SIZE,
                         retry_attempts: int = RETRY_ATTEMPTS,
                         supabase_url: str = None,
                         supabase_key: str = None):

    supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
    supabase_key = supabase_key or os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env or CLI args.")

    logger.info(f"Connecting to Supabase: {supabase_url}")
    supabase = create_client(supabase_url, supabase_key)

    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"CSV not found: {input_csv}")

    df = pd.read_csv(input_csv, parse_dates=["time"])
    logger.info(f"Loaded {len(df)} rows.")

    # Ensure all expected columns exist
    expected = [
        "city", "time", "pm10", "pm2_5", "carbon_monoxide",
        "nitrogen_dioxide", "sulphur_dioxide", "ozone",
        "uv_index", "aqi_category", "severity_score",
        "risk_flag", "hour"
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = None

    df = df[expected]

    records = [row_to_insertable(row) for _, row in df.iterrows()]

    total_inserted = 0
    total_failed = 0

    for batch_idx, batch in enumerate(chunks(records, batch_size), start=1):
        logger.info(f"Inserting batch {batch_idx} (size={len(batch)})")

        success = False
        for attempt in range(1, retry_attempts + 2):
            try:
                resp = supabase.table("air_quality_data").insert(batch).execute()
                logger.info(f"Batch {batch_idx} inserted.")
                total_inserted += len(batch)
                success = True
                break
            except Exception as e:
                logger.warning(f"Batch {batch_idx} attempt {attempt} failed: {e}")
                if attempt <= retry_attempts:
                    time.sleep(RETRY_BACKOFF ** attempt)
                else:
                    logger.error(f"Batch {batch_idx} failed after max retries.")
                    total_failed += len(batch)

    logger.info(f"Insert complete. Inserted={total_inserted}, Failed={total_failed}")
    return {"inserted": total_inserted, "failed": total_failed}

# ---------------- CLI ----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load air quality CSV into Supabase.")
    parser.add_argument("--input", type=str, default=DEFAULT_INPUT)
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--retries", type=int, default=RETRY_ATTEMPTS)
    parser.add_argument("--supabase-url", type=str, help="Override .env URL")
    parser.add_argument("--supabase-key", type=str, help="Override .env KEY")

    args = parser.parse_args()

    load_csv_to_supabase(
        input_csv=args.input,
        batch_size=args.batch,
        retry_attempts=args.retries,
        supabase_url=args.supabase_url,
        supabase_key=args.supabase_key
    )
