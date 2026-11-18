"""Shared building blocks: env loading, MySQL access, ageing buckets, pivots, Excel/PDF/HTML output."""
from __future__ import annotations

import datetime as dt
import html
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from tracker_common_data import BASE_SQL, HEADERS, HOLIDAYS

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "logo.png"
CLIENT_COL = "Company Name"
CHECK_COL = "Check Name"
ID_COL = "Case Check Id"

BUCKET_ORDER = ["0-2", "3-5", "6-7", "8-10", "11-14", "15-30", "31-45",
                "46-60", "61-90", "91-120", "121-180", "181+"]
_BINS = [-np.inf, 2, 5, 7, 10, 14, 30, 45, 60, 90, 120, 180, np.inf]

# Columns removed from the *client-facing* files (Excel + PDF). Empty by default;
# e.g. ["CAT Name", "CAT TL Name", "DM", "Department", "Verifier Name"] to hide internal staff.
CLIENT_EXCLUDE_COLUMNS: list[str] = []


# --------------------------------------------------------------------------- env
def load_env(path: Path | None = None) -> None:
    """Load .env tolerantly. Accepts KEY=value, 'KEY value' and keys containing spaces
    (e.g. 'GEMINI_API KEY=...' -> GEMINI_API_KEY). Real environment variables win."""
    path = path or APP_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
        else:
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            key, val = parts
        key = re.sub(r"\s+", "_", key.strip())
        val = val.strip().strip("'\"")
        if key and val:
            os.environ.setdefault(key, val)


def env(*names: str, default: str = "") -> str:
    for n in names:
        if os.getenv(n):
            return os.environ[n]
    return default


# ---------------------------------------------------------------------------- db
@dataclass(frozen=True)
class TrackerSpec:
    key: str            # "insuff" / "onhold"
    label: str          # shown in UI / reports
    bucket_col: str     # ageing bucket column used for the pivot
    check_status: int   # ec_case_checks.check_status filter
    aged_from: str = "31-45"      # first bucket shaded red in the overview (checks older than the threshold)
    threshold: str = ">30 Days"   # shown in the overview heading
    blurb: str = ""               # overview paragraph for this tracker
    ask: str = ""                 # what the client is asked to provide

    @property
    def sql(self) -> str:
        return BASE_SQL.format(status=self.check_status)


