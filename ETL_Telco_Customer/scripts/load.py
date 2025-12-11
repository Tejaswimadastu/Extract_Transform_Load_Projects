import os
import sys
import time
import uuid
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

TABLE_NAME = "churn_customers"
BATCH_SIZE = 200
MAX_RETRIES = 3
BACKOFF = 2

DB_COLUMNS = [
    "customerid",
    "tenure",
    "monthlycharges",
    "totalcharges",
    "churn",
    "internetservice",
    "contract",
    "paymentmethod",
    "tenure_group",
    "monthly_charge_segment",
    "has_internet_service",
    "is_multi_line_user",
    "contract_type_code",
]

def get_supabase_client():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

def find_csv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(script_dir, ".."))
    paths = [
        os.path.join(root, "data", "staged", "churn_transformed.csv"),
        os.path.join(script_dir, "data", "staged", "churn_transformed.csv"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def clean_record(r):
    cleaned = {}
    for k, v in r.items():
        k2 = str(k).strip().lower()
        if k2 in DB_COLUMNS:
            cleaned[k2] = None if pd.isna(v) else v
    if not cleaned.get("customerid"):
        cleaned["customerid"] = str(uuid.uuid4())
    return cleaned

def insert_with_retry(client, records):
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            res = client.table(TABLE_NAME).insert(records).execute()
            if hasattr(res, "error") and res.error:
                raise Exception(res.error)
            return True
        except Exception as e:
            attempt += 1
            wait = BACKOFF ** attempt
            print(f"Insert failed ({e}). Retrying in {wait}s...")
            time.sleep(wait)
    return False

def load_data():
    path = find_csv()
    if not path:
        print("CSV not found.")
        sys.exit(1)

    print("Using CSV:", path)
    df = pd.read_csv(path)

    df.columns = [c.lower() for c in df.columns]  # normalize lowercase

    df = df.where(pd.notnull(df), None)

    client = get_supabase_client()

    total = len(df)
    print("Rows:", total)

    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df.iloc[start:end].to_dict("records")
        batch_clean = [clean_record(r) for r in batch]

        ok = insert_with_retry(client, batch_clean)
        if ok:
            print(f"Inserted rows {start+1}-{end}")
        else:
            print(f"Failed rows {start+1}-{end}")
            break

    print("DONE.")

if __name__ == "__main__":
    load_data()
