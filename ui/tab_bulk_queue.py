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

def render_bulk_queue_tab():
    st.subheader("⚡ Bulk Keyword Queue Autopilot (20–50 Keywords)")
    st.caption("Queue up 20 to 50 keywords at once with automated concurrency control, rate limiting, and background processing.")

    sites = list_wordpress_sites()

    # 1. Bulk Batch Configuration Form
    with st.form("bulk_queue_form"):
        col_b1, col_b2 = st.columns([2, 1])

        with col_b1:
            st.markdown("#### 1. Paste Keywords")
            bulk_input = st.text_area(
                "Keywords (One per line)",
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

    # Progress Summary
    summary = get_batch_summary(selected_batch)
    running_state = is_batch_running(selected_batch)
    status_label = "🟢 Running in background" if running_state else "⚪ Completed or idle"

    st.markdown(f"**Batch Status:** {status_label}")
    st.progress(summary["percent_complete"] / 100.0)

    # Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Keywords", summary["total"])
    c2.metric("🟢 Completed", summary["completed"])
    c3.metric("🔵 Processing", summary["processing"])
    c4.metric("⏳ Pending", summary["pending"])
    c5.metric("❌ Failed", summary["failed"])

    # Task Table
    tasks_in_batch = list_bulk_tasks(batch_id=selected_batch)
    st.markdown("#### Task Queue Details:")

    for t in tasks_in_batch:
        col_t1, col_t2, col_t3, col_t4 = st.columns([3, 1, 1, 2])
        with col_t1:
            st.markdown(f"**{t.keyword}**")
            if t.asins_or_facts:
                st.caption(f"ASINs: `{t.asins_or_facts[:40]}`")
        with col_t2:
            st.caption(f"Type: `{t.article_type}`")
        with col_t3:
            if t.status == BulkTaskStatus.COMPLETED:
                st.markdown("🟢 **Completed**")
            elif t.status == BulkTaskStatus.PROCESSING:
                st.markdown(f"🔵 **Processing ({t.progress}%)**")
            elif t.status == BulkTaskStatus.FAILED:
                st.markdown("❌ **Failed**")
            else:
                st.markdown("⏳ **Pending**")
        with col_t4:
            if t.draft_id:
                st.caption(f"Draft ID: `{t.draft_id}`")
            elif t.error_message:
                st.caption(f"⚠️ {t.error_message[:60]}")

    st.markdown("---")
    st.info("💡 Once keywords are completed, they appear in the **'HITL Review Queue'** with full Quality Scorecards ready for your final approval!")
