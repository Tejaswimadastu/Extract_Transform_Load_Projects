import os
import pandas as pd

def transform_data(raw_path):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    staged_dir = os.path.join(base_dir, "data", "staged")
    os.makedirs(staged_dir, exist_ok=True)

    df = pd.read_csv(raw_path)

    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")

    for col in ["tenure", "MonthlyCharges", "TotalCharges"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(df[col].median())

    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for c in cat_cols:
        df[c] = df[c].fillna("Unknown").astype(str)

    def tenure_group_label(t):
        try:
            t = float(t)
        except:
            return "Unknown"
        if t <= 12:
            return "New"
        if t <= 36:
            return "Regular"
        if t <= 60:
            return "Loyal"
        return "Champion"

    df["tenure_group"] = df["tenure"].apply(tenure_group_label)

    def monthly_charge_segment(x):
        try:
            x = float(x)
        except:
            return "Unknown"
        if x < 30:
            return "Low"
        if x <= 70:
            return "Medium"
        return "High"

    df["monthly_charge_segment"] = df["MonthlyCharges"].apply(monthly_charge_segment)

    df["has_internet_service"] = df["InternetService"].map({"DSL": 1, "Fiber optic": 1, "No": 0}).fillna(0).astype(int)
    df["is_multi_line_user"] = (df.get("MultipleLines", "") == "Yes").astype(int)
    df["contract_type_code"] = df["Contract"].map({"Month-to-month": 0, "One year": 1, "Two year": 2}).fillna(-1).astype(int)
    df["churn_flag"] = df.get("Churn", "").map({"Yes": 1, "No": 0}).fillna(-1).astype(int)

    for col in ["customerID", "gender"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    staged_path = os.path.join(staged_dir, "churn_transformed.csv")
    df.to_csv(staged_path, index=False)
    print(f"✅ Data transformed and saved at: {staged_path}")
    return staged_path

if __name__ == "__main__":
    from extract import extract_data
    raw_path = extract_data()
    transform_data(raw_path)
