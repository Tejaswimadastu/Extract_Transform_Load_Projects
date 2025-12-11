import os
import pandas as pd
def extract_data():
    # Go up one level from /scripts
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Create data/raw folder
    data_dir = os.path.join(base_dir, "data", "raw")
    os.makedirs(data_dir, exist_ok=True)

    # 👉 Path to your downloaded dataset
    source_csv = r"F:\Downloads\archive (1)\WA_Fn-UseC_-Telco-Customer-Churn.csv"

    if not os.path.exists(source_csv):
        raise FileNotFoundError(f"Dataset not found at: {source_csv}")

    # Load dataset
    df = pd.read_csv(source_csv)

    # Save into project structure
    raw_path = os.path.join(data_dir, "churn_raw.csv")
    df.to_csv(raw_path, index=False)

    print(f"✅ Data extracted and saved at: {raw_path}")
    return raw_path

if __name__ == "__main__":
    extract_data()
