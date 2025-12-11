import os
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "churn_raw.csv")
STAGED_PATH = os.path.join(PROJECT_ROOT, "data", "staged", "churn_transformed.csv")

print("Loading files...")
raw = pd.read_csv(RAW_PATH, dtype=str).fillna("")   # keep as strings for exact matching
staged = pd.read_csv(STAGED_PATH, dtype=str).fillna("")

print(f"Raw rows: {len(raw)}, Raw unique rows: {len(raw.drop_duplicates())}")
print(f"Staged rows: {len(staged)}, Staged unique rows: {len(staged.drop_duplicates())}")

# 1) find duplicate rows in staged (rows that appear more than once across all columns)
staged_dup_mask = staged.duplicated(keep=False)
duplicates_staged = staged[staged_dup_mask].copy()
if duplicates_staged.empty:
    print("No duplicated rows in staged (unexpected).")
else:
    # count how many distinct duplicated groups and total duplicated rows
    grouped = duplicates_staged.groupby(list(duplicates_staged.columns))
    dup_groups = grouped.size().reset_index(name="count").sort_values("count", ascending=False)
    print(f"Found {len(dup_groups)} duplicated groups in staged, total duplicated rows: {len(duplicates_staged)}")
    dup_groups.to_csv(os.path.join(os.path.dirname(STAGED_PATH), "staged_duplicate_groups.csv"), index=False)
    print("Wrote staged_duplicate_groups.csv")

# 2) For each duplicated staged group, find the corresponding customerIDs from raw
# Determine the columns used in staged (the transformed columns)
staged_cols = list(staged.columns)

# We'll attempt to find rows in raw that match each duplicated staged row on *all staged columns*
# But raw still has customerID column; we must map by matching staged columns in raw.
if "customerID" not in raw.columns and "customerId" not in raw.columns:
    # try lowercase variants
    possible_id_cols = [c for c in raw.columns if c.lower() == "customerid"]
    id_col = possible_id_cols[0] if possible_id_cols else None
else:
    id_col = "customerID" if "customerID" in raw.columns else "customerId"

if id_col is None:
    print("Warning: could not find customerID column name in raw CSV. Searching raw by everything except known staged columns.")
else:
    print("Found customer id column in raw:", id_col)

# Prepare raw for matching: ensure staged columns exist in raw; if not, convert name casing
raw_cols_lower = {c.lower(): c for c in raw.columns}
staged_to_raw_map = {}
for c in staged_cols:
    lookup = c.lower()
    if lookup in raw_cols_lower:
        staged_to_raw_map[c] = raw_cols_lower[lookup]
    elif c in raw.columns:
        staged_to_raw_map[c] = c
    else:
        staged_to_raw_map[c] = None

missing_in_raw = [k for k,v in staged_to_raw_map.items() if v is None]
if missing_in_raw:
    print("Warning: these staged columns do not exist in raw and will not be used for mapping:", missing_in_raw)

# build a subset of raw that has the columns we can match on
match_raw_cols = [v for v in staged_to_raw_map.values() if v is not None]
raw_subset = raw[[id_col] + match_raw_cols].copy() if id_col else raw[match_raw_cols].copy()
# rename raw subset columns to staged column names for direct comparison
rename_map = {v:k for k,v in staged_to_raw_map.items() if v is not None}
raw_subset = raw_subset.rename(columns=rename_map)

# Now for each duplicate staged group, find matching customerIDs in raw
mappings = []
if not duplicates_staged.empty:
    # group duplicates by their column values (convert to tuple key)
    grouped_iter = duplicates_staged.groupby(staged_cols)
    for key_vals, group_df in grouped_iter:
        # create a boolean mask for raw_subset matching this group's values
        # key_vals may be a single value if staged_cols length is 1, so normalize to tuple
        if not isinstance(key_vals, tuple):
            key_vals = (key_vals,)
        cond = pd.Series([True]*len(raw_subset))
        for col_name, val in zip(staged_cols, key_vals):
            if col_name in raw_subset.columns:
                cond = cond & (raw_subset[col_name].astype(str).fillna("") == str(val))
            else:
                # if raw doesn't have this column, can't filter by it
                pass
        matched = raw_subset[cond]
        matched_ids = matched[id_col].tolist() if id_col and id_col in matched.columns else []
        mappings.append({
            "group_values": dict(zip(staged_cols, key_vals)),
            "staged_count": len(group_df),
            "matched_raw_count": len(matched),
            "customer_ids": matched_ids
        })

    # save mapping to CSV/JSON
    import json
    out_path = os.path.join(os.path.dirname(STAGED_PATH), "duplicate_mapping.json")
    with open(out_path, "w", encoding="utf8") as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)
    print("Wrote mapping of duplicate staged groups -> raw customerIDs to:", out_path)
    # print a short sample
    for m in mappings[:10]:
        print("Group staged_count=", m["staged_count"], "matched_raw_count=", m["matched_raw_count"])
        print(" customer_ids sample:", m["customer_ids"][:5])
else:
    print("No duplicates in staged to map.")

# 3) Show staged rows that do not exist uniquely in raw (sanity)
# Merge staged unique rows back to raw (on staged columns that exist in raw) to see unmatched
unique_staged = staged.drop_duplicates()
merge_cols = [c for c in staged_cols if staged_to_raw_map.get(c) is not None]
if merge_cols:
    merged = unique_staged.merge(raw, left_on=merge_cols, right_on=[staged_to_raw_map[c] for c in merge_cols], how="left", indicator=True)
    unmatched = merged[merged['_merge']=="left_only"]
    print("Number of staged-unique rows with NO matching raw row on matched columns:", len(unmatched))
    if len(unmatched) > 0:
        unmatched.head(10).to_csv(os.path.join(os.path.dirname(STAGED_PATH), "staged_unmatched_sample.csv"), index=False)
        print("Saved sample unmatched staged rows to staged_unmatched_sample.csv")
else:
    print("No common columns to attempt matching unique staged -> raw.")

print("Diagnosis complete.")
