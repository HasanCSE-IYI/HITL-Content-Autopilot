import streamlit as st
import uuid
from typing import List
from core.models import BulkTask, BulkTaskStatus, ArticleType
from core.database import (
    create_bulk_task,
    list_bulk_tasks,
    get_batch_summary,
    list_wordpress_sites
)
from services.queue.bulk_manager import start_batch_execution, is_batch_running
from services.amazon.csv_importer import generate_bulk_keywords_csv_template, parse_bulk_keywords_csv

def render_bulk_queue_tab():
    st.subheader("⚡ Bulk Keyword Queue Autopilot (20–50 Keywords)")
    st.caption("Queue up 20 to 50 keywords at once with automated concurrency control, rate limiting, and background processing.")

    sites = list_wordpress_sites()

    # CSV Import Helper (Section 10 Compliance)
    with st.expander("📂 Import Keywords from CSV Spreadsheet", expanded=False):
        st.caption("Upload a CSV file containing keywords, optional ASINs, and article formats (roundup, single_review, comparison).")
        csv_b1, csv_b2 = st.columns([1.5, 1])
        with csv_b2:
            st.download_button(
                "📥 Download CSV Template",
                data=generate_bulk_keywords_csv_template(),
                file_name="bulk_keywords_template.csv",
                mime="text/csv",
                key="bulk_dl_csv_tpl",
                use_container_width=True
            )
        with csv_b1:
            bulk_csv_file = st.file_uploader("Upload Keywords CSV", type=["csv"], key="bulk_csv_uploader")
            if bulk_csv_file:
                csv_str = bulk_csv_file.getvalue().decode("utf-8", errors="ignore")
                tasks_parsed, dups = parse_bulk_keywords_csv(csv_str)
                if tasks_parsed:
                    formatted_lines = []
                    for t in tasks_parsed:
                        if t["asins"]:
                            formatted_lines.append(f"{t['keyword']} | {t['asins']}")
                        else:
                            formatted_lines.append(t["keyword"])
                    st.session_state["bulk_keywords_input"] = "\n".join(formatted_lines)
                    st.toast(f"✅ Imported {len(tasks_parsed)} keywords from CSV!", icon="📋")
                    if dups:
                        st.warning(f"⚠️ Filtered out {len(dups)} duplicate keyword(s): {', '.join(dups[:3])}")

    # 1. Bulk Batch Configuration Form
    with st.form("bulk_queue_form"):
        col_b1, col_b2 = st.columns([2, 1])

        with col_b1:
            st.markdown("#### 1. Paste Keywords")
            default_bulk = st.session_state.get("bulk_keywords_input", "")
            bulk_input = st.text_area(
                "Keywords (One per line)",
                value=default_bulk,
                height=180,
                placeholder="Best Wireless Ergonomic Keyboard\nBest Standing Desk Under 500\nTop Noise Cancelling Headphones 2026\nBest Mechanical Gaming Mouse\nBest USB-C Monitor For MacBook...",
                help="Paste 10, 20, or up to 50 keywords. Optional format: Keyword | ASIN1, ASIN2"
            )

        with col_b2:
            st.markdown("#### 2. Target Site & Settings")
            site_options = {s.id: f"{s.name} ({s.url})" for s in sites}
            chosen_site_id = None
            if sites:
                default_idx = next((i for i, s in enumerate(sites) if s.is_default), 0)
                chosen_site_id = st.selectbox(
                    "Target WordPress Site",
                    options=list(site_options.keys()),
                    format_func=lambda x: site_options[x],
                    index=default_idx
                )
            else:
                st.warning("⚠️ No WordPress sites connected. You can still generate drafts and publish later.")

            article_type = st.selectbox(
                "Default Article Type",
                options=[ArticleType.ROUNDUP, ArticleType.SINGLE_REVIEW, ArticleType.COMPARISON],
                format_func=lambda x: "Top X Roundup" if x == "roundup" else ("Single Review" if x == "single_review" else "Comparison"),
                index=0
            )

            concurrency = st.slider(
                "Worker Concurrency (Threads)",
                min_value=1,
                max_value=5,
                value=2,
                help="Recommended: 2. Higher values may trigger rate limits on Gemini or Amazon."
            )

            delay_secs = st.slider(
                "Polite Request Delay (seconds)",
                min_value=1,
                max_value=10,
                value=4,
                help="Delay between keyword generations to prevent API quotas & scraping blocks."
            )

        launch_btn = st.form_submit_button("🚀 Launch Bulk Queue Batch", type="primary", use_container_width=True)

        if launch_btn:
            raw_lines = [l.strip() for l in bulk_input.splitlines() if l.strip()]
            if not raw_lines:
                st.error("Please enter at least one keyword.")
            else:
                batch_id = f"batch_{str(uuid.uuid4())[:8]}"
                created_count = 0
                for line in raw_lines:
                    # Support 'Keyword | ASIN1, ASIN2' or pure 'Keyword'
                    if "|" in line:
                        kw, asins = line.split("|", 1)
                        kw = kw.strip()
                        asins = asins.strip()
                    else:
                        kw = line.strip()
                        asins = ""

                    task = BulkTask(
                        batch_id=batch_id,
                        keyword=kw,
                        article_type=article_type,
                        asins_or_facts=asins,
                        target_wp_site_id=chosen_site_id
                    )
                    create_bulk_task(task)
                    created_count += 1

                # Start background thread execution
                started = start_batch_execution(batch_id, concurrency=concurrency, delay_seconds=float(delay_secs))
                if started:
                    st.session_state["current_batch_id"] = batch_id
                    st.success(f"🎉 Created batch `{batch_id}` with {created_count} keywords! Processing started in background.")
                    st.rerun()

    st.markdown("---")

    # 2. Batch Monitor & Live Progress
    recent_tasks = list_bulk_tasks()
    if not recent_tasks:
        st.info("ℹ️ No bulk batches yet. Enter keywords above and launch your first batch!")
        return

    # Find unique batches
    unique_batches = []
    for t in recent_tasks:
        if t.batch_id not in unique_batches:
            unique_batches.append(t.batch_id)

    col_m1, col_m2 = st.columns([3, 1])
    with col_m1:
        selected_batch = st.selectbox(
            "Select Batch to Monitor",
            options=unique_batches,
            index=0 if "current_batch_id" not in st.session_state or st.session_state["current_batch_id"] not in unique_batches else unique_batches.index(st.session_state["current_batch_id"])
        )
    with col_m2:
        if st.button("🔄 Refresh Progress", use_container_width=True):
            st.rerun()

    @st.fragment(run_every="3s")
    def render_live_batch_monitor(batch_id: str):
        summary = get_batch_summary(batch_id)
        running_state = is_batch_running(batch_id)
        status_label = "Active (Processing)" if running_state else "Completed / Idle"
        beacon_color = "#34c759" if running_state else "#94a3b8"

        st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 14px; padding: 14px 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="apple-beacon-dot" style="background: {beacon_color};"></span>
                    <span style="font-weight: 700; font-size: 0.98rem; color: #1d1d1f;">Batch: <code>{batch_id}</code></span>
                    <span class="apple-pill-badge" style="background: {'rgba(52,199,89,0.1)' if running_state else 'rgba(0,0,0,0.05)'}; color: {'#15803d' if running_state else '#64748b'}; border: 1px solid {'rgba(52,199,89,0.2)' if running_state else 'rgba(0,0,0,0.08)'};">
                        {status_label}
                    </span>
                    <span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.08); color: #0071e3; border: 1px solid rgba(0, 113, 227, 0.2);">
                        ⚡ Live Reactivity: 3s
                    </span>
                </div>
                <span style="font-size: 0.92rem; font-weight: 700; color: #0071e3;">{summary['percent_complete']}% Complete ({summary['completed']}/{summary['total']} items)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.progress(summary["percent_complete"] / 100.0)

        if running_state:
            st.info("⚡ Background worker is actively generating drafts. This monitor updates every 3 seconds automatically without reloading the page.")

        # Metrics
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Keywords", summary["total"])
        c2.metric("🟢 Completed", summary["completed"])
        c3.metric("🔵 Processing", summary["processing"])
        c4.metric("⏳ Pending", summary["pending"])
        c5.metric("❌ Failed", summary["failed"])

        # Task Table
        tasks_in_batch = list_bulk_tasks(batch_id=batch_id)
        st.markdown("#### 📋 Task Queue Details:")

        for t in tasks_in_batch:
            with st.container(border=True):
                col_t1, col_t2, col_t3, col_t4 = st.columns([3, 1, 1.2, 2])
                with col_t1:
                    st.markdown(f"**{t.keyword}**")
                    if t.asins_or_facts:
                        st.caption(f"ASINs: `{t.asins_or_facts[:40]}`")
                with col_t2:
                    st.caption(f"Format: `{t.article_type}`")
                with col_t3:
                    if t.status == BulkTaskStatus.COMPLETED:
                        st.markdown("""<span class="apple-pill-badge" style="background: rgba(52,199,89,0.1); color: #166534; border: 1px solid rgba(52,199,89,0.25);">🟢 Completed</span>""", unsafe_allow_html=True)
                    elif t.status == BulkTaskStatus.PROCESSING:
                        st.markdown(f"""<span class="apple-pill-badge" style="background: rgba(0,113,227,0.1); color: #0071e3; border: 1px solid rgba(0,113,227,0.25);">🔵 Running ({t.progress}%)</span>""", unsafe_allow_html=True)
                    elif t.status == BulkTaskStatus.FAILED:
                        st.markdown("""<span class="apple-pill-badge" style="background: rgba(239,68,68,0.1); color: #991b1b; border: 1px solid rgba(239,68,68,0.25);">❌ Failed</span>""", unsafe_allow_html=True)
                    else:
                        st.markdown("""<span class="apple-pill-badge" style="background: rgba(0,0,0,0.05); color: #64748b; border: 1px solid rgba(0,0,0,0.1);">⏳ Pending</span>""", unsafe_allow_html=True)
                with col_t4:
                    if t.draft_id:
                        st.caption(f"Draft ID: `{t.draft_id}`")
                    elif t.error_message:
                        st.caption(f"⚠️ {t.error_message[:60]}")

    render_live_batch_monitor(selected_batch)

    st.markdown("---")
    st.info("💡 Once keywords are completed, they appear in the **'HITL Review Queue'** with full Quality Scorecards ready for your final approval!")
