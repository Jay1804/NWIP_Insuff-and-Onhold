"""End-to-end run: per-client PDF + Excel, Gemini insights, e-mail, S3 upload."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

import delivery as dv
import insuffTracker
import onholdTracker
import tracker_common as tc

SPECS = {"insuff": insuffTracker.SPEC, "onhold": onholdTracker.SPEC}


CACHE_DIR = tc.APP_DIR / ".cache"


def _cache_file(day: dt.date) -> Path:
    return CACHE_DIR / f"data_{day:%Y-%m-%d}.pkl"


def load_cached() -> tuple[dict[str, pd.DataFrame], dt.datetime] | None:
    """Today's cached data (ageing is date-dependent, so only a same-day cache is valid)."""
    f = _cache_file(dt.date.today())
    if not f.exists():
        return None
    try:
        obj = pd.read_pickle(f)
        return obj["data"], obj["fetched_at"]
    except Exception:
        return None


def fetch_all(log=print, use_cache: bool = False) -> dict[str, pd.DataFrame]:
    """Both trackers, queried in parallel. use_cache=True returns today's cached copy if present;
    a fresh query always rewrites the cache."""
    if use_cache and (hit := load_cached()):
        log(f"Using cached data from {hit[1]:%H:%M}")
        return hit[0]
    from concurrent.futures import ThreadPoolExecutor

    tc.get_holidays()  # resolve once before the worker threads start
    mods = (insuffTracker, onholdTracker)
    log("Fetching Insuff and On-Hold data in parallel ...")
    with ThreadPoolExecutor(max_workers=len(mods)) as ex:
        frames = list(ex.map(lambda m: m.fetch(), mods))
    out = {m.SPEC.key: df for m, df in zip(mods, frames)}
    for k, df in out.items():
        log(f"  {SPECS[k].label}: {len(df)} checks (holidays: {tc.HOLIDAY_SOURCE})")
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        for old in CACHE_DIR.glob("data_*.pkl"):
            old.unlink(missing_ok=True)
        pd.to_pickle({"data": out, "fetched_at": dt.datetime.now()}, _cache_file(dt.date.today()))
    except Exception as e:
        log(f"  (cache not saved: {e})")
    return out


def client_names(data: dict[str, pd.DataFrame]) -> list[str]:
    names = set()
    for df in data.values():
        names |= set(df[tc.CLIENT_COL].dropna().astype(str).str.strip())
    return sorted(n for n in names if n)


def _slice(df: pd.DataFrame, client: str) -> pd.DataFrame:
    return df[df[tc.CLIENT_COL].astype(str).str.strip() == client]


def build_client_report(data: dict[str, pd.DataFrame], client: str, out_dir: Path, today: dt.date,
                        use_gemini: bool = True):
    """ONE PDF + ONE Excel for the client covering Insuff and On-Hold (whichever have open checks).
    Returns (xlsx, pdf, insights, insights_source, items) with items = [(spec, pivot), ...]."""
    items, parts, sections = [], [], []
    for key, spec in SPECS.items():
        sub = _slice(data[key], client)
        if sub.empty:
            continue
        p = tc.build_pivot(sub, spec.bucket_col)
        items.append((spec, p))
        sections.append((f"{spec.label} Ageing ({spec.bucket_col})", p, len(sub)))
        parts.append((spec.label, sub, spec.bucket_col, f"{spec.label.replace('-', '')} "))
    if not items:
        raise ValueError("no open checks")
    base = tc.safe_name(client)
    stem = out_dir / base / f"{base}_Insuff_OnHold_Ageing_{today:%Y-%m-%d}"
    xlsx = tc.write_excel(stem.with_suffix(".xlsx"), parts)
    insights, src = dv.generate_insights(client, [(sp.label, p) for sp, p in items], use_gemini)
    pdf = tc.write_pdf(stem.with_suffix(".pdf"), client, sections, insights, today,
                       heading="Insuff & On-Hold Ageing Summary", overview=items)
    return xlsx, pdf, insights, src, items


def run_pipeline(data: dict[str, pd.DataFrame], dist: pd.DataFrame, out_root: Path | None = None,
                 clients: list[str] | None = None, send_mail: bool = True, upload_s3: bool = True,
                 use_gemini: bool = True, test_recipient: str | None = None,
                 log=print, progress=None) -> pd.DataFrame:
    """One combined e-mail per client, sent to that client's row(s) in the single distribution list."""
    today = dt.date.today()
    out_dir = (out_root or tc.APP_DIR / "output") / f"{today:%Y-%m-%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    s3 = dv.s3_client() if upload_s3 else None

    def upload(path: Path, *key_parts: str) -> str:
        if not s3:
            return "skipped"
        try:
            s3.upload_file(str(path), dv.S3_BUCKET, dv.s3_key(today, *key_parts))
            return "ok"
        except Exception as e:
            log(f"  S3 upload failed for {path.name}: {e}")
            return f"failed: {type(e).__name__}: {str(e)[:100]}"

    for key, spec in SPECS.items():  # consolidated all-client trackers: Data tab + Summary tab
        path = tc.write_excel(out_dir / f"{key}Tracker_{today:%Y-%m-%d}.xlsx",
                              [(spec.label, data[key], spec.bucket_col, "")])
        log(f"Consolidated {spec.label} workbook: {path.name} -> S3 {upload(path, 'Consolidated', path.name)}")

    targets = [c for c in (clients or client_names(data)) if any(len(_slice(data[k], c)) for k in SPECS)]
    results = []
    mailer_cm = dv.Mailer() if send_mail else None
    mailer = mailer_cm.__enter__() if mailer_cm else None
    try:
        for i, client in enumerate(targets, 1):
            row = {"Client": client, "Insuff": len(_slice(data["insuff"], client)),
                   "On-Hold": len(_slice(data["onhold"], client)), "Insights": "", "To": "", "Mail": "", "S3": ""}
            try:
                xlsx, pdf, insights, src, items = build_client_report(data, client, out_dir, today, use_gemini)
                row["Insights"] = src
                to, cc = dv.recipients_for(dist, client)
                if test_recipient:
                    to, cc = [test_recipient], []
                row["To"] = "; ".join(to)
                if not send_mail:
                    row["Mail"] = "not sent (disabled)"
                elif not to:
                    row["Mail"] = "no recipient in distribution list"
                else:
                    kinds = " and ".join("Insufficiency" if sp.key == "insuff" else "On-Hold" for sp, _ in items)
                    subj = (f"{'[TEST] ' if test_recipient else ''}Urgent: {client} – "
                            f"Closure of Aged {kinds} Checks")
                    mailer.send(to, cc, subj, dv.build_email_html(client, items, today), [pdf, xlsx])
                    row["Mail"] = "sent"
                base = tc.safe_name(client)
                row["S3"] = "/".join(sorted({upload(pdf, "Clients", base, pdf.name),
                                              upload(xlsx, "Clients", base, xlsx.name)}))
            except Exception as e:
                if row["Mail"] != "sent":
                    row["Mail"] = f"error: {type(e).__name__}: {str(e)[:150]}"
                log(f"{client}: {e}")
            results.append(row)
            if progress:
                progress(i / len(targets), client)
    finally:
        if mailer_cm:
            mailer_cm.__exit__(None, None, None)
    return pd.DataFrame(results)
