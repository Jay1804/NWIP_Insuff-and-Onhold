"""On-Hold tracker: query, ageing and 'CS Bucket - Onhold'.

Ageing = working days (Mon-Fri, minus holidays) since 'Case Created Date', i.e. the original
'Ageing (Initiation)' column (NETWORKDAYS(Case Created Date, TODAY)) which the old
'CS Bucket - Onhold' formula was based on.

Buckets: 0-2 3-5 6-7 8-10 11-14 15-30 31-45 46-60 61-90 91-120 121-180 181+
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import tracker_common as tc

SPEC = tc.TrackerSpec(key="onhold", label="On-Hold", bucket_col="CS Bucket - Onhold", check_status=2,
    aged_from="61-90", threshold=">60 Working Days",
    blurb=("Any case held at your request for more than 60 working days will be closed, unless communicated here to keep "
           "them in unworkable. These also represent significant compliance risk."),
    ask="Go-ahead for on-hold checks")


def add_ageing(df: pd.DataFrame, today: pd.Timestamp | None = None) -> pd.DataFrame:
    today = today or pd.Timestamp.today().normalize()
    df = tc.align_headers(df)

    initiation = tc.networkdays(df["Case Created Date"], today)
    df["Ageing (Initiation)"] = initiation.astype("Int64")
    df["Ageing (Initiation) Bucket"] = tc.bucketize(initiation)
    df[SPEC.bucket_col] = tc.bucketize(initiation)
    return tc.finish_frame(df)


def fetch() -> pd.DataFrame:
    return add_ageing(tc.fetch_dataframe(SPEC.sql))


if __name__ == "__main__":
    tc.load_env()
    data = fetch()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else tc.APP_DIR / "output" / f"onholdTracker_{datetime.now():%Y-%m-%d_%H%M}.xlsx"
    tc.write_excel(out, [(SPEC.label, data, SPEC.bucket_col, "")])
    print(out)
