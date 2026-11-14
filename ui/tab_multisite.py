import streamlit as st
from datetime import datetime
from core.models import WordPressSite
from core.database import (
    add_wordpress_site,
    update_wordpress_site,
    delete_wordpress_site,
    list_wordpress_sites,
    set_default_wordpress_site
)
from services.publisher.wordpress import WordPressPublisher

def render_multisite_tab():
    st.subheader("🌐 Multi-Site WordPress Manager & Taxonomy Sync")
    st.caption("Connect multiple WordPress affiliate niche sites, auto-sync their categories and tags, and manage multi-site publishing.")

    sites = list_wordpress_sites()

    # 1. Add New Site Form
    with st.expander("➕ Connect New WordPress Site", expanded=len(sites) == 0):
        with st.form("add_site_form"):
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                name = st.text_input("Site Nickname", placeholder="e.g. Ergonomic Office Hub")
                url = st.text_input("WordPress URL", placeholder="https://example.com")
            with col_s2:
                username = st.text_input("WP Username", placeholder="admin")
                app_password = st.text_input("Application Password", placeholder="xxxx xxxx xxxx xxxx", type="password")
            
            is_default = st.checkbox("Set as default publishing site", value=len(sites) == 0)
            submitted = st.form_submit_button("🔌 Save & Test Connection", use_container_width=True, type="primary")

            if submitted:
                if not name.strip() or not url.strip() or not username.strip() or not app_password.strip():
                    st.error("Please fill in all site connection fields.")
                else:
                    new_site = WordPressSite(
                        name=name.strip(),
                        url=url.strip().rstrip("/"),
                        username=username.strip(),
                        app_password=app_password.strip(),
                        is_default=is_default
                    )
                    saved = add_wordpress_site(new_site)
                    st.success(f"Site '{saved.name}' added successfully!")
                    
                    # Test connection & initial sync immediately
                    publisher = WordPressPublisher(site=saved)
                    test_res = publisher.test_connection()
                    if test_res["success"]:
                        st.info("Testing connection: Successful! Syncing categories...")
                        sync_res = publisher.sync_taxonomies(saved.id)
                        if sync_res["success"]:
                            st.success(f"Auto-synced {sync_res['categories_count']} categories and {sync_res['tags_count']} tags!")
                    else:
                        st.warning(f"Connection warning: {test_res['message']}")
                    st.rerun()

    st.markdown("---")

    # 2. List Connected Sites
    if not sites:
        st.info("ℹ️ No WordPress sites connected yet. Connect your first site above!")
        return

    st.markdown(f"### 📋 Connected WordPress Sites ({len(sites)})")

    for site in sites:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                default_badge = " ⭐ (Default)" if site.is_default else ""
                st.markdown(f"#### {site.name}{default_badge}")
                st.caption(f"🔗 `{site.url}` | User: `{site.username}`")
            with col2:
                cat_count = len(site.categories)
                tag_count = len(site.tags)
                st.markdown(f"**Taxonomies:** {cat_count} Cats / {tag_count} Tags")
                last_sync = site.last_synced_at[:16].replace("T", " ") if site.last_synced_at else "Never"
                st.caption(f"Last sync: {last_sync}")
            with col3:
                if st.button("🔄 Sync Taxonomies", key=f"sync_btn_{site.id}", use_container_width=True):
                    with st.spinner("Fetching categories and tags from WordPress..."):
                        publisher = WordPressPublisher(site=site)
                        res = publisher.sync_taxonomies(site.id)
                        if res["success"]:
                            st.success(f"Synced {res['categories_count']} categories and {res['tags_count']} tags!")
                            st.rerun()
                        else:
                            st.error(f"Sync failed: {res['message']}")
            with col4:
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if not site.is_default and st.button("⭐ Default", key=f"def_btn_{site.id}"):
                        set_default_wordpress_site(site.id)
                        st.rerun()
                with btn_col2:
                    if st.button("🗑️ Delete", key=f"del_site_{site.id}"):
                        delete_wordpress_site(site.id)
                        st.warning(f"Deleted {site.name}")
                        st.rerun()

            # Taxonomy viewer accordion
            if site.categories or site.tags:
                with st.expander(f"📁 View Synced Taxonomies for '{site.name}'"):
                    t_col1, t_col2 = st.columns(2)
                    with t_col1:
                        st.markdown("**Categories:**")
                        cat_list = [f"- **{c['name']}** (ID: `{c['id']}`, {c.get('count', 0)} posts)" for c in site.categories]
                        st.markdown("\n".join(cat_list[:30]) if cat_list else "No categories found.")
                    with t_col2:
                        st.markdown("**Tags:**")
                        tag_list = [f"- **{t['name']}** (ID: `{t['id']}`, {t.get('count', 0)} posts)" for t in site.tags]
                        st.markdown("\n".join(tag_list[:30]) if tag_list else "No tags found.")

            st.markdown("---")
