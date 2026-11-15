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

SAMPLE_BULK_KEYWORDS = """Best Wireless Ergonomic Keyboard | B0CX23V2ZT
Best Standing Desk Under 500
Quiet Air Purifier for Bedroom 2026
Best Mechanical Gaming Mouse
Best USB-C Monitor For MacBook"""

def render_bulk_queue_tab():
    st.subheader("⚡ Bulk Keyword Queue Autopilot (20–50 Keywords)")
    st.caption("Queue up 20 to 50 keywords at once with automated concurrency control, rate limiting, and background processing.")

    sites = list_wordpress_sites()

    col_pre1, col_pre2 = st.columns([3, 1.2])
    with col_pre2:
        if st.button("📋 Load Sample 5-Keyword Batch", use_container_width=True, key="bulk_load_sample_btn"):
            st.session_state["bulk_keywords_input"] = SAMPLE_BULK_KEYWORDS
            st.toast("Loaded 5 high-intent sample keywords into Bulk Queue!", icon="📋")
            st.rerun()

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
        st.markdown("""
        <div class="apple-card-elevated" style="text-align: center; padding: 36px 20px; margin-top: 14px;">
            <div style="font-size: 2.2rem; margin-bottom: 8px;">⚡</div>
            <div style="font-weight: 700; font-size: 1.15rem; color: var(--apple-ink-primary); margin-bottom: 6px;">No Bulk Batches Queued Yet</div>
            <div style="font-size: 0.88rem; color: var(--apple-ink-secondary); max-width: 520px; margin: 0 auto;">
                Paste 10 to 50 keywords above (or click <strong>Load Sample 5-Keyword Batch</strong>) to batch-generate Amazon affiliate articles with automated background workers, controlled concurrency, and polite delay pacing.
            </div>
        </div>
        """, unsafe_allow_html=True)
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
        beacon_color = "var(--apple-green)" if running_state else "var(--apple-slate)"

        running_pill_bg = 'rgba(52,199,89,0.1)' if running_state else 'var(--apple-surface-secondary)'
        running_pill_fg = 'var(--apple-green-dark)' if running_state else 'var(--apple-ink-secondary)'
        running_pill_border = 'rgba(52,199,89,0.2)' if running_state else 'var(--apple-border)'

        batch_card_html = (
            '<div style="background: var(--apple-surface-card); border: 1px solid var(--apple-border); border-radius: 14px; padding: 14px 20px; margin-bottom: 12px; box-shadow: var(--apple-shadow-sm);">'
            '<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">'
            '<div style="display: flex; align-items: center; gap: 8px;">'
            f'<span class="apple-beacon-dot" style="background: {beacon_color};"></span>'
            f'<span style="font-weight: 700; font-size: 0.98rem; color: var(--apple-ink-primary);">Batch: <code>{batch_id}</code></span>'
            f'<span class="apple-pill-badge" style="background: {running_pill_bg}; color: {running_pill_fg}; border: 1px solid {running_pill_border};">{status_label}</span>'
            '<span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.08); color: var(--apple-blue); border: 1px solid rgba(0, 113, 227, 0.2);">⚡ Live Reactivity: 3s</span>'
            '</div>'
            f'<span style="font-size: 0.92rem; font-weight: 700; color: var(--apple-blue);">{summary["percent_complete"]}% Complete ({summary["completed"]}/{summary["total"]} items)</span>'
            '</div>'
            '</div>'
        )
        st.markdown(batch_card_html, unsafe_allow_html=True)

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
                        st.markdown("""<span class="apple-pill-badge" style="background: rgba(52,199,89,0.1); color: var(--apple-green-deep); border: 1px solid rgba(52,199,89,0.25);">🟢 Completed</span>""", unsafe_allow_html=True)
                    elif t.status == BulkTaskStatus.PROCESSING:
                        st.markdown(f"""<span class="apple-pill-badge" style="background: rgba(0,113,227,0.1); color: var(--apple-blue); border: 1px solid rgba(0,113,227,0.25);">🔵 Running ({t.progress}%)</span>""", unsafe_allow_html=True)
                    elif t.status == BulkTaskStatus.FAILED:
                        st.markdown("""<span class="apple-pill-badge" style="background: rgba(239,68,68,0.1); color: var(--apple-red-deep); border: 1px solid rgba(239,68,68,0.25);">❌ Failed</span>""", unsafe_allow_html=True)
                    else:
                        st.markdown("""<span class="apple-pill-badge" style="background: var(--apple-surface-secondary); color: var(--apple-ink-secondary); border: 1px solid var(--apple-border);">⏳ Pending</span>""", unsafe_allow_html=True)
                with col_t4:
                    if t.draft_id:
                        st.caption(f"Draft ID: `{t.draft_id}`")
                    elif t.error_message:
                        st.caption(f"⚠️ {t.error_message[:45]}")
                        if st.button("🔁 Retry", key=f"inline_retry_{t.id}", use_container_width=True):
                            from core.database import update_bulk_task
                            update_bulk_task(t.id, status=BulkTaskStatus.PENDING, progress=0, error_message="")
                            st.toast(f"Reset '{t.keyword[:25]}' to Pending for retry!", icon="🔄")
                            st.rerun()

    render_live_batch_monitor(selected_batch)

    st.markdown("---")
    st.info("💡 Once keywords are completed, they appear in the **'HITL Review Queue'** with full Quality Scorecards ready for your final approval!")