@lru_cache(maxsize=1)
def get_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    missing = [k for k in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing DB settings in .env: {', '.join(missing)}")
    url = URL.create(
        "mysql+mysqlconnector",
        username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"], port=int(os.getenv("DB_PORT", "3306")),
        database=os.environ["DB_NAME"],
    )
    return create_engine(url, pool_pre_ping=True)


def fetch_dataframe(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql_query(sql, conn)


HOLIDAY_SOURCE = "static list"


@lru_cache(maxsize=1)
def get_holidays() -> np.ndarray:
    """Holiday dates for NETWORKDAYS, read from the DB (HOLIDAY_TABLE, default
    ec_master_holidays_for_networkdays; falls back to ec_master_holidays, then the static list)."""
    global HOLIDAY_SOURCE
    tables = [os.getenv("HOLIDAY_TABLE", "ec_master_holidays_for_networkdays"), "ec_master_holidays"]
    for t in dict.fromkeys(tables):
        try:
            d = fetch_dataframe(f"SELECT HOLIDAY_DATE FROM {t}")
            dates = pd.to_datetime(d["HOLIDAY_DATE"], errors="coerce").dropna()
            if len(dates):
                HOLIDAY_SOURCE = f"DB table {t}"
                return dates.values.astype("datetime64[D]")
        except Exception:
            continue
    return np.array(HOLIDAYS, dtype="datetime64[D]")


def align_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Same column layout as the original Excel trackers (missing columns blank)."""
    df = df.copy()
    for col in HEADERS:
        if col not in df.columns:
            df[col] = ""
    return df[HEADERS]


# ------------------------------------------------------------------------ ageing
def networkdays(start, today: pd.Timestamp) -> pd.Series:
    """Excel NETWORKDAYS(start, today, holidays): Mon-Fri, both ends inclusive."""
    st = pd.to_datetime(start, errors="coerce")
    valid = st.notna()
    arr = st.fillna(today).values.astype("datetime64[D]")
    end = np.datetime64(today.date(), "D") + 1
    days = np.busday_count(arr, end, holidays=get_holidays())
    return pd.Series(days, index=st.index, dtype="float64").where(valid)


def bucketize(age: pd.Series) -> pd.Series:
    out = pd.cut(age.astype("float64"), bins=_BINS, labels=BUCKET_ORDER)
    return out.astype(object).where(age.notna(), "")


def finish_frame(df: pd.DataFrame) -> pd.DataFrame:
    # LEFT JOINs can repeat a check; the pivot counts distinct Case Check Ids.
    return df.drop_duplicates(subset=ID_COL).reset_index(drop=True)


# ----------------------------------------------------------------------- summary
def build_pivot(df: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    """Check Name (rows) x bucket (columns), count of Case Check Id, with totals."""
    cols = BUCKET_ORDER + ["Grand Total"]
    if df.empty:
        return pd.DataFrame(columns=cols, index=pd.Index([], name=CHECK_COL), dtype="int64")
    d = df[[CHECK_COL, bucket_col, ID_COL]].copy()
    d[CHECK_COL] = d[CHECK_COL].fillna("(blank)")
    p = pd.pivot_table(d, index=CHECK_COL, columns=bucket_col, values=ID_COL,
                       aggfunc="count", fill_value=0)
    p = p.reindex(columns=BUCKET_ORDER, fill_value=0).astype("int64")
    p["Grand Total"] = p.sum(axis=1)
    p = p.sort_values("Grand Total", ascending=False)
    p.loc["Grand Total"] = p.sum()
    p.index.name = CHECK_COL
    return p


OVERVIEW_INTRO = ("We are writing to bring your immediate attention to several long-standing checks that remain "
                  "unresolved. To maintain data integrity and report accuracy, we are requesting a formal closure "
                  "for these checks. <i>All ageing buckets below are in working days (Monday-Friday, excluding "
                  "holidays), not calendar days.</i>")
OVERVIEW_CLOSING = ("In case of no action or response, such checks may be closed. Hence, it's imperative that the "
                    "attached list is reviewed.")


SIGNOFF_LINES = [
    "Please find attached the updated report regarding your Insufficiency and On-Hold Checks.",
    "We look forward to your prompt response to prevent automatic closure.",
]
SIGNATURE_LINES = ["Regards,", "Authbridge Research Private Limited", "Web: www.authbridge.com"]
DISCLAIMER = "This is a system generated email."


def signoff_html() -> str:
    font = "font-family:Calibri,Arial,sans-serif;font-size:13px;"
    body = "".join(f"<p style='{font}'>{html.escape(l)}</p>" for l in SIGNOFF_LINES)
    sig = "<br>".join(html.escape(l) for l in SIGNATURE_LINES)
    return (f"<div style='{font}'>{body}<p>{sig}</p>"
            f"<p style='font-size:11px;color:#555;'>{html.escape(DISCLAIMER)}</p></div>")


def overview_counts(p: pd.DataFrame) -> list[int]:
    if p.empty:
        return [0] * len(BUCKET_ORDER)
    return [int(p.loc["Grand Total", b]) for b in BUCKET_ORDER]


def overview_html(items: list[tuple[TrackerSpec, pd.DataFrame]]) -> str:
    """Letter-style overview for one or more trackers: intro once, then per tracker a bold lead + blurb and a
    one-row bucket table (aged buckets shaded), then the combined ask and closing."""
    font = "font-family:Calibri,Arial,sans-serif;font-size:13px;"
    cell = "border:2px solid #000;padding:5px 10px;text-align:center;" + font
    parts = [f"<p>Dear Partner,</p><p>{OVERVIEW_INTRO}</p>"]
    for spec, p in items:
        aged_i = BUCKET_ORDER.index(spec.aged_from)
        head = "".join(f"<td style='{cell}background:#D9D9D9;font-weight:bold;'>{b}</td>" for b in BUCKET_ORDER)
        vals = "".join(
            f"<td style='{cell}" + ("background:#FFE0E0;font-weight:bold;" if i >= aged_i else "") + f"'>{v}</td>"
            for i, v in enumerate(overview_counts(p)))
        parts.append(f"<ul><li><b>{html.escape(spec.label)} Checks ({html.escape(spec.threshold)}):</b> "
                     f"{html.escape(spec.blurb)}</li></ul>"
                     f"<table style='border-collapse:collapse;margin-left:30px;'><tr>{head}</tr><tr>{vals}</tr></table>")
    asks = "".join(f"<li>{html.escape(spec.ask)}</li>" for spec, _ in items)
    parts.append(f"<p><b>What this means for you:</b></p><p>Kindly provide the following:</p><ul>{asks}</ul>"
                 f"<p>{OVERVIEW_CLOSING}</p>")
    return f"<div style='{font}'>{''.join(parts)}</div>"


def pivot_to_html(p: pd.DataFrame, title: str = "") -> str:
    """Inline-styled table (bold light-gray header, full borders) for the e-mail and the UI."""
    cell = "border:1px solid #000;padding:4px 6px;font-family:Calibri,Arial,sans-serif;font-size:12px;"
    head = cell + "background:#D9D9D9;font-weight:bold;text-align:center;"
    rows = [f"<tr><th style='{head}text-align:left;'>{html.escape(str(p.index.name or CHECK_COL))}</th>"
            + "".join(f"<th style='{head}'>{html.escape(str(c))}</th>" for c in p.columns) + "</tr>"]
    for name, row in p.iterrows():
        bold = "font-weight:bold;" if name == "Grand Total" else ""
        rows.append(f"<tr><td style='{cell}{bold}'>{html.escape(str(name))}</td>"
                    + "".join(f"<td style='{cell}{bold}text-align:center;'>{int(v)}</td>" for v in row) + "</tr>")
    h = f"<h3 style='font-family:Calibri,Arial,sans-serif;'>{html.escape(title)}</h3>" if title else ""
    return f"{h}<table style='border-collapse:collapse;'>{''.join(rows)}</table>"


# ------------------------------------------------------------------------- excel
def client_view(df: pd.DataFrame) -> pd.DataFrame:
    """Drop all-blank and configured internal columns for client-facing output."""
    blank = df.replace(r"^\s*$", pd.NA, regex=True).isna().all()
    keep = [c for c in df.columns if not blank[c] and c not in CLIENT_EXCLUDE_COLUMNS]
    return df[keep]


def _column_kind(s: pd.Series) -> str:
    vals = s.dropna()
    if vals.empty:
        return "text"
    first = vals.iloc[0]
    if isinstance(first, (dt.datetime, dt.date, pd.Timestamp)):
        ts = pd.to_datetime(vals, errors="coerce").dropna()
        return "date" if (ts == ts.dt.normalize()).all() else "datetime"
    return "text"


def write_excel(path: Path, parts: list[tuple[str, pd.DataFrame, str, str]]) -> Path:
    """parts = [(tracker label, data_df, bucket_col, sheet prefix)].
    Sheets: '<prefix>Data' and '<prefix>Summary' (prefix '' -> 'Data'/'Summary')."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        wb = xw.book
        base = {"border": 1, "font_name": "Calibri", "font_size": 11}
        f_head = wb.add_format({**base, "bold": True, "bg_color": "#D9D9D9",
                                "align": "center", "valign": "vcenter", "text_wrap": True})
        f_text = wb.add_format(base)
        f_num = wb.add_format({**base, "align": "center"})
        f_date = wb.add_format({**base, "num_format": "dd-mmm-yyyy"})
        f_dtm = wb.add_format({**base, "num_format": "dd-mmm-yyyy hh:mm"})
        f_totl = wb.add_format({**base, "bold": True, "align": "center"})
        f_totl_l = wb.add_format({**base, "bold": True})
        f_ttl = wb.add_format({"bold": True, "font_name": "Calibri", "font_size": 12})

        for label, df, bucket_col, prefix in parts:
            # ---- data tab
            ws = wb.add_worksheet(f"{prefix}Data")
            data = client_view(df)
            for c, name in enumerate(data.columns):
                ws.write(0, c, name, f_head)
                s = data[name]
                kind = _column_kind(s)
                fmt = {"date": f_date, "datetime": f_dtm}.get(kind, f_text)
                if kind != "text":
                    s = pd.to_datetime(s, errors="coerce")
                vals = [None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v)
                        for v in s.astype(object)]
                ws.write_column(1, c, vals, fmt)
                width = min(max(len(str(name)) + 2, 12), 40)
                ws.set_column(c, c, width)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(data), 1), max(len(data.columns) - 1, 0))

            # ---- summary tab
            sm = wb.add_worksheet(f"{prefix}Summary")
            p = build_pivot(df, bucket_col)
            sm.write(0, 0, f"{label} - Count of {ID_COL}", f_ttl)
            sm.write(1, 0, bucket_col, f_ttl)
            sm.write(2, 0, CHECK_COL, f_head)
            for c, name in enumerate(p.columns, start=1):
                sm.write(2, c, name, f_head)
            for r, (name, row) in enumerate(p.iterrows(), start=3):
                tot = name == "Grand Total"
                sm.write(r, 0, name, f_totl_l if tot else f_text)
                for c, v in enumerate(row, start=1):
                    sm.write_number(r, c, int(v), f_totl if tot or c == len(row) else f_num)
            sm.set_column(0, 0, 45)
            sm.set_column(1, len(p.columns), 11)
    return path


