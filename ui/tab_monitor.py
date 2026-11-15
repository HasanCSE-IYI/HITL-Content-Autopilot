import streamlit as st
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from core.models import ArticleDraft, BulkTask, BulkTaskStatus
from core.database import (
    list_drafts,
    list_bulk_tasks,
    update_bulk_task,
    list_wordpress_sites,
    get_wordpress_site
)

def _calculate_age_days(date_str: Optional[str]) -> int:
    if not date_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()
        diff = now - dt
        return max(0, diff.days)
    except Exception:
        return 0

def render_monitor_tab():
    st.markdown("### 📈 Monitor & Freshness Alerts Dashboard")
    st.caption("Track live WordPress post statuses, monitor 30/60/90-day content freshness for Amazon compliance, and audit task errors with 1-click retry.")

    drafts: List[ArticleDraft] = list_drafts()
    bulk_tasks: List[BulkTask] = list_bulk_tasks()
    sites = {s.id: s.name for s in list_wordpress_sites() if s.id}

    published_drafts = [d for d in drafts if d.status == "published"]
    scheduled_drafts = [d for d in drafts if d.status == "future" or d.scheduled_at]
    in_review_drafts = [d for d in drafts if d.status in ("draft", "pending_review")]

    # Freshness Auditing
    fresh_count = 0
    warning_30_count = 0
    warning_60_count = 0
    critical_90_count = 0

    stale_items: List[Dict[str, Any]] = []

    for d in published_drafts:
        age_days = _calculate_age_days(d.updated_at or d.created_at)
        if age_days >= 90:
            critical_90_count += 1
            severity = "critical"
            status_badge = "🔴 Critical (90+ Days)"
        elif age_days >= 60:
            warning_60_count += 1
            severity = "warning_high"
            status_badge = "🟠 Review Needed (60+ Days)"
        elif age_days >= 30:
            warning_30_count += 1
            severity = "warning_low"
            status_badge = "🟡 Approaching (30+ Days)"
        else:
            fresh_count += 1
            severity = "fresh"
            status_badge = "🟢 Fresh (<30 Days)"

        if severity != "fresh":
            stale_items.append({
                "draft": d,
                "age_days": age_days,
                "severity": severity,
                "badge": status_badge
            })

    # Top KPI Metrics Row
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total Generated Articles", len(drafts))
    with kpi2:
        st.metric("Live Published on WP", len(published_drafts))
    with kpi3:
        st.metric("Scheduled on WP", len(scheduled_drafts))
    with kpi4:
        st.metric("Freshness Risk Alerts", len(stale_items), delta=f"-{critical_90_count} Critical" if critical_90_count else None)

    st.markdown("---")

    # Tabs inside Monitor for Clean Navigation
    m_tab1, m_tab2, m_tab3, m_tab4 = st.tabs([
        "⚠️ Content Freshness Alerts",
        "🌐 Published & Scheduled Posts",
        "🛑 Error Logs & Task Retries",
        "📊 Click & Conversion Analytics"
    ])

    # TAB 1: Content Freshness Alerts
    with m_tab1:
        st.markdown("#### 🕒 Amazon Compliance & Price Freshness Reminders")
        st.caption(
            "Amazon Associates Operating Agreement (Section 3) requires that advertised prices and availability "
            "must remain accurate. Amazon prices fluctuate; articles older than 60–90 days should be verified or refreshed."
        )

        alert_col1, alert_col2, alert_col3 = st.columns(3)
        with alert_col1:
            st.markdown(f"""
            <div style="background: rgba(255, 149, 0, 0.08); border: 1px solid rgba(255, 149, 0, 0.25); border-radius: 12px; padding: 12px 16px; text-align: center;">
                <div style="font-size: 0.8rem; font-weight: 600; color: #b45309; text-transform: uppercase;">30–59 Days (Approaching)</div>
                <div style="font-size: 1.6rem; font-weight: 800; color: #92400e;">{warning_30_count} <span style="font-size: 0.9rem; font-weight: 500;">posts</span></div>
            </div>
            """, unsafe_allow_html=True)
        with alert_col2:
            st.markdown(f"""
            <div style="background: rgba(249, 115, 22, 0.08); border: 1px solid rgba(249, 115, 22, 0.25); border-radius: 12px; padding: 12px 16px; text-align: center;">
                <div style="font-size: 0.8rem; font-weight: 600; color: #c2410c; text-transform: uppercase;">60–89 Days (Review Needed)</div>
                <div style="font-size: 1.6rem; font-weight: 800; color: #9a3412;">{warning_60_count} <span style="font-size: 0.9rem; font-weight: 500;">posts</span></div>
            </div>
            """, unsafe_allow_html=True)
        with alert_col3:
            st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 12px; padding: 12px 16px; text-align: center;">
                <div style="font-size: 0.8rem; font-weight: 600; color: #b91c1c; text-transform: uppercase;">90+ Days (Critical Policy Risk)</div>
                <div style="font-size: 1.6rem; font-weight: 800; color: #7f1d1d;">{critical_90_count} <span style="font-size: 0.9rem; font-weight: 500;">posts</span></div>
            </div>
            """, unsafe_allow_html=True)

        if not stale_items:
            st.success("🎉 All published articles are fresh (< 30 days old). No price refresh action required!")
        else:
            for item in stale_items:
                d = item["draft"]
                with st.expander(f"{item['badge']} — {d.title} (Age: {item['age_days']} days)"):
                    st.markdown(f"**Target Keyword:** `{d.target_keyword}`")
                    st.markdown(f"**WordPress Site:** {sites.get(d.wp_site_id, 'Default Site')}")
                    if d.published_url:
                        st.markdown(f"**Live Article:** [{d.published_url}]({d.published_url})")
                    st.markdown(f"**Products Reviewed:** {len(d.products)} products")

                    col_act1, col_act2 = st.columns([2, 1])
                    with col_act1:
                        st.info("💡 **Recommended Action:** Review product stock and current pricing on Amazon to ensure links remain compliant.")
                    with col_act2:
                        if st.button("Mark Verified / Reset Age", key=f"btn_reset_age_{d.id}"):
                            d.updated_at = datetime.now().isoformat()
                            from core.database import save_draft
                            save_draft(d)
                            st.success("Article marked fresh!")
                            st.rerun()

    # TAB 2: Published & Scheduled Posts
    with m_tab2:
        st.markdown("#### 🌐 Published & Scheduled WordPress Posts")
        active_posts = published_drafts + scheduled_drafts

        if not active_posts:
            st.info("No published or scheduled posts found in the local database. Publish articles from the 'HITL Review Studio' tab.")
        else:
            for post in active_posts:
                site_name = sites.get(post.wp_site_id, "Connected Site")
                is_pub = post.status == "published"
                status_badge_bg = "rgba(52, 199, 89, 0.1)" if is_pub else "rgba(88, 86, 214, 0.1)"
                status_badge_fg = "#15803d" if is_pub else "#4338ca"
                status_badge_border = "rgba(52, 199, 89, 0.25)" if is_pub else "rgba(88, 86, 214, 0.25)"
                status_label = "🟢 Live on WP" if is_pub else "⏰ Scheduled"
                beacon_dot = "#34c759" if is_pub else "#5856d6"
                date_display = post.scheduled_at or post.updated_at or post.created_at

                st.markdown(f"""
                <div class="apple-card-elevated" style="margin-bottom: 12px; padding: 14px 18px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="apple-beacon-dot" style="background: {beacon_dot};"></span>
                            <span style="font-weight: 700; font-size: 0.98rem; color: #1d1d1f;">{post.title}</span>
                        </div>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <span class="apple-pill-badge" style="background: {status_badge_bg}; color: {status_badge_fg}; border: 1px solid {status_badge_border};">
                                {status_label}
                            </span>
                            <span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.08); color: #0071e3; border: 1px solid rgba(0, 113, 227, 0.2);">
                                {site_name}
                            </span>
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; color: #86868b; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                        <span>Keyword: <code>{post.target_keyword}</code> • Format: <strong>{post.article_type}</strong> • Date: <strong>{date_display[:10] if date_display else 'N/A'}</strong></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if post.published_url:
                    st.link_button(f"🔗 View Live Post on {site_name}", post.published_url, use_container_width=True)
                elif post.wordpress_post_id:
                    st.caption(f"WordPress Post ID: #{post.wordpress_post_id} (Scheduled)")

    # TAB 3: Error Logs & 1-Click Retries
    with m_tab3:
        st.markdown("#### 🛑 Error Audit Logs & Retry Management")
        st.caption("Detailed error traces from the Bulk Queue and automated processing pipeline.")

        failed_tasks = [t for t in bulk_tasks if t.status == BulkTaskStatus.FAILED]

        if not failed_tasks:
            st.success("✅ No task failures recorded in the audit log!")
        else:
            st.error(f"Found {len(failed_tasks)} failed task(s) requiring review or retry.")
            for task in failed_tasks:
                with st.expander(f"❌ Failed: Keyword '{task.keyword}' (Batch: {task.batch_id})", expanded=True):
                    st.markdown(f"**Task ID:** `{task.id}`")
                    st.markdown(f"**Created At:** {task.created_at}")
                    st.markdown(f"**Error Message:**")
                    st.code(task.error_message or "Unknown exception occurred during processing.", language="text")

                    col_r1, col_r2 = st.columns([1, 4])
                    with col_r1:
                        if st.button("🔁 Retry Task", key=f"retry_{task.id}", type="primary"):
                            update_bulk_task(task.id, status=BulkTaskStatus.PENDING, progress=0, error_message="")
                            st.success(f"Task '{task.id}' reset to Pending. Bulk worker will re-process.")
                            st.rerun()
                    with col_r2:
                        st.caption("Resets the task status to 'pending' so it can be picked up by the next queue run.")

    # TAB 4: Click & Conversion Analytics
    with m_tab4:
        st.markdown("#### 📊 Affiliate Click & Performance Analytics")
        st.caption("Integration hook for Amazon Creators API and Click Tracking telemetry.")

        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            st.metric("Total Link Clicks", "0", help="Aggregated from connected analytics / Amazon Creator reports.")
        with ac2:
            st.metric("Active Tracked ASINs", sum(len(d.products) for d in published_drafts))
        with ac3:
            st.metric("Estimated EPC", "$0.00")

        st.info(
            "💡 **Amazon Creators API / Tracking Integration:**\n\n"
            "Official Amazon reporting telemetry connects automatically once Amazon Creators API credentials are activated "
            "in the **Settings** tab. In the meantime, link clicks and impressions can be monitored directly inside the "
            "Amazon Associates Central portal using your configured Tracking Tag."
        )
