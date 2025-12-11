# transform.py
"""
Transform step for AtmosTrack Open-Meteo Air Quality ETL.

Produces a single CSV:
  data/staged/air_quality_transformed.csv

It expects per-city raw JSON files under data/raw/ with names like:
  delhi_raw_20251211T102233Z.json

Handles Open-Meteo hourly structure:
{
  "hourly": {
     "time": ["2025-12-11T00:00", ...],
     "pm10": [...],
     "pm2_5": [...],
     ...
  },
  ...
}
"""
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parents[0]
RAW_DIR = BASE_DIR / "data" / "raw"
STAGED_DIR = BASE_DIR / "data" / "staged"
STAGED_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = STAGED_DIR / "air_quality_transformed.csv"

# pollutant keys we want in final output (normalize to these column names)
TARGET_POLLUTANTS = [
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "uv_index",
]

# tolerant key-name variants mapping -> normalized name
KEY_VARIANTS = {
    "pm10": ["pm10", "pm_10", "pm-10"],
    "pm2_5": ["pm2_5", "pm_2_5", "pm2.5", "pm25", "pm_25"],
    "carbon_monoxide": ["carbon_monoxide", "co", "carbonmonoxide"],
    "nitrogen_dioxide": ["nitrogen_dioxide", "no2", "nitrogendioxide"],
    "sulphur_dioxide": ["sulphur_dioxide", "so2", "sulphurdioxide"],
    "ozone": ["ozone", "o3"],
    "uv_index": ["uv_index", "uvi", "uvindex"],
    "time": ["time", "timestamp", "datetime"],
}

# -------------------------
# helper functions
# -------------------------
def _pick_key(d: dict, variants: List[str]) -> Optional[str]:
    """Return the first matching key from d for any variant; else None."""
    for v in variants:
        if v in d:
            return v
    # try lower-cased match
    lower_keys = {k.lower(): k for k in d.keys()}
    for v in variants:
        if v.lower() in lower_keys:
            return lower_keys[v.lower()]
    return None

def _normalize_hourly_json(obj: dict):
    """
    Given parsed JSON for one file, try to produce a DataFrame with columns:
      time, pm10, pm2_5, carbon_monoxide, nitrogen_dioxide, sulphur_dioxide, ozone, uv_index
    Returns (city_name, df) or (None, None) if can't parse
    """
    # Many Open-Meteo responses have top-level 'hourly' dict with arrays
    if "hourly" in obj and isinstance(obj["hourly"], dict):
        h = obj["hourly"]
        # find time key
        tkey = _pick_key(h, KEY_VARIANTS["time"])
        if tkey is None:
            return None, None
        time_arr = h[tkey]
        n = len(time_arr)
        out = {"time": time_arr}
        # for each target pollutant try to find a key in hourly
        for tgt in TARGET_POLLUTANTS:
            variants = KEY_VARIANTS.get(tgt, [tgt])
            found = _pick_key(h, variants)
            if found and isinstance(h.get(found), (list, tuple)):
                arr = h.get(found)
                # ensure length matches, else pad/truncate to n
                if len(arr) != n:
                    # try to coerce: if scalar repeat
                    if isinstance(arr, (int, float)):
                        arr2 = [arr] * n
                    else:
                        # pad with NAs or trim
                        arr2 = list(arr)[:n] + [None] * max(0, n - len(arr))
                    out[tgt] = arr2
                else:
                    out[tgt] = arr
            else:
                out[tgt] = [None] * n
        # city detection: try 'city' or 'metadata' else None
        city = None
        # some Open-Meteo responses include 'latitude'/'longitude' but not city — we'll extract from input filename later if needed
        if "city" in obj:
            city = obj.get("city")
        elif "meta" in obj and isinstance(obj["meta"], dict) and "city" in obj["meta"]:
            city = obj["meta"].get("city")
        df = pd.DataFrame(out)
        return city, df

    # alternative shape: list of hourly records under 'results' or top-level list
    if isinstance(obj, list):
        # assume each entry may have 'hourly' or directly pollutant values with time
        records = []
        for rec in obj:
            if isinstance(rec, dict) and "hourly" in rec and isinstance(rec["hourly"], dict):
                # flatten the same as above (unlikely)
                c, df = _normalize_hourly_json(rec)
                if df is not None:
                    return c, df
            # if entry has measurements list with 'date' / 'value'
            # falling back: can't easily normalize generic lists -> skip
        return None, None

    # guarded fallback: sometimes API returns structure with 'data' or 'results' list containing hourly arrays per location
    for container_key in ("results", "data"):
        if container_key in obj and isinstance(obj[container_key], list) and len(obj[container_key]) > 0:
            # try to find first element with 'hourly'
            for item in obj[container_key]:
                c, df = _normalize_hourly_json(item)
                if df is not None:
                    # prefer item['city'] if present
                    city = item.get("city") or c
                    return city, df
    return None, None

