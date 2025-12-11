#!/usr/bin/env python3
"""
etl_analysis.py

Reads air_quality_data from Supabase and produces:
 A. KPI Metrics
 B. City pollution trend report
 C. CSV outputs under data/processed/
 D. PNG visualizations under data/processed/

Usage:
  Ensure SUPABASE_URL and SUPABASE_KEY are set in environment or pass via CLI:
    python etl_analysis.py --supabase-url "..." --supabase-key "..."
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any
import pandas as pd
import numpy as np
from supabase import create_client
import matplotlib.pyplot as plt
from dotenv import load_dotenv
load_dotenv()


# Output folder
OUT_DIR = os.path.join("data", "processed")
os.makedirs(OUT_DIR, exist_ok=True)

# Filenames
SUMMARY_CSV = os.path.join(OUT_DIR, "summary_metrics.csv")
RISK_DIST_CSV = os.path.join(OUT_DIR, "city_risk_distribution.csv")
TRENDS_CSV = os.path.join(OUT_DIR, "pollution_trends.csv")

PM25_HIST = os.path.join(OUT_DIR, "pm25_histogram.png")
RISK_BAR = os.path.join(OUT_DIR, "risk_flags_by_city.png")
HOURLY_LINE = os.path.join(OUT_DIR, "hourly_pm25_trends.png")
SCATTER_PNG = os.path.join(OUT_DIR, "severity_vs_pm25_scatter.png")

# Logging
logging.basicConfig(level=os.environ.get("ETL_LOG_LEVEL", "INFO"))
logger = logging.getLogger("etl_analysis")


def fetch_table_all(supabase, table_name: str) -> pd.DataFrame:
    """
    Fetches all rows from a Supabase table using supabase-py client.
    Tries common response shapes and returns a DataFrame.
    """
    logger.info("Fetching rows from table '%s' ...", table_name)
    try:
        resp = supabase.table(table_name).select("*").execute()
    except Exception as e:
        logger.exception("Supabase query failed: %s", e)
        raise

    # Normalize different client versions/shapes
    data = None
    if isinstance(resp, dict) and "data" in resp:
        data = resp["data"]
    else:
        data = getattr(resp, "data", None)
        if data is None:
            # try tuple-like
            try:
                data = resp[0]
            except Exception:
                data = None

    if not data:
        logger.warning("No rows returned from %s", table_name)
        return pd.DataFrame()

    df = pd.DataFrame(data)
    logger.info("Fetched %d rows, %d columns", len(df), len(df.columns))
    return df


def coerce_and_prepare(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce columns into the expected types and ensure required columns exist.
    """
    # Normalize column name variants
    rename_map = {
        "pm2.5": "pm2_5",
        "PM2_5": "pm2_5",
        "pm_25": "pm2_5",
        "severity": "severity_score",
        "risk_class": "risk_flag",
        "risk_classification": "risk_flag",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df = df.rename(columns={k: v})

    expected = [
        "city", "time", "pm10", "pm2_5", "ozone", "uv_index",
        "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide",
        "aqi_category", "severity_score", "risk_flag", "hour"
    ]
    for c in expected:
        if c not in df.columns:
            df[c] = np.nan

    # Parse time
    try:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
    except Exception:
        df["time"] = pd.to_datetime(df["time"].astype(str), errors="coerce")

    # numeric coercion
    for col in ["pm10", "pm2_5", "ozone", "uv_index", "severity_score", "hour",
                "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalize risk_flag strings (keep None as NaN)
    df["risk_flag"] = df["risk_flag"].astype(object).where(df["risk_flag"].notna(), None)
    df["city"] = df["city"].astype(object).where(df["city"].notna(), None)

    # Drop rows with no city or no time — cannot analyze
    df = df[df["city"].notna() & df["time"].notna()].copy()
    return df


def compute_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    # City with highest avg PM2.5
    grp = df.groupby("city", dropna=True)
    avg_pm25 = grp["pm2_5"].mean().dropna()
    if not avg_pm25.empty:
        top_city_pm25 = avg_pm25.idxmax()
        result["city_highest_avg_pm2_5"] = {"city": top_city_pm25, "avg_pm2_5": float(avg_pm25.max())}
    else:
        result["city_highest_avg_pm2_5"] = None

    # City with highest avg severity_score
    avg_sev = grp["severity_score"].mean().dropna()
    if not avg_sev.empty:
        top_city_sev = avg_sev.idxmax()
        result["city_highest_avg_severity"] = {"city": top_city_sev, "avg_severity": float(avg_sev.max())}
    else:
        result["city_highest_avg_severity"] = None

    # Percentage distribution of risk flags overall
    rf = df["risk_flag"].fillna("Unknown")
    counts = rf.value_counts(dropna=False)
    total = int(counts.sum()) if not counts.empty else 0
    dist = {}
    for k, v in counts.items():
        dist[str(k)] = float(v) / total * 100.0 if total > 0 else 0.0
    result["risk_flag_distribution_percent"] = dist

    # Per-city risk distribution DataFrame
    city_risk = (
        df.assign(risk_flag=rf)
          .groupby(["city", "risk_flag"])
          .size()
          .reset_index(name="count")
    )
    # percentage per city
    city_totals = city_risk.groupby("city")["count"].transform("sum")
    city_risk["pct"] = city_risk["count"] / city_totals * 100.0
    result["city_risk_df"] = city_risk

    # Hour of day with worst avg PM2.5
    if "hour" in df.columns and df["hour"].notna().any():
        hourly = df.groupby("hour")["pm2_5"].mean().dropna()
        if not hourly.empty:
            worst_hour = int(hourly.idxmax())
            result["hour_worst_avg_pm2_5"] = {"hour": worst_hour, "avg_pm2_5": float(hourly.max())}
        else:
            result["hour_worst_avg_pm2_5"] = None
    else:
        df["hour_of_day"] = df["time"].dt.hour
        hourly = df.groupby("hour_of_day")["pm2_5"].mean().dropna()
        if not hourly.empty:
            worst_hour = int(hourly.idxmax())
            result["hour_worst_avg_pm2_5"] = {"hour": worst_hour, "avg_pm2_5": float(hourly.max())}
        else:
            result["hour_worst_avg_pm2_5"] = None

    # attach helper objects
    result["avg_pm25_series"] = avg_pm25
    result["avg_severity_series"] = avg_sev

    return result


def build_trends(df: pd.DataFrame) -> pd.DataFrame:
    # long-format city/time trends with pm2_5, pm10, ozone
    cols = ["city", "time", "pm2_5", "pm10", "ozone"]
    trends = df[cols].copy()
    trends = trends.sort_values(["city", "time"])
    return trends


def save_outputs_and_plots(df: pd.DataFrame, kpis: Dict[str, Any]):
    # 1) summary CSV
    rows = []
    if kpis.get("city_highest_avg_pm2_5"):
        x = kpis["city_highest_avg_pm2_5"]
        rows.append({"metric": "city_highest_avg_pm2_5", "city": x["city"], "value": x["avg_pm2_5"]})
    if kpis.get("city_highest_avg_severity"):
        x = kpis["city_highest_avg_severity"]
        rows.append({"metric": "city_highest_avg_severity", "city": x["city"], "value": x["avg_severity"]})
    if kpis.get("hour_worst_avg_pm2_5"):
        x = kpis["hour_worst_avg_pm2_5"]
        rows.append({"metric": "hour_worst_avg_pm2_5", "hour": x["hour"], "value": x["avg_pm2_5"]})
    # risk distribution overall
    for k, v in kpis.get("risk_flag_distribution_percent", {}).items():
        rows.append({"metric": "risk_flag_percent", "category": k, "value": v})
    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(SUMMARY_CSV, index=False)
    logger.info("Saved summary metrics: %s", SUMMARY_CSV)

    # 2) city risk distribution CSV
    city_risk_df = kpis.get("city_risk_df")
    if city_risk_df is not None and not city_risk_df.empty:
        city_risk_df.to_csv(RISK_DIST_CSV, index=False)
        logger.info("Saved city risk distribution: %s", RISK_DIST_CSV)
    else:
        logger.warning("City risk distribution is empty; skipping CSV save.")

    # 3) trends CSV
    trends_df = build_trends(df)
    trends_df.to_csv(TRENDS_CSV, index=False)
    logger.info("Saved pollution trends: %s", TRENDS_CSV)

    # --- PLOTS ---

    # Histogram of PM2.5
    plt.figure(figsize=(8, 5))
    vals = df["pm2_5"].dropna()
    if not vals.empty:
        plt.hist(vals, bins=30)
        plt.title("Histogram of PM2.5")
        plt.xlabel("PM2.5")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(PM25_HIST)
        plt.close()
        logger.info("Saved PM2.5 histogram: %s", PM25_HIST)
    else:
        logger.warning("No pm2_5 data for histogram.")

    # Bar chart of risk flags per city (stacked)
    if "risk_flag" in df.columns and df["risk_flag"].notna().any():
        pivot = df.pivot_table(index="city", columns="risk_flag", values="time", aggfunc="count", fill_value=0)
        ax = pivot.plot(kind="bar", stacked=True, figsize=(10, 6))
        ax.set_title("Risk flags per city")
        ax.set_ylabel("Count")
        ax.set_xlabel("City")
        plt.tight_layout()
        plt.savefig(RISK_BAR)
        plt.close()
        logger.info("Saved risk flags by city: %s", RISK_BAR)
    else:
        logger.warning("No risk_flag data for risk bar chart.")

    # Line chart of hourly PM2.5 trends (overall plus top 3 cities)
    if "time" in df.columns and df["time"].notna().any():
        df["hour_of_day"] = df["time"].dt.hour
        hourly = df.groupby("hour_of_day")["pm2_5"].mean().reset_index()
        plt.figure(figsize=(9, 5))
        plt.plot(hourly["hour_of_day"], hourly["pm2_5"], marker="o", label="Overall avg")
        top_cities = df["city"].value_counts().head(3).index.tolist()
        for c in top_cities:
            tmp = df[df["city"] == c].groupby(df[df["city"] == c]["time"].dt.hour)["pm2_5"].mean().reindex(range(24), fill_value=np.nan)
            plt.plot(range(24), tmp.values, marker=".", label=c)
        plt.title("Hourly PM2.5 trends")
        plt.xlabel("Hour of day")
        plt.ylabel("PM2.5")
        plt.legend()
        plt.tight_layout()
        plt.savefig(HOURLY_LINE)
        plt.close()
        logger.info("Saved hourly PM2.5 trends: %s", HOURLY_LINE)
    else:
        logger.warning("No time data for hourly trends.")

    # Scatter: severity_score vs pm2_5
    if df["severity_score"].notna().any() and df["pm2_5"].notna().any():
        sub = df.dropna(subset=["severity_score", "pm2_5"])
        plt.figure(figsize=(6, 6))
        plt.scatter(sub["pm2_5"], sub["severity_score"], alpha=0.6, s=20)
        plt.xlabel("PM2.5")
        plt.ylabel("Severity score")
        plt.title("Severity score vs PM2.5")
        plt.tight_layout()
        plt.savefig(SCATTER_PNG)
        plt.close()
        logger.info("Saved severity vs pm2_5 scatter: %s", SCATTER_PNG)
    else:
        logger.warning("Not enough severity_score and pm2_5 data for scatter plot.")


def main():
    parser = argparse.ArgumentParser(description="ETL analysis: fetch Supabase air_quality_data and create reports/plots")
    parser.add_argument("--supabase-url", type=str, help="Supabase URL (optional; overrides env)")
    parser.add_argument("--supabase-key", type=str, help="Supabase key (optional; overrides env)")
    args = parser.parse_args()

    supabase_url = args.supabase_url or os.environ.get("SUPABASE_URL")
    supabase_key = args.supabase_key or os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        logger.error("Supabase credentials missing. Set SUPABASE_URL and SUPABASE_KEY in env or pass via CLI.")
        sys.exit(2)

    supabase = create_client(supabase_url, supabase_key)

    df_raw = fetch_table_all(supabase, "air_quality_data")
    if df_raw.empty:
        logger.error("No data loaded from Supabase table air_quality_data. Exiting.")
        sys.exit(3)

    df = coerce_and_prepare(df_raw)
    kpis = compute_kpis(df)
    save_outputs_and_plots(df, kpis)

    logger.info("ETL analysis complete. Outputs in %s", OUT_DIR)


if __name__ == "__main__":
    main()
