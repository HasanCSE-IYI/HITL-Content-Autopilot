import streamlit as st
import markdown
from datetime import datetime, timedelta
from core.models import ArticleStatus
from core.database import (
    list_drafts,
    get_draft,
    save_draft,
    delete_draft,
    update_draft_status,
    list_wordpress_sites,
    get_wordpress_site
)
from services.compliance.rules import enforce_nofollow_sponsored
from services.compliance.quality_checker import audit_article_quality
from services.generator.gemini_client import GeminiClient
from services.generator.prompts import build_section_regenerate_prompt
from services.publisher.wordpress import WordPressPublisher

STATUS_COLORS = {
    ArticleStatus.NEEDS_REVIEW: "🟡 Needs Review",
    ArticleStatus.DRAFT: "🔵 Draft",
    ArticleStatus.APPROVED: "🟢 Approved",
    ArticleStatus.SCHEDULED: "📅 Scheduled",
    ArticleStatus.PUBLISHED: "🟣 Published"
}

def render_review_tab():
    st.subheader("📝 Human-In-The-Loop (HITL) Review Queue")
    st.caption("Review drafts with automated Quality Scorecards, override AI categories, edit markdown, and publish or schedule to WordPress.")

    sites = list_wordpress_sites()
    sites_map = {s.id: s for s in sites}

    # 1. Filters
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        site_filter_opts = {"all": "All WordPress Sites"}
        for s in sites:
            site_filter_opts[str(s.id)] = s.name
        chosen_site_filter = st.selectbox(
            "Filter by Site",
            options=list(site_filter_opts.keys()),
            format_func=lambda x: site_filter_opts[x]
        )
        filter_site_id = int(chosen_site_filter) if chosen_site_filter != "all" else None

    with col_f2:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["all", ArticleStatus.NEEDS_REVIEW, ArticleStatus.APPROVED, ArticleStatus.DRAFT, ArticleStatus.SCHEDULED, ArticleStatus.PUBLISHED],
            format_func=lambda x: "All Statuses" if x == "all" else STATUS_COLORS.get(x, x)
        )

    drafts = list_drafts(status=status_filter, wp_site_id=filter_site_id)
    if not drafts:
        st.info("ℹ️ No drafts found matching this filter.")
        return

    with col_f3:
        draft_options = {d.id: f"[{d.id}] {d.title[:55]}... ({STATUS_COLORS.get(d.status, d.status)})" for d in drafts}
        selected_id = st.selectbox(
            "Select Article to Review",
            options=list(draft_options.keys()),
            format_func=lambda x: draft_options[x]
        )

    draft = get_draft(selected_id)
    if not draft:
        st.error("Draft not found.")
        return

    # Ensure quality scorecard is present
    if not draft.quality_scorecard:
        draft.quality_scorecard = audit_article_quality(draft)
        save_draft(draft)

    scorecard = draft.quality_scorecard

    st.markdown("---")

    # 2. Quality Scorecard Ribbon
    score = scorecard.total_score
    score_color = "🟢" if score >= 85 else ("🟡" if score >= 70 else "🔴")
    score_badge = f"{score_color} **Quality Score:** {score}/100"

    col_q1, col_q2, col_q3, col_q4 = st.columns([1, 1, 1, 2])
    with col_q1:
        st.markdown(f"**Status:** {STATUS_COLORS.get(draft.status, draft.status)}")
    with col_q2:
        st.markdown(score_badge)
    with col_q3:
        st.markdown(f"**Word Count:** {scorecard.word_count} words")
    with col_q4:
        # Target site name
        site_name = sites_map[draft.wp_site_id].name if draft.wp_site_id in sites_map else "No target site"
        st.caption(f"Target Site: **{site_name}**")

    # Quality details expander
    with st.expander(f"🛡️ Quality & Policy Audit Report ({score}/100)", expanded=score < 80):
        qc1, qc2, qc3 = st.columns(3)
        with qc1:
            st.markdown(f"**FTC Disclosure:** {'✅ Present' if scorecard.has_ftc_disclosure else '❌ Missing'}")
            st.markdown(f"**Price Disclaimer:** {'✅ Present' if scorecard.has_price_disclaimer else '❌ Missing'}")
        with qc2:
            st.markdown(f"**Schema JSON-LD:** {'✅ Present' if scorecard.has_schema_markup else '❌ Missing'}")
            st.markdown(f"**Comparison Table:** {'✅ Present' if scorecard.has_comparison_table else '❌ Missing'}")
        with qc3:
            st.markdown(f"**Pros & Cons:** {'✅ Present' if scorecard.has_pros_cons else '❌ Missing'}")
            st.markdown(f"**Compliant Links:** {int(scorecard.compliant_link_ratio*100)}%")

        if scorecard.issues:
            st.warning("**Actionable Recommendations:**\n" + "\n".join([f"- {iss}" for iss in scorecard.issues]))

    st.markdown("---")

    # 3. Taxonomy & Scheduling Controls
    target_site = sites_map.get(draft.wp_site_id) if draft.wp_site_id else None
    
    with st.expander("🏷️ Category, Tags & Scheduling Options", expanded=True):
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            if target_site and target_site.categories:
                cat_dict = {c["id"]: c["name"] for c in target_site.categories}
                # Check suggested category
                if draft.suggested_category_name:
                    st.caption(f"💡 AI Recommendation: **{draft.suggested_category_name}**")
                
                cat_keys = list(cat_dict.keys())
                chosen_cat_id = draft.selected_category_id or draft.suggested_category_id or (cat_keys[0] if cat_keys else None)
                cat_idx = cat_keys.index(chosen_cat_id) if chosen_cat_id in cat_keys else 0

                selected_cat = st.selectbox(
                    "WordPress Category",
                    options=cat_keys,
                    format_func=lambda x: cat_dict.get(x, "Uncategorized"),
                    index=cat_idx
                )
                draft.selected_category_id = selected_cat
            else:
                st.caption("No categories synced for target site. Sync in 'Multi-Site WordPress' tab.")

        with col_c2:
            if target_site and target_site.tags:
                tag_dict = {t["id"]: t["name"] for t in target_site.tags}
                chosen_tags = st.multiselect(
                    "WordPress Tags",
                    options=list(tag_dict.keys()),
                    default=[t for t in draft.selected_tags if t in tag_dict],
                    format_func=lambda x: tag_dict.get(x, "")
                )
                draft.selected_tags = chosen_tags
            else:
                st.caption("No tags synced for target site.")

        with col_c3:
            st.markdown("**Scheduling:**")
            now_dt = datetime.now()
            schedule_date = st.date_input("Scheduled Date", value=now_dt.date() + timedelta(days=1))
            schedule_time = st.time_input("Scheduled Time", value=now_dt.time())
            scheduled_iso = f"{schedule_date.isoformat()}T{schedule_time.strftime('%H:%M:%S')}"
            draft.scheduled_at = scheduled_iso

    st.markdown("---")

    # 4. Side-by-Side Product Sourcing Facts & Editor
    col_products, col_editor = st.columns([1, 2])

    with col_products:
        st.markdown("### 📦 Product Provenance")
        for idx, prod in enumerate(draft.products):
            with st.expander(f"{idx+1}. {prod.badge or 'Product'}: {prod.title[:40]}...", expanded=idx == 0):
                if prod.main_image:
                    st.image(prod.main_image, use_container_width=True)
                st.markdown(f"**ASIN:** `{prod.asin}`")
                st.markdown(f"**Price:** `{prod.price}`")
                st.caption(f"Source: `{prod.provenance or 'Amazon'}`")
                if prod.rating:
                    st.markdown(f"**Rating:** ⭐ {prod.rating}/5 ({prod.review_count or 0} reviews)")
                if prod.affiliate_url:
                    st.link_button("🔗 Affiliate Link", prod.affiliate_url, use_container_width=True)
                if prod.features:
                    st.markdown("**Key Specs:**")
                    for feat in prod.features[:4]:
                        st.markdown(f"- {feat}")

    with col_editor:
        st.markdown("### ✏️ Content Editor")

        edit_title = st.text_input("Article Title (H1)", value=draft.title)
        col_slug, col_kw_edit = st.columns(2)
        with col_slug:
            edit_slug = st.text_input("URL Slug", value=draft.slug)
        with col_kw_edit:
            edit_meta_title = st.text_input("SEO Meta Title", value=draft.meta_title)

        edit_meta_desc = st.text_area("Meta Description (150-160 chars)", value=draft.meta_description, height=70)

        tab_preview, tab_raw_md, tab_html = st.tabs(["👁️ Live Preview", "📝 Markdown Editor", "🏷️ HTML & Schema"])

        with tab_preview:
            st.markdown(draft.content_markdown)

        with tab_raw_md:
            edit_markdown = st.text_area(
                "Article Markdown",
                value=draft.content_markdown,
                height=520
            )

        with tab_html:
            st.code(draft.schema_json_ld, language="html")

        # AI Section Regenerator
        with st.expander("🪄 AI Section Regenerator (Refine with Gemini)"):
            regen_input = st.text_area("Section Text to Rewrite", placeholder="Paste section here...", key="regen_text_rev")
            regen_inst = st.text_input("Instruction", placeholder="e.g. Make it more persuasive, add comparison points...", key="regen_inst_rev")
            if st.button("✨ Regenerate Section with Gemini", key="regen_btn_rev"):
                client = GeminiClient()
                if not regen_input.strip() or not regen_inst.strip():
                    st.warning("Please provide text and instruction.")
                else:
                    with st.spinner("Rewriting with Gemini..."):
                        prompt = build_section_regenerate_prompt(regen_input, regen_inst)
                        revised_text = client.generate_text(prompt)
                        st.text_area("Revised Markdown", value=revised_text, height=180)
                        st.info("Copy the revised markdown above into the Markdown Editor, then click 'Save Changes'.")

        # 5. Action Buttons
        st.markdown("---")
        act_col1, act_col2, act_col3, act_col4 = st.columns(4)

        with act_col1:
            if st.button("💾 Save Changes", type="primary", use_container_width=True):
                draft.title = edit_title.strip()
                draft.slug = edit_slug.strip()
                draft.meta_title = edit_meta_title.strip()
                draft.meta_description = edit_meta_desc.strip()
                draft.content_markdown = edit_markdown
                html_body = markdown.markdown(edit_markdown, extensions=["tables", "fenced_code", "nl2br"])
                draft.content_html = enforce_nofollow_sponsored(html_body)
                # Re-audit
                draft.quality_scorecard = audit_article_quality(draft)
                save_draft(draft)
                st.success("✅ Changes saved!")
                st.rerun()

        with act_col2:
            if st.button("✅ Approve Draft", use_container_width=True):
                update_draft_status(draft.id, ArticleStatus.APPROVED)
                st.success("Draft Approved! Ready for publishing.")
                st.rerun()

        with act_col3:
            if st.button("📅 Schedule Post", use_container_width=True):
                if not target_site:
                    st.error("No target WordPress site assigned.")
                else:
                    with st.spinner("Scheduling to WordPress..."):
                        pub = WordPressPublisher(site=target_site)
                        res = pub.publish_article(
                            draft=draft,
                            status="future",
                            scheduled_datetime=draft.scheduled_at,
                            category_ids=[draft.selected_category_id] if draft.selected_category_id else None,
                            tag_ids=draft.selected_tags
                        )
                        if res["success"]:
                            update_draft_status(
                                draft.id,
                                status=ArticleStatus.SCHEDULED,
                                wordpress_post_id=res.get("post_id"),
                                published_url=res.get("link"),
                                scheduled_at=res.get("scheduled_at")
                            )
                            st.balloons()
                            st.success(f"🎉 Post scheduled on {target_site.name} for {draft.scheduled_at}!")
                            st.rerun()
                        else:
                            st.error(f"Scheduling failed: {res['message']}")

        with act_col4:
            if st.button("🚀 Publish Live Now", use_container_width=True):
                if not target_site:
                    st.error("No target WordPress site assigned.")
                else:
                    with st.spinner("Publishing live to WordPress..."):
                        pub = WordPressPublisher(site=target_site)
                        res = pub.publish_article(
                            draft=draft,
                            status="publish",
                            category_ids=[draft.selected_category_id] if draft.selected_category_id else None,
                            tag_ids=draft.selected_tags
                        )
                        if res["success"]:
                            update_draft_status(
                                draft.id,
                                status=ArticleStatus.PUBLISHED,
                                wordpress_post_id=res.get("post_id"),
                                published_url=res.get("link")
                            )
                            st.balloons()
                            st.success(f"🎉 Published live! (Post ID: {res.get('post_id')})")
                            st.rerun()
                        else:
                            st.error(f"Publish failed: {res['message']}")
