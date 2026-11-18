"""Gemini insights, distribution list handling, SMTP mail and S3 upload."""
from __future__ import annotations

import datetime as dt
import html
import mimetypes
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

import tracker_common as tc

S3_BUCKET = "amzn-s3-mis"
S3_PREFIX = "NWIP_HUB"
DIST_PATH = tc.APP_DIR / "distribution_list.csv"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
AGED_BUCKETS = ["31-45", "46-60", "61-90", "91-120", "121-180", "181+"]


# ------------------------------------------------------------------ distribution
def _split(v) -> list[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return []
    return [x for x in re.split(r"[;,\s]+", str(v).strip()) if x and x.lower() != "nan"]


def normalise_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Accepts columns Client/Client Name/Company Name, To/Email, CC (any case). Returns Client, To, CC."""
    cols = {re.sub(r"[^a-z]", "", str(c).lower()): c for c in df.columns}

    def pick(*aliases):
        for a in aliases:
            if a in cols:
                return cols[a]

    c_client = pick("client", "clientname", "companyname", "company")
    c_to = pick("to", "toemail", "toemails", "email", "emails", "recipients")
    c_cc = pick("cc", "ccemail", "ccemails")
    if not c_client or not c_to:
        raise ValueError("Distribution list needs a client column (Client / Client Name / Company Name) "
                         "and a To column (To / Email). Optional: CC.")
    out = pd.DataFrame({
        "Client": df[c_client].astype(str).str.strip(),
        "To": df[c_to].map(lambda v: "; ".join(_split(v))),
        "CC": df[c_cc].map(lambda v: "; ".join(_split(v))) if c_cc else "",
    })
    return out[(out["Client"] != "") & (out["Client"].str.lower() != "nan")].reset_index(drop=True)


def read_distribution_file(file) -> pd.DataFrame:
    name = getattr(file, "name", str(file)).lower()
    df = pd.read_csv(file, dtype=str) if name.endswith(".csv") else pd.read_excel(file, dtype=str)
    return normalise_distribution(df)


def load_saved_distribution() -> pd.DataFrame:
    if DIST_PATH.exists():
        return normalise_distribution(pd.read_csv(DIST_PATH, dtype=str))
    return pd.DataFrame({"Client": pd.Series(dtype=str), "To": pd.Series(dtype=str), "CC": pd.Series(dtype=str)})


def save_distribution(df: pd.DataFrame) -> None:
    normalise_distribution(df).to_csv(DIST_PATH, index=False)


def invalid_emails(df: pd.DataFrame) -> list[str]:
    return sorted({e for col in ("To", "CC") for v in df[col] for e in _split(v) if not _EMAIL_RE.match(e)})


def recipients_for(dist: pd.DataFrame, client: str) -> tuple[list[str], list[str]]:
    rows = dist[dist["Client"].str.casefold() == client.strip().casefold()]
    to = list(dict.fromkeys(e for v in rows["To"] for e in _split(v)))
    cc = list(dict.fromkeys(e for v in rows["CC"] for e in _split(v) if e not in to))
    return to, cc


# ----------------------------------------------------------------------- insights
def _stats(label: str, p: pd.DataFrame) -> str:
    if p.empty:
        return f"{label}: no open checks."
    total = int(p.loc["Grand Total", "Grand Total"])
    body = p.drop(index="Grand Total")
    aged = int(body[AGED_BUCKETS].to_numpy().sum())
    buckets = ", ".join(f"{b}: {int(p.loc['Grand Total', b])}" for b in tc.BUCKET_ORDER)
    oldest = int(p.loc["Grand Total", "181+"])
    rows = []
    for n, r in body.sort_values("Grand Total", ascending=False).head(10).iterrows():
        rows.append(f"    - {n}: total {int(r['Grand Total'])}, older than 30 days {int(r[AGED_BUCKETS].sum())}, "
                    f"older than 90 days {int(r[['91-120', '121-180', '181+']].sum())}, 181+ days {int(r['181+'])}")
    return (f"{label}: total {total}; older than 30 working days {aged} ({aged * 100 // max(total, 1)}%); "
            f"181+ days {oldest}.\n  Bucket counts -> {buckets}.\n  Check types (largest first):\n" + "\n".join(rows))


def rule_based_insights(client: str, pivots: list[tuple[str, pd.DataFrame]]) -> str:
    lines = []
    for label, p in pivots:
        if p.empty:
            lines.append(f"{label}: no open checks for {client}.")
            continue
        total = int(p.loc["Grand Total", "Grand Total"])
        body = p.drop(index="Grand Total")
        aged = int(body[AGED_BUCKETS].to_numpy().sum())
        top = body["Grand Total"].idxmax()
        lines.append(f"{label}: {total} open check(s); {aged} ({aged * 100 // max(total, 1)}%) are older than "
                     f"30 working days. Largest group: {top} ({int(body.loc[top, 'Grand Total'])}).")
        if int(p.loc["Grand Total", "181+"]):
            lines.append(f"{label}: {int(p.loc['Grand Total', '181+'])} check(s) are 181+ days old and need urgent closure.")
    return "\n".join(f"- {l}" for l in lines)


def generate_insights(client: str, pivots: list[tuple[str, pd.DataFrame]], use_gemini: bool = True) -> tuple[str, str]:
    """Returns (text, source). Only aggregate counts are sent to Gemini - no candidate-level data."""
    key = tc.env("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not use_gemini or not key:
        return rule_based_insights(client, pivots), "rule-based (Gemini off or no key)"
    prompt = (
        "You are a senior operations analyst at a background-verification company writing the 'Insights' section "
        f"of a report for the client '{client}'. Below are aggregate ageing figures (working days) of their open "
        "Insufficiency and/or On-Hold checks. IMPORTANT: the reader sees only a one-row bucket-count table per "
        "category and your bullets - no check-level table - so every bullet must be self-explanatory: say whether a "
        "number refers to Insufficiency or On-Hold checks, name the check types, and write ages as 'working days'. "
        "Keep it SHORT and crisp: write exactly 3 bullet points (each starting with '- '), in this order: "
        "(1) a headline bullet with the total open checks and the share older than 30 working days; "
        "(2) where the aged backlog sits - name the top check types with their aged counts for each category; "
        "(3) the oldest items and the risk of closure if no action is taken. "
        "Do NOT include positive trends, recommended actions or next steps. Never use '**' except as balanced bold pairs. "
        "Be specific with numbers, factual and professional, no greetings, no headings, no markdown other than "
        "**bold** for key numbers. Use ONLY the numbers given; do not invent anything - in particular never name a closure status or outcome "
        "(say only that such checks 'may be closed'), and never mention policies, dates or deadlines not given.\n\n"
        + "\n".join(_stats(l, p) for l, p in pivots))
    try:
        from google import genai
        gclient = genai.Client(api_key=key)  # keep a reference; a temporary gets closed on GC
        resp = gclient.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt)
        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError("empty response")
        return text, "gemini"
    except Exception as e:  # keep the daily run alive
        return rule_based_insights(client, pivots), f"rule-based (Gemini failed: {type(e).__name__}: {str(e)[:120]})"


def insights_to_html(text: str) -> str:
    items = [l.strip().lstrip("-*• ").strip() for l in text.splitlines() if l.strip()]
    li = "".join("<li>" + re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(i)) + "</li>" for i in items)
    return ("<h3 style='font-family:Calibri,Arial,sans-serif;'>Insights</h3>"
            f"<ul style='font-family:Calibri,Arial,sans-serif;font-size:13px;'>{li}</ul>")


# --------------------------------------------------------------------------- mail
def smtp_configured() -> bool:
    return all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_PORT", "EMAIL_SENDER", "EMAIL_PASSWORD"))


class Mailer:
    def __enter__(self):
        host, port = os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])
        ctx = ssl.create_default_context()
        if os.getenv("SMTP_VERIFY_SSL", "true").lower() == "false":  # opt-in, only for TLS-inspecting networks
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        if port == 465:
            self.s = smtplib.SMTP_SSL(host, port, context=ctx, timeout=60)
        else:
            self.s = smtplib.SMTP(host, port, timeout=60)
            self.s.starttls(context=ctx)
        self.s.login(os.environ["EMAIL_SENDER"], os.environ["EMAIL_PASSWORD"])
        return self

    def __exit__(self, *exc):
        try:
            self.s.quit()
        except Exception:
            pass

    def send(self, to, cc, subject, html_body, attachments: list[Path]):
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = os.environ["EMAIL_SENDER"], ", ".join(to), subject
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg.set_content("Please view this e-mail in an HTML-capable client. The ageing details are in the attached Excel.")
        msg.add_alternative(html_body, subtype="html")
        for p in attachments:
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            main, sub = ctype.split("/", 1)
            msg.add_attachment(p.read_bytes(), maintype=main, subtype=sub, filename=p.name)
        self.s.send_message(msg, to_addrs=list(to) + list(cc))


def build_email_html(client: str, items: list[tuple[tc.TrackerSpec, pd.DataFrame]], insights: str,
                     on: dt.date) -> str:
    """Body = the full content of the PDF: client/date line, overview, insights, sign-off."""
    return (f"<p style='font-family:Calibri,Arial,sans-serif;font-size:13px;'><b>{html.escape(client)}</b> "
            f"&nbsp;|&nbsp; {on:%d-%b-%Y}</p>{tc.overview_html(items)}{insights_to_html(insights)}"
            f"{tc.signoff_html()}")


# ----------------------------------------------------------------------------- s3
def s3_configured() -> bool:
    return bool(tc.env("ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID") and tc.env("SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"))


def s3_client():
    import boto3
    return boto3.client(
        "s3", region_name=os.getenv("AWS_REGION", "ap-south-1"),
        aws_access_key_id=tc.env("ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=tc.env("SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"))


def s3_key(on: dt.date, *parts: str) -> str:
    return "/".join([S3_PREFIX, f"{on:%Y-%m-%d}", *parts])
