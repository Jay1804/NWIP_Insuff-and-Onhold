"""NWIP Insuff & On-Hold client tracker.  Run:  streamlit run app.py"""
import base64
import datetime as dt
import pathlib
import tempfile

import streamlit as st

import delivery as dv
import insuffTracker
import onholdTracker
import pipeline
import tracker_common as tc

tc.load_env()
st.set_page_config(page_title="NWIP Client Trackers", layout="wide")
st.title("NWIP – Insuff & On-Hold Client Trackers")

SPECS = {"insuff": insuffTracker.SPEC, "onhold": onholdTracker.SPEC}
ss = st.session_state
if "data" not in ss:  # instant start from today's cached copy, if any
    _hit = pipeline.load_cached()
    ss.data, ss.fetched_at = (_hit if _hit else (None, None))
ss.setdefault("dist", dv.load_saved_distribution())

with st.sidebar:
    st.header("Configuration")
    st.write("SMTP:", "✅" if dv.smtp_configured() else "❌ missing in .env")
    st.write("S3:", "✅" if dv.s3_configured() else "❌ missing in .env")
    st.write("Gemini:", "✅" if tc.env("GEMINI_API_KEY", "GOOGLE_API_KEY") else "❌ missing in .env")
    if ss.data:
        st.caption(f"Holidays from: {tc.HOLIDAY_SOURCE}")


def all_clients() -> list[str]:
    return pipeline.client_names(ss.data)


def section_summary():
    st.subheader("Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Open Insuff checks", len(ss.data["insuff"]))
    c2.metric("Open On-Hold checks", len(ss.data["onhold"]))
    c3.metric("Clients", len(all_clients()))
    for key, spec in SPECS.items():
        with st.expander(f"All clients – {spec.label}: Check Name × {spec.bucket_col}"):
            st.markdown(tc.pivot_to_html(tc.build_pivot(ss.data[key], spec.bucket_col)), unsafe_allow_html=True)


def section_client():
    st.subheader("Client report")
    clients = all_clients()
    q = st.text_input("🔍 Search client", key="q", placeholder="Type part of the client name")
    matches = [c for c in clients if q.strip().lower() in c.lower()] if q.strip() else clients
    st.caption(f"{len(matches)} of {len(clients)} clients")
    if not matches:
        st.info("No client matches your search.")
        return
    client = st.selectbox("Client", matches, key="sel")

    for key, spec in SPECS.items():
        sub = pipeline._slice(ss.data[key], client)
        st.markdown(f"**{spec.label}** – {len(sub)} open check(s)")
        if len(sub):
            st.markdown(tc.pivot_to_html(tc.build_pivot(sub, spec.bucket_col)), unsafe_allow_html=True)
            with st.expander(f"{spec.label} data"):
                st.dataframe(tc.client_view(sub), width="stretch")

    if st.button("Generate PDF + Excel", key="gen"):
        with st.spinner("Generating ..."), tempfile.TemporaryDirectory() as d:
            xlsx, pdf, _, src, _ = pipeline.build_client_report(
                ss.data, client, pathlib.Path(d), dt.date.today(), use_gemini=True)
            ss["files"] = {"client": client, "xlsx": xlsx.read_bytes(), "pdf": pdf.read_bytes(),
                           "xname": xlsx.name, "pname": pdf.name, "src": src}
    f = ss.get("files")
    if f and f["client"] == client:
        st.caption(f"Insights source: {f['src']}")
        d1, d2 = st.columns(2)
        d1.download_button("Download PDF", f["pdf"], file_name=f["pname"], mime="application/pdf", key="dp")
        d2.download_button("Download Excel (Data + Summary tabs)", f["xlsx"], file_name=f["xname"], key="dx")
        b64 = base64.b64encode(f["pdf"]).decode()
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="650"></iframe>',
                    unsafe_allow_html=True)


