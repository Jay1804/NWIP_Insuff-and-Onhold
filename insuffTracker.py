"""Insufficiency tracker: query, ageing and 'CS Bucket - Insuff'.

Ageing = working days (Mon-Fri, minus holidays) since the Insuff Date, same as the original
'Insuff Ageing' formula (NETWORKDAYS(Insuff Date, TODAY) - 1). If a check has no Insuff Date it
falls back to working days since 'Max 1' (the old 'Ageing' column), then to the case-created ageing.

Buckets: 0-2 3-5 6-7 8-10 11-14 15-30 31-45 46-60 61-90 91-120 121-180 181+
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import tracker_common as tc

SPEC = tc.TrackerSpec(key="insuff", label="Insufficiency", bucket_col="CS Bucket - Insuff", check_status=3,
    aged_from="31-45", threshold=">30 Days",
    blurb=("These pending checks represent a significant compliance and audit risk since mandatory documents are "
           "pending at the candidate. Any check pending more than 30 days will be closed, unless communicated "
           "here to keep them open."),
    ask="Required candidate documents/ details for insufficient checks")


def add_ageing(df: pd.DataFrame, today: pd.Timestamp | None = None) -> pd.DataFrame:
    today = today or pd.Timestamp.today().normalize()
    df = tc.align_headers(df)

    initiation = tc.networkdays(df["Case Created Date"], today)
    df["Ageing (Initiation)"] = initiation.astype("Int64")
    df["Ageing (Initiation) Bucket"] = tc.bucketize(initiation)

    since_last = tc.networkdays(df["Max 1"], today)
    calendar = (today - pd.to_datetime(df["Case Received Date"], errors="coerce")).dt.days
    fallback = since_last.where(df["Client External Code"].astype(str).str.strip() != "3145", calendar)
    df["Ageing"] = fallback.astype("Int64")

    insuff = (tc.networkdays(df["Insuff Date"], today).fillna(fallback).fillna(initiation) - 1).clip(lower=0)
    df["Insuff Ageing"] = insuff.astype("Int64")
    df["Insuff Bucket"] = tc.bucketize(insuff)
    df[SPEC.bucket_col] = tc.bucketize(insuff)
    return tc.finish_frame(df)


def fetch() -> pd.DataFrame:
    return add_ageing(tc.fetch_dataframe(SPEC.sql))


if __name__ == "__main__":
    tc.load_env()
    data = fetch()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else tc.APP_DIR / "output" / f"insuffTracker_{datetime.now():%Y-%m-%d_%H%M}.xlsx"
    tc.write_excel(out, [(SPEC.label, data, SPEC.bucket_col, "")])
    print(out)