# --------------------------------------------------------------------------- pdf
def write_pdf(path: Path, client: str, sections: list[tuple[str, pd.DataFrame, int]],
              insights: str, generated_on: dt.date, heading: str = "Ageing Summary",
              overview: list | None = None) -> Path:
    """sections = [(title, pivot, total_checks)]. Landscape A4, bold light-gray headers, full borders."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    path.parent.mkdir(parents=True, exist_ok=True)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=16, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    cellp = ParagraphStyle("c", parent=ss["BodyText"], fontSize=8, leading=9.5)

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=f"{client} - {heading}")
    titles = [Paragraph(html.escape(client), h1),
              Paragraph(f"{html.escape(heading)} &nbsp;|&nbsp; {generated_on:%d-%b-%Y}",
                        ParagraphStyle("sub", parent=body, alignment=1))]
    page_w = landscape(A4)[0] - 24 * mm
    logo_w = 48 * mm
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=logo_w, height=logo_w * 100 / 421)  # source is 421x100 px
        head = Table([[logo, titles, ""]], colWidths=[logo_w + 4 * mm, page_w - 2 * (logo_w + 4 * mm), logo_w + 4 * mm])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "LEFT"),
                                  ("LEFTPADDING", (0, 0), (0, 0), 0)]))
        story = [head, Spacer(1, 8)]
    else:
        story = titles + [Spacer(1, 6)]

    avail = landscape(A4)[0] - 24 * mm
    if overview:
        story += [Paragraph("Dear Partner,", body), Spacer(1, 4), Paragraph(OVERVIEW_INTRO, body), Spacer(1, 4)]
        for ospec, op in overview:
            aged_i = BUCKET_ORDER.index(ospec.aged_from)
            story += [Paragraph(f"&bull; <b>{html.escape(ospec.label)} Checks ({html.escape(ospec.threshold)}):</b> "
                                f"{html.escape(ospec.blurb)}", body), Spacer(1, 4)]
            ot = Table([BUCKET_ORDER, overview_counts(op)], colWidths=[avail / 14] * len(BUCKET_ORDER), hAlign="LEFT")
            ot.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
                ("BACKGROUND", (aged_i, 1), (-1, 1), colors.HexColor("#FFE0E0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (aged_i, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            story += [ot, Spacer(1, 8)]
        story += [Paragraph("<b>What this means for you:</b>", body), Spacer(1, 3),
                  Paragraph("Kindly provide the following:", body), Spacer(1, 3)]
        story += [Paragraph(f"&bull; {html.escape(o.ask)}", body) for o, _ in overview]
        story += [Spacer(1, 4), Paragraph(OVERVIEW_CLOSING, body), Spacer(1, 6)]

    for title, p, total in sections:
        story.append(Paragraph(f"{html.escape(title)} &mdash; {total} check(s)", h2))
        head = [CHECK_COL] + list(p.columns)
        data = [head]
        for name, row in p.iterrows():
            data.append([Paragraph(f"<b>{html.escape(str(name))}</b>" if name == "Grand Total" else html.escape(str(name)), cellp)] + [int(v) for v in row])
        first = 52 * mm
        other = (avail - first) / len(p.columns)
        t = Table(data, colWidths=[first] + [other] * len(p.columns), repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if len(data) > 1:
            style += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                      ("FONTNAME", (-1, 1), (-1, -1), "Helvetica-Bold")]
        t.setStyle(TableStyle(style))
        story.append(t)

    story.append(Paragraph("Insights", h2))
    for line in [l.strip() for l in insights.splitlines() if l.strip()]:
        text = html.escape(line.lstrip("-*• ").strip())
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        story.append(Paragraph(f"&bull; {text}", body))
    sign = [Spacer(1, 8)]
    for line in SIGNOFF_LINES:
        sign += [Paragraph(html.escape(line), body), Spacer(1, 3)]
    sign += [Spacer(1, 26)] + [Paragraph(html.escape(l), body) for l in SIGNATURE_LINES]  # ~2 blank lines before Regards
    sign += [Spacer(1, 6), Paragraph(f"<i>{html.escape(DISCLAIMER)}</i>",
                                     ParagraphStyle("disc", parent=body, fontSize=8, textColor=colors.grey))]
    story.append(KeepTogether(sign))
    doc.build(story)
    return path


def safe_name(s: str) -> str:
    return re.sub(r"[^\w\- ]+", "_", s).strip().replace(" ", "_")[:80] or "client"
