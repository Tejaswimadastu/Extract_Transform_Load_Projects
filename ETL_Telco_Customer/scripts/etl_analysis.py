# etl_analysis.py
import os
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from supabase import create_client

TABLE_NAME = "churn_customers"

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
PLOT_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "plots")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

load_dotenv()


def supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing Supabase credentials")
    return create_client(url, key)


def load_supabase_table():
    client = supabase_client()
    data = client.table(TABLE_NAME).select("*").execute()
    df = pd.DataFrame(data.data)
    return df


def analyze(df):
    summary = {}

    churn_rate = (df["churn"] == "Yes").mean() * 100
    summary["churn_percentage"] = round(churn_rate, 2)

    avg_monthly_by_contract = (
        df.groupby("contract")["monthlycharges"].mean().round(2).to_dict()
    )
    summary["avg_monthly_by_contract"] = avg_monthly_by_contract

    tcounts = df["tenure_group"].value_counts().to_dict()
    summary["tenure_group_counts"] = tcounts

    internet_dist = df["internetservice"].value_counts().to_dict()
    summary["internet_service_distribution"] = internet_dist

    pivot = (
        pd.crosstab(df["tenure_group"], df["churn"])
        .reset_index()
        .to_dict(orient="records")
    )
    summary["pivot_tenure_vs_churn"] = pivot

    return summary


def save_summary(summary_dict):
    rows = []

    for key, value in summary_dict.items():
        rows.append({"metric": key, "value": str(value)})

    summary_df = pd.DataFrame(rows)
    out_path = os.path.join(PROCESSED_DIR, "analysis_summary.csv")
    summary_df.to_csv(out_path, index=False)
    print("Saved analysis summary to:", out_path)


def create_plots(df):
    plt.figure(figsize=(6, 4))
    df.groupby("monthly_charge_segment")["churn"].apply(lambda x: (x == "Yes").mean()).plot(kind="bar")
    plt.title("Churn Rate by Monthly Charge Segment")
    plt.xlabel("Monthly Charge Segment")
    plt.ylabel("Churn Rate")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "churn_rate_by_charge_segment.png"))
    plt.close()

    plt.figure(figsize=(6, 4))
    df["totalcharges"].plot(kind="hist", bins=30)
    plt.title("Distribution of Total Charges")
    plt.xlabel("Total Charges")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "total_charges_histogram.png"))
    plt.close()

    plt.figure(figsize=(6, 4))
    df["contract"].value_counts().plot(kind="bar")
    plt.title("Contract Type Distribution")
    plt.xlabel("Contract Type")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "contract_type_distribution.png"))
    plt.close()

    print("Plots saved under:", PLOT_DIR)


def main():
    print("\n📊 Running ETL Analysis...\n")

    df = load_supabase_table()
    print("Loaded rows from Supabase:", len(df))

    summary = analyze(df)
    save_summary(summary)

    create_plots(df)

    print("\n🎉 Analysis complete! Check data/processed/ for results and charts.\n")


if __name__ == "__main__":
    main()
