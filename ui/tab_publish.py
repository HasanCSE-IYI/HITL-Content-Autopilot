import streamlit as st
from core.models import ArticleStatus
from core.config import settings
from core.database import list_drafts, get_draft, update_draft_status
from services.publisher.wordpress import WordPressPublisher

def render_publish_tab():
    st.subheader("🌐 WordPress One-Click Publisher")
    st.caption("Publish your approved affiliate articles directly to your WordPress site with SEO metadata and featured images.")

    publisher = WordPressPublisher()
    is_configured = publisher.is_configured()

    if not is_configured:
        st.warning("⚠️ WordPress credentials are not configured yet. Please configure them in the **Settings & API Keys** tab first.")
        return

    # Check connection
    col_stat1, col_stat2 = st.columns([3, 1])
    with col_stat1:
        st.info(f"Connected to WordPress Site: **{settings.WORDPRESS_URL}** (User: `{settings.WORDPRESS_USERNAME}`)")
    with col_stat2:
        if st.button("🔄 Test Connection"):
            res = publisher.test_connection()
            if res["success"]:
                st.success(res["message"])
            else:
                st.error(res["message"])

    st.markdown("---")

    # Select article to publish
    approved_drafts = list_drafts(status=ArticleStatus.APPROVED)
    all_drafts = list_drafts()

    if not approved_drafts and not all_drafts:
        st.info("ℹ️ No articles in database. Please generate an article first!")
        return

    show_all = st.checkbox("Show all articles (including non-approved)", value=not bool(approved_drafts))
    selectable_drafts = all_drafts if show_all else approved_drafts

    if not selectable_drafts:
        st.warning("⚠️ No approved articles ready for publishing. Please approve a draft in the 'HITL Review Queue' tab or check 'Show all articles'.")
        return

    draft_options = {d.id: f"[{d.id}] {d.title[:65]}... (Status: {d.status.upper()})" for d in selectable_drafts}
    selected_id = st.selectbox(
        "Choose Article to Publish",
        options=list(draft_options.keys()),
        format_func=lambda x: draft_options[x]
    )

    draft = get_draft(selected_id)
    if not draft:
        return

    st.markdown("### ⚙️ Publishing Options")
    col_opt1, col_opt2 = st.columns(2)

    with col_opt1:
        post_status = st.selectbox(
            "WordPress Post Status",
            options=["draft", "publish", "pending"],
            index=0 if settings.WORDPRESS_DEFAULT_STATUS == "draft" else 1,
            help="'draft' creates a draft in WP admin for safety; 'publish' goes live immediately."
        )

    with col_opt2:
        # Fetch live WP categories
        categories = publisher.get_categories()
        selected_cat_ids = []
        if categories:
            cat_map = {c["id"]: c["name"] for c in categories}
            chosen_names = st.multiselect("Assign Categories", options=list(cat_map.values()))
            selected_cat_ids = [cid for cid, name in cat_map.items() if name in chosen_names]
        else:
            st.caption("No categories found or could not fetch from WordPress.")

    # Image upload toggle
    has_image = bool(draft.products and draft.products[0].main_image)
    upload_img = st.checkbox(
        "Auto-upload primary product image as WordPress Featured Image",
        value=has_image,
        disabled=not has_image
    )

    st.markdown("---")
    pub_btn = st.button("🚀 Publish to WordPress Now", type="primary", use_container_width=True)

    if pub_btn:
        with st.spinner("Publishing post and uploading media to WordPress..."):
            res = publisher.publish_article(
                draft=draft,
                status=post_status,
                category_ids=selected_cat_ids
            )

            if res["success"]:
                post_id = res.get("post_id")
                link = res.get("link")
                update_draft_status(
                    draft.id,
                    status=ArticleStatus.PUBLISHED,
                    wordpress_post_id=post_id,
                    published_url=link
                )
                st.balloons()
                st.success(f"🎉 Article published successfully! (Post ID: {post_id})")
                if link:
                    st.markdown(f"👉 **[Click here to view post on your website]({link})**")
            else:
                st.error(f"❌ Failed to publish: {res['message']}")

    # 4. Published History
    st.markdown("---")
    st.markdown("### 📜 Published Articles History")
    published_list = list_drafts(status=ArticleStatus.PUBLISHED)
    if not published_list:
        st.caption("No published articles yet.")
    else:
        for p in published_list:
            col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
            with col_h1:
                st.markdown(f"**{p.title}**")
            with col_h2:
                st.caption(f"Post ID: `{p.wordpress_post_id}`")
            with col_h3:
                if p.published_url:
                    st.link_button("🌐 View Live", p.published_url, use_container_width=True)