def section_distribution():
    st.subheader("Distribution list")
    st.caption("Columns: **Client** (must match Company Name), **To**, optional **CC** "
               "(separate addresses with `;` or `,`).")
    st.download_button("Download template", "Client,To,CC\nExample Client Pvt Ltd,a@x.com; b@x.com,c@x.com\n",
                       file_name="distribution_list_template.csv", key="tpl")
    up = st.file_uploader("Upload distribution list", type=["csv", "xlsx", "xls"], key="up")
    if up is not None and st.button("Use uploaded file", key="use"):
        try:
            ss.dist = dv.read_distribution_file(up)
            st.success(f"{len(ss.dist)} rows loaded (click Save to keep them).")
        except Exception as e:
            st.error(str(e))
    search = st.text_input("🔍 Filter list", key="dq", placeholder="Filter rows by client or e-mail")
    full = ss.dist
    if search.strip():
        q = search.strip().lower()
        st.caption("Showing filtered rows (read-only). Clear the filter to edit.")
        st.dataframe(full[full.apply(lambda r: q in " ".join(r.astype(str)).lower(), axis=1)], width="stretch")
        edited = full
    else:
        edited = st.data_editor(full, num_rows="dynamic", width="stretch", key="ed")
    bad = dv.invalid_emails(edited) if len(edited) else []
    if bad:
        st.warning("Invalid e-mail address(es): " + ", ".join(bad))
    have = {c.casefold() for c in edited["Client"].astype(str)}
    missing = [c for c in all_clients() if c.casefold() not in have]
    if missing:
        with st.expander(f"{len(missing)} client(s) with open checks have no recipients"):
            st.write(missing)
    if st.button("Save distribution list", key="save"):
        ss.dist = dv.normalise_distribution(edited)
        dv.save_distribution(ss.dist)
        st.success(f"Saved to {dv.DIST_PATH.name} (used by the scheduled daily run).")


def section_run():
    st.subheader("Generate & send")
    st.caption("One PDF, one Excel and one e-mail per client covering both Insuff and On-Hold. "
               "Recipients come from the distribution list.")
    sel = st.multiselect("Clients (type to search; empty = all)", all_clients(), key="msel")
    c1, c2, c3 = st.columns(3)
    use_g = c1.checkbox("Gemini insights", True, key="g")
    do_s3 = c2.checkbox(f"Save to s3://{dv.S3_BUCKET}/{dv.S3_PREFIX}/", True, key="s3")
    do_mail = c3.checkbox("Send e-mails", False, key="m")
    test_to = st.text_input("Test mode: send ALL e-mails to this address instead of clients (recommended first)",
                            key="t")
    if do_mail and not test_to.strip():
        st.warning("E-mails will go to the real client recipients in the distribution list.")
    if st.button("Run", type="primary", key="run"):
        dist = ss.dist if len(ss.dist) else dv.load_saved_distribution()
        bar, logs = st.progress(0.0), []
        try:
            res = pipeline.run_pipeline(
                ss.data, dist, clients=sel or None, send_mail=do_mail, upload_s3=do_s3, use_gemini=use_g,
                test_recipient=test_to.strip() or None, log=logs.append,
                progress=lambda f, c: bar.progress(min(f, 1.0), text=c))
            bar.progress(1.0)
            st.dataframe(res, width="stretch")
            if logs:
                with st.expander("Log"):
                    st.code("\n".join(logs))
        except Exception as e:
            st.error(f"Run failed: {e}")


def render():
    c1, c2 = st.columns([1, 3])
    if c1.button("Refresh data from MySQL", type="primary", key="load"):
        try:
            with st.spinner("Querying database ..."):
                ss.data = pipeline.fetch_all(log=lambda m: None)
                ss.fetched_at = dt.datetime.now()
        except Exception as e:
            st.error(f"Database error: {e}")
    if ss.data:
        c2.caption(f"Data as of {ss.fetched_at:%d-%b-%Y %H:%M} (cached for today; Refresh re-queries the database)")
    else:
        st.info("Click **Refresh data from MySQL** to load the data.")
        return
    section_summary()
    st.divider()
    section_client()
    st.divider()
    section_distribution()
    st.divider()
    section_run()


(tab,) = st.tabs(["Insuff & On-Hold"])
with tab:
    render()
