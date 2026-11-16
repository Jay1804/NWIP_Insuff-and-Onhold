"""Headless daily run (Task Scheduler / cron): python run_daily.py [--no-mail] [--no-s3] [--no-gemini] [--test-to a@b.com]"""
import argparse
import sys

import delivery as dv
import pipeline
import tracker_common as tc

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mail", action="store_true")
    ap.add_argument("--no-s3", action="store_true")
    ap.add_argument("--no-gemini", action="store_true")
    ap.add_argument("--test-to", help="send every mail to this address instead of the clients")
    a = ap.parse_args()

    tc.load_env()
    data = pipeline.fetch_all()
    res = pipeline.run_pipeline(data, dv.load_saved_distribution(), send_mail=not a.no_mail,
                                upload_s3=not a.no_s3, use_gemini=not a.no_gemini, test_recipient=a.test_to)
    print(res.to_string(index=False))
    failed = res["Mail"].str.startswith("error") | res["S3"].str.contains("failed")
    sys.exit(1 if failed.any() else 0)
