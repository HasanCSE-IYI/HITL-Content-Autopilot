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
from services.generator.factory import get_llm_client
from services.generator.prompts import build_section_regenerate_prompt
from services.publisher.wordpress import WordPressPublisher
from core.config import settings
from ui.ui_utils import render_safe_image

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

    # 2. Quality Scorecard Bento Strip
    score = scorecard.total_score
    score_fg = "#15803d" if score >= 85 else ("#b45309" if score >= 70 else "#b91c1c")
    site_name = sites_map[draft.wp_site_id].name if draft.wp_site_id in sites_map else "No target site configured"

    st.markdown(f"""
    <div style="background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 16px; padding: 18px 22px; box-shadow: 0 4px 16px rgba(0,0,0,0.04); margin-bottom: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="font-size: 2.2rem; font-weight: 800; color: {score_fg}; letter-spacing: -0.03em;">{score}<span style="font-size: 1.1rem; color: #86868b; font-weight: 500;">/100</span></div>
                <div>
                    <div style="font-weight: 700; font-size: 1.0rem; color: #1d1d1f; letter-spacing: -0.01em;">Audited Quality Score</div>
                    <div style="font-size: 0.82rem; color: #86868b;">{scorecard.word_count} words • Target: <strong>{site_name}</strong> • Status: <strong>{STATUS_COLORS.get(draft.status, draft.status)}</strong></div>
                </div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <span class="apple-pill-badge" style="background: {'rgba(52,199,89,0.09)' if scorecard.has_ftc_disclosure else 'rgba(239,68,68,0.09)'}; color: {'#15803d' if scorecard.has_ftc_disclosure else '#b91c1c'}; border: 1px solid {'rgba(52,199,89,0.25)' if scorecard.has_ftc_disclosure else 'rgba(239,68,68,0.25)'};">
                    FTC: {'✅ Present' if scorecard.has_ftc_disclosure else '❌ Missing'}
                </span>
                <span class="apple-pill-badge" style="background: {'rgba(52,199,89,0.09)' if scorecard.has_price_disclaimer else 'rgba(239,68,68,0.09)'}; color: {'#15803d' if scorecard.has_price_disclaimer else '#b91c1c'}; border: 1px solid {'rgba(52,199,89,0.25)' if scorecard.has_price_disclaimer else 'rgba(239,68,68,0.25)'};">
                    Price Disclaimer: {'✅ Present' if scorecard.has_price_disclaimer else '❌ Missing'}
                </span>
                <span class="apple-pill-badge" style="background: {'rgba(52,199,89,0.09)' if scorecard.has_schema_markup else 'rgba(239,68,68,0.09)'}; color: {'#15803d' if scorecard.has_schema_markup else '#b91c1c'}; border: 1px solid {'rgba(52,199,89,0.25)' if scorecard.has_schema_markup else 'rgba(239,68,68,0.25)'};">
                    Schema JSON-LD: {'✅ Valid' if scorecard.has_schema_markup else '❌ Missing'}
                </span>
                <span class="apple-pill-badge" style="background: {'rgba(52,199,89,0.09)' if scorecard.has_comparison_table else 'rgba(0,0,0,0.04)'}; color: {'#15803d' if scorecard.has_comparison_table else '#64748b'}; border: 1px solid {'rgba(52,199,89,0.25)' if scorecard.has_comparison_table else 'rgba(0,0,0,0.08)'};">
                    Table: {'✅ Rendered' if scorecard.has_comparison_table else '—'}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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
            with st.expander(f"{idx+1}. {prod.badge or 'Product'}: {prod.title[:38]}...", expanded=idx == 0):
                if prod.main_image:
                    render_safe_image(prod.main_image, use_container_width=True)
                
                st.markdown(f"""
                <div style="display: flex; gap: 8px; align-items: center; margin: 8px 0;">
                    <span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.09); color: #0071e3; font-weight: 700; border: 1px solid rgba(0, 113, 227, 0.2);">
                        {prod.price or 'Price N/A'}
                    </span>
                    <span style="font-size: 0.8rem; color: #86868b;">ASIN: <code>{prod.asin}</code></span>
                </div>
                """, unsafe_allow_html=True)
                
                st.caption(f"Source: `{prod.provenance or 'Amazon Safe Scraper'}`")
                if prod.rating:
                    st.markdown(f"**Customer Rating:** ⭐ **{prod.rating}/5** ({prod.review_count or 0:,} reviews)")
                if prod.affiliate_url:
                    st.link_button("🔗 Verified Affiliate Link", prod.affiliate_url, use_container_width=True)
                if prod.features:
                    st.markdown("**Key Specs & Testing Notes:**")
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
            html_preview = markdown.markdown(draft.content_markdown, extensions=["tables", "fenced_code", "nl2br"])
            st.markdown(f'<div class="apple-prose-container">{html_preview}</div>', unsafe_allow_html=True)

        with tab_raw_md:
            edit_markdown = st.text_area(
                "Article Markdown",
                value=draft.content_markdown,
                height=520
            )

        with tab_html:
            st.code(draft.schema_json_ld, language="html")

        # AI Section Regenerator
        active_provider = getattr(settings, "get_active_provider", lambda: getattr(settings, "AI_PROVIDER", "openai"))()
        active_model_name = "GPT-6 Luna" if active_provider == "openai" else "Gemini"

        with st.expander(f"🪄 AI Section Regenerator (Powered by {active_model_name})"):
            st.caption(f"Select a quick preset or type custom instructions to rewrite any section using **{active_model_name}**.")
            
            # Quick preset buttons for instant UX
            p_col1, p_col2, p_col3, p_col4 = st.columns(4)
            with p_col1:
                if st.button("✨ Polish Tone", key="p_btn_tone", use_container_width=True):
                    st.session_state["regen_preset_val"] = "Make the tone authoritative, engaging, and flow naturally with seamless transitions."
            with p_col2:
                if st.button("⚖️ Add Specs/Data", key="p_btn_comp", use_container_width=True):
                    st.session_state["regen_preset_val"] = "Add concrete comparison metrics, technical specs context, and value analysis."
            with p_col3:
                if st.button("🔍 Expand Cons/Tradeoffs", key="p_btn_cons", use_container_width=True):
                    st.session_state["regen_preset_val"] = "Expand on real-world testing observations, ergonomic trade-offs, and critical drawbacks."
            with p_col4:
                if st.button("⚡ Make Punchy", key="p_btn_conc", use_container_width=True):
                    st.session_state["regen_preset_val"] = "Tighten the prose, remove fluff, and make it crisp and skimmable for mobile readers."

            default_inst = st.session_state.get("regen_preset_val", "")
            regen_input = st.text_area("Section Text to Rewrite", placeholder="Paste section here...", key="regen_text_rev", height=110)
            regen_inst = st.text_input("Instruction / Focus", value=default_inst, placeholder="e.g. Polish tone, add comparison points...", key="regen_inst_rev")
            
            if st.button(f"✨ Regenerate Section with {active_model_name}", key="regen_btn_rev", type="primary"):
                if not regen_input.strip() or not regen_inst.strip():
                    st.warning("Please provide both the section text and an instruction.")
                else:
                    with st.spinner(f"Rewriting section with {active_model_name}..."):
                        client = get_llm_client()
                        prompt = build_section_regenerate_prompt(regen_input, regen_inst)
                        revised_output = client.generate_text(prompt)
                        st.session_state["last_revised_section"] = revised_output
                        st.session_state["last_target_section"] = regen_input.strip()

            revised_text = st.session_state.get("last_revised_section")
            target_text = st.session_state.get("last_target_section")

            if revised_text:
                st.markdown("##### 📝 Revised Markdown Preview:")
                st.text_area("Revised Markdown", value=revised_text, height=140, key="revised_md_preview_box")
                
                col_rev_act1, col_rev_act2 = st.columns([1.5, 1])
                with col_rev_act1:
                    if st.button("📥 Apply Revision to Article Draft", type="primary", use_container_width=True, key="btn_apply_rev_direct"):
                        # Save undo snapshot
                        st.session_state[f"undo_draft_{draft.id}"] = draft.content_markdown
                        if target_text and target_text in draft.content_markdown:
                            draft.content_markdown = draft.content_markdown.replace(target_text, revised_text, 1)
                        else:
                            draft.content_markdown = draft.content_markdown + "\n\n" + revised_text
                        
                        html_body = markdown.markdown(draft.content_markdown, extensions=["tables", "fenced_code", "nl2br"])
                        draft.content_html = enforce_nofollow_sponsored(html_body)
                        draft.quality_scorecard = audit_article_quality(draft)
                        save_draft(draft)
                        st.session_state.pop("last_revised_section", None)
                        st.session_state.pop("last_target_section", None)
                        st.toast("✅ Applied revised section directly into draft!", icon="✨")
                        st.rerun()

                with col_rev_act2:
                    if f"undo_draft_{draft.id}" in st.session_state:
                        if st.button("↩️ Revert Revision (Undo)", use_container_width=True, key="btn_undo_rev_direct"):
                            draft.content_markdown = st.session_state.pop(f"undo_draft_{draft.id}")
                            html_body = markdown.markdown(draft.content_markdown, extensions=["tables", "fenced_code", "nl2br"])
                            draft.content_html = enforce_nofollow_sponsored(html_body)
                            draft.quality_scorecard = audit_article_quality(draft)
                            save_draft(draft)
                            st.toast("↩️ Draft reverted to previous state!", icon="🔄")
                            st.rerun()

        # 5. Apple Control Center Action Dock
        st.markdown(f"""
        <div class="apple-action-dock">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="apple-beacon-dot" style="background: #0071e3;"></span>
                    <span style="font-weight: 700; font-size: 0.95rem; color: #1d1d1f; letter-spacing: -0.01em;">⚡ Editorial Execution & Publishing Dock</span>
                </div>
                <div style="font-size: 0.8rem; color: #86868b;">
                    Current Status: <strong style="color: #1d1d1f;">{STATUS_COLORS.get(draft.status, draft.status)}</strong>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
                st.success("✅ Changes saved & quality re-audited!")
                st.rerun()
            st.caption("💾 Re-audits & saves edits")

        with act_col2:
            if st.button("✅ Approve Draft", use_container_width=True):
                update_draft_status(draft.id, ArticleStatus.APPROVED)
                st.success("Draft Approved! Ready for publishing.")
                st.rerun()
            st.caption("✅ Signs off quality for queue")

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
            st.caption("📅 Queues to WP at set time")

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
            st.caption("🚀 Immediate live WordPress push")