def _pm25_to_aqi_category(pm25_val: float) -> Optional[str]:
    if pm25_val is None or (isinstance(pm25_val, float) and np.isnan(pm25_val)):
        return None
    try:
        v = float(pm25_val)
    except Exception:
        return None
    if v <= 50:
        return "Good"
    if v <= 100:
        return "Moderate"
    if v <= 200:
        return "Unhealthy"
    if v <= 300:
        return "Very Unhealthy"
    return "Hazardous"

def _compute_severity_score(row):
    # severity = (pm2_5 * 5) + (pm10 * 3) +
    #            (nitrogen_dioxide * 4) + (sulphur_dioxide * 4) +
    #            (carbon_monoxide * 2) + (ozone * 3)
    def val(x):
        return 0.0 if pd.isna(x) else float(x)
    return (
        val(row.get("pm2_5")) * 5.0 +
        val(row.get("pm10")) * 3.0 +
        val(row.get("nitrogen_dioxide")) * 4.0 +
        val(row.get("sulphur_dioxide")) * 4.0 +
        val(row.get("carbon_monoxide")) * 2.0 +
        val(row.get("ozone")) * 3.0
    )

def _risk_from_severity(score: float) -> str:
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return "Unknown"
    if score > 400:
        return "High Risk"
    if score > 200:
        return "Moderate Risk"
    return "Low Risk"

# -------------------------
# main transform function
# -------------------------
def transform_all(raw_dir: Path = RAW_DIR, output_csv: Path = OUTPUT_CSV) -> Path:
    """
    Read all *_raw_*.json files from raw_dir, transform & append into one CSV.
    Returns Path to written CSV.
    """
    raw_files = sorted(raw_dir.glob("*_raw_*.json"))
    if not raw_files:
        raise FileNotFoundError(f"No raw files found in {raw_dir}")

    all_dfs = []
    for f in raw_files:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"WARN: skipping {f} - failed to parse JSON: {exc}")
            continue

        # try to extract city from file name: prefix before "_raw_"
        fname = f.stem
        city_from_name = None
        if "_raw_" in fname:
            city_from_name = fname.split("_raw_")[0].replace("_", " ").title()

        city_in_json, df_hourly = _normalize_hourly_json(obj)
        if df_hourly is None:
            print(f"WARN: skipping {f} - unrecognized JSON shape")
            continue

        city = city_in_json or city_from_name or "unknown"

        # normalize column names to our target pollutant names
        rename_map = {}
        for col in list(df_hourly.columns):
            lc = col.lower().strip()
            # direct matches
            if lc in ("time", "timestamp", "datetime"):
                rename_map[col] = "time"
                continue
            # match variants for pollutants
            for norm, variants in KEY_VARIANTS.items():
                if lc in [v.lower() for v in variants]:
                    rename_map[col] = norm
                    break
        # apply rename
        df_hourly = df_hourly.rename(columns=rename_map)

        # ensure all target pollutant columns exist
        for tgt in TARGET_POLLUTANTS:
            if tgt not in df_hourly.columns:
                df_hourly[tgt] = np.nan

        # convert time column to datetime
        df_hourly["time"] = pd.to_datetime(df_hourly["time"], errors="coerce")

        # coerce pollutants to numeric
        for tgt in TARGET_POLLUTANTS:
            df_hourly[tgt] = pd.to_numeric(df_hourly[tgt], errors="coerce")

        # drop rows where all pollutant readings are missing
        pollutant_cols = TARGET_POLLUTANTS
        df_hourly = df_hourly[~df_hourly[pollutant_cols].isna().all(axis=1)].copy()

        if df_hourly.empty:
            print(f"INFO: {f} produced zero rows after dropping empty pollutant rows")
            continue

        # add city column and hour
        df_hourly["city"] = city
        df_hourly["hour"] = df_hourly["time"].dt.hour

        # derived features
        df_hourly["aqi_pm25"] = df_hourly["pm2_5"].apply(_pm25_to_aqi_category)
        df_hourly["severity_score"] = df_hourly.apply(_compute_severity_score, axis=1)
        df_hourly["risk_classification"] = df_hourly["severity_score"].apply(_risk_from_severity)

        # keep only desired columns in required order
        cols_out = ["city", "time"] + TARGET_POLLUTANTS + ["hour", "aqi_pm25", "severity_score", "risk_classification"]
        df_out = df_hourly[cols_out].copy()

        all_dfs.append(df_out)

    if not all_dfs:
        raise RuntimeError("No transformed rows produced from raw files")

    df_all = pd.concat(all_dfs, ignore_index=True)
    # sort for neatness
    df_all = df_all.sort_values(["city", "time"]).reset_index(drop=True)

    # final write
    df_all.to_csv(output_csv, index=False)
    print(f"Transform complete. Wrote {len(df_all)} rows to {output_csv}")
    return output_csv

# -------------------------
# convenient CLI
# -------------------------
if __name__ == "__main__":
    try:
        path = transform_all()
    except Exception as e:
        print("Error:", e)
        raise
