import streamlit as st
import markdown
from core.models import ArticleStatus
from core.database import list_drafts, get_draft, save_draft, delete_draft, update_draft_status
from services.compliance.rules import enforce_nofollow_sponsored
from services.generator.gemini_client import GeminiClient
from services.generator.prompts import build_section_regenerate_prompt

STATUS_COLORS = {
    ArticleStatus.NEEDS_REVIEW: "🟡 Needs Review",
    ArticleStatus.DRAFT: "🔵 Draft",
    ArticleStatus.APPROVED: "🟢 Approved",
    ArticleStatus.PUBLISHED: "🟣 Published"
}

def render_review_tab():
    st.subheader("📝 Human-In-The-Loop (HITL) Review Queue")
    st.caption("Review AI-generated drafts, edit content, regenerate sections, and approve articles for publishing.")

    # 1. Filter and select draft
    col_filter, col_select = st.columns([1, 3])
    with col_filter:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["all", ArticleStatus.NEEDS_REVIEW, ArticleStatus.DRAFT, ArticleStatus.APPROVED, ArticleStatus.PUBLISHED],
            format_func=lambda x: "All Statuses" if x == "all" else STATUS_COLORS.get(x, x)
        )

    drafts = list_drafts(status=status_filter)
    if not drafts:
        st.info("ℹ️ No drafts found matching this filter. Generate a new article in the 'Generate Article' tab!")
        return

    with col_select:
        draft_options = {d.id: f"[{d.id}] {d.title[:60]}... ({d.status.upper()})" for d in drafts}
        selected_id = st.selectbox(
            "Select Article to Review",
            options=list(draft_options.keys()),
            format_func=lambda x: draft_options[x]
        )

    draft = get_draft(selected_id)
    if not draft:
        st.error("Draft not found.")
        return

    st.markdown("---")

    # 2. Status Banner & Quick Actions
    col_badge, col_type, col_kw, col_actions = st.columns([1, 1, 1, 2])
    with col_badge:
        st.markdown(f"**Status:** {STATUS_COLORS.get(draft.status, draft.status)}")
    with col_type:
        st.markdown(f"**Type:** `{draft.article_type.upper()}`")
    with col_kw:
        st.markdown(f"**Keyword:** `{draft.target_keyword}`")
    with col_actions:
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("✅ Approve", use_container_width=True, type="primary"):
                update_draft_status(draft.id, ArticleStatus.APPROVED)
                st.success("Draft marked as APPROVED! You can now publish it in the 'WordPress Publish' tab.")
                st.rerun()
        with b2:
            if st.button("⏪ Revert to Draft", use_container_width=True):
                update_draft_status(draft.id, ArticleStatus.DRAFT)
                st.info("Status set to DRAFT.")
                st.rerun()
        with b3:
            if st.button("🗑️ Delete", use_container_width=True):
                delete_draft(draft.id)
                st.warning("Draft deleted.")
                st.rerun()

    st.markdown("---")

    # 3. Side-by-side Product Preview & Content Editor
    col_products, col_editor = st.columns([1, 2])

    with col_products:
        st.markdown("### 📦 Products Included")
        for idx, prod in enumerate(draft.products):
            with st.expander(f"{idx+1}. {prod.badge or 'Product'}: {prod.title[:40]}...", expanded=idx == 0):
                if prod.main_image:
                    st.image(prod.main_image, use_container_width=True)
                st.markdown(f"**ASIN:** `{prod.asin}`")
                st.markdown(f"**Price:** `{prod.price}`")
                if prod.rating:
                    st.markdown(f"**Rating:** ⭐ {prod.rating}/5 ({prod.review_count or 0} reviews)")
                if prod.affiliate_url:
                    st.link_button("🔗 View Affiliate Link", prod.affiliate_url, use_container_width=True)
                if prod.features:
                    st.markdown("**Specs Highlights:**")
                    for feat in prod.features[:4]:
                        st.markdown(f"- {feat}")

    with col_editor:
        st.markdown("### ✏️ Content & SEO Editor")

        edit_title = st.text_input("Article Title (H1)", value=draft.title)
        col_slug, col_kw_edit = st.columns(2)
        with col_slug:
            edit_slug = st.text_input("URL Slug", value=draft.slug)
        with col_kw_edit:
            edit_meta_title = st.text_input("SEO Meta Title", value=draft.meta_title)

        edit_meta_desc = st.text_area("Meta Description (150-160 chars)", value=draft.meta_description, height=70)

        # Tabbed preview / editor
        tab_preview, tab_raw_md, tab_html = st.tabs(["👁️ Live Preview", "📝 Markdown Editor", "🏷️ HTML & Schema"])

        with tab_preview:
            st.markdown(draft.content_markdown)

        with tab_raw_md:
            edit_markdown = st.text_area(
                "Article Markdown",
                value=draft.content_markdown,
                height=550,
                help="Edit the markdown directly. Changes will be saved upon clicking 'Save Changes'."
            )

        with tab_html:
            st.caption("Auto-generated HTML & JSON-LD Schema markup for Google Rich Snippets:")
            st.code(draft.schema_json_ld, language="html")

        # 4. AI Section Regenerator
        with st.expander("🪄 AI Section Regenerator (Refine with Gemini)"):
            st.caption("Need to rewrite or improve a specific section? Paste the text below and give instructions.")
            regen_input = st.text_area("Section Text to Rewrite", placeholder="Paste paragraph or heading text here...")
            regen_inst = st.text_input("Instruction", placeholder="e.g. Make it more persuasive, add more comparison points, shorten the intro...")
            if st.button("✨ Regenerate Section with Gemini"):
                client = GeminiClient()
                if not client.is_configured():
                    st.error("Gemini API key not configured!")
                elif not regen_input.strip() or not regen_inst.strip():
                    st.warning("Please provide both the original text and an instruction.")
                else:
                    with st.spinner("Rewriting section with Gemini..."):
                        prompt = build_section_regenerate_prompt(regen_input, regen_inst)
                        revised_text = client.generate_text(prompt)
                        st.success("Revised Version:")
                        st.text_area("Revised Markdown", value=revised_text, height=200)
                        st.info("Copy and paste the revised markdown above into the Markdown Editor tab, then click 'Save Changes'.")

        # 5. Save changes
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            draft.title = edit_title.strip()
            draft.slug = edit_slug.strip()
            draft.meta_title = edit_meta_title.strip()
            draft.meta_description = edit_meta_desc.strip()
            draft.content_markdown = edit_markdown
            # Recompute HTML
            html_body = markdown.markdown(edit_markdown, extensions=["tables", "fenced_code", "nl2br"])
            draft.content_html = enforce_nofollow_sponsored(html_body)
            save_draft(draft)
            st.success("✅ Changes saved successfully!")
            st.rerun()
