#!/usr/bin/env python3
"""
run_pipeline.py
Master script to run the full ETL + Analysis pipeline:

1. Extract  → fetch raw AQ data
2. Transform → create air_quality_transformed.csv
3. Load → insert into Supabase
4. Analysis → generate KPIs, CSVs, visualizations
"""

import subprocess
import sys
import logging
import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

logger = logging.getLogger("pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def run_step(name, command):
    """Run a script step and stop pipeline if it fails."""
    logger.info("▶️  Running step: %s", name)
    result = subprocess.run(command, shell=True)

    if result.returncode != 0:
        logger.error("❌ Step FAILED: %s", name)
        sys.exit(result.returncode)

    logger.info("✅ Step completed: %s\n", name)


def main():
    logger.info("🚀 Starting Full AQ ETL Pipeline")

    # ----------- Validate Required ENV Vars --------------
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
        logger.error("❌ Missing Supabase credentials. Ensure your .env file has SUPABASE_URL and SUPABASE_KEY.")
        sys.exit(1)

    # ----------- Steps ---------------------
    steps = [
        ("Extract",   "python extract.py"),
        ("Transform", "python transform.py"),
        (
            "Load to Supabase",
            "python load.py --input data/staged/air_quality_transformed.csv --batch 200 --retries 2"
        ),
        ("Analysis", "python etl_analysis.py")
    ]

    for step_name, cmd in steps:
        run_step(step_name, cmd)

    logger.info("🎉 PIPELINE COMPLETE — All steps succeeded!")


if __name__ == "__main__":
    main()
