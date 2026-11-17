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
            col_s1, col_s2 = st.columns(2, vertical_alignment="top")
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
                    clean_url = url.strip().rstrip("/")
                    if not clean_url.startswith(("http://", "https://")):
                        clean_url = f"https://{clean_url}"
                    new_site = WordPressSite(
                        name=name.strip(),
                        url=clean_url,
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
        st.markdown("""
        <div class="apple-card-elevated" style="text-align: center; padding: 36px 20px; margin-top: 14px;">
            <div style="font-size: 2.2rem; margin-bottom: 8px;">🌐</div>
            <div style="font-weight: 700; font-size: 1.15rem; color: var(--apple-ink-primary); margin-bottom: 6px;">No WordPress Sites Connected Yet</div>
            <div style="font-size: 0.88rem; color: var(--apple-ink-secondary); max-width: 520px; margin: 0 auto 16px auto;">
                Connect your WordPress niche affiliate websites to enable 1-click publishing, automated schema injection, and category taxonomy synchronization.
            </div>
            <div style="display: inline-flex; justify-content: center; gap: 10px; font-size: 0.82rem; color: var(--apple-ink-secondary); background: var(--apple-surface-secondary); padding: 8px 16px; border-radius: 9999px; border: 1px solid var(--apple-border);">
                <span>1️⃣ Log in to WP Admin</span> ➔ <span>2️⃣ Users > Profile > Application Passwords</span> ➔ <span>3️⃣ Generate Key</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"### 📋 Connected WordPress Sites ({len(sites)})")

    for site in sites:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2.4, 1.8], vertical_alignment="center")
            with col1:
                default_badge = ' <span class="apple-pill-badge" style="background: rgba(255, 149, 0, 0.1); color: var(--apple-amber-deep); border: 1px solid rgba(255, 149, 0, 0.25);">⭐ Primary</span>' if site.is_default else ''
                site_header_html = (
                    '<div style="display: flex; align-items: center; gap: 8px;">'
                    '<span class="apple-beacon-dot" style="background: var(--apple-green);"></span>'
                    f'<span style="font-weight: 700; font-size: 1.05rem; color: var(--apple-ink-primary);">{site.name}</span>'
                    f'{default_badge}'
                    '</div>'
                )
                st.markdown(site_header_html, unsafe_allow_html=True)
                st.caption(f"🔗 `{site.url}` &nbsp;•&nbsp; User: `{site.username}`")
            with col2:
                cat_count = len(site.categories)
                tag_count = len(site.tags)
                if cat_count == 0 and tag_count == 0:
                    tax_badge_html = (
                        '<span class="apple-pill-badge" style="background: rgba(255, 149, 0, 0.1); color: var(--apple-amber-deep); border: 1px solid rgba(255, 149, 0, 0.25);">'
                        '⚠️ Not Synced (Click 🔄 Sync)'
                        '</span>'
                    )
                else:
                    tax_badge_html = (
                        '<span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.08); color: var(--apple-blue); border: 1px solid rgba(0, 113, 227, 0.2);">'
                        f'Taxonomies: {cat_count} Cats / {tag_count} Tags'
                        '</span>'
                    )
                st.markdown(tax_badge_html, unsafe_allow_html=True)
                last_sync = site.last_synced_at[:16].replace("T", " ") if site.last_synced_at else "Never"
                st.caption(f"Last sync: {last_sync}")
            with col3:
                btn_act1, btn_act2 = st.columns(2, vertical_alignment="center")
                with btn_act1:
                    if st.button("🔌 Test", key=f"test_btn_{site.id}", use_container_width=True):
                        publisher = WordPressPublisher(site=site)
                        t_res = publisher.test_connection()
                        if t_res["success"]:
                            st.toast(f"✅ Connection OK: {t_res.get('user', 'Connected')}", icon="🌐")
                            st.success(t_res["message"])
                        else:
                            st.toast("❌ Connection failed", icon="⚠️")
                            st.error(t_res["message"])
                with btn_act2:
                    if st.button("🔄 Sync", key=f"sync_btn_{site.id}", use_container_width=True, type="secondary"):
                        with st.spinner("Fetching categories & tags..."):
                            publisher = WordPressPublisher(site=site)
                            res = publisher.sync_taxonomies(site.id)
                            if res["success"]:
                                st.toast(f"✅ Synced {res['categories_count']} categories!", icon="🔄")
                                st.success(f"Synced {res['categories_count']} categories and {res['tags_count']} tags!")
                                st.rerun()
                            else:
                                st.error(f"Sync failed: {res['message']}")
            with col4:
                btn_col1, btn_col2 = st.columns(2, vertical_alignment="center")
                with btn_col1:
                    if not site.is_default:
                        if st.button("⭐ Default", key=f"def_btn_{site.id}", use_container_width=True):
                            set_default_wordpress_site(site.id)
                            st.toast(f"⭐ Set '{site.name}' as default primary site!", icon="⭐")
                            st.rerun()
                    else:
                        st.markdown('<div style="text-align: center;"><span class="apple-pill-badge" style="background: rgba(255, 149, 0, 0.1); color: var(--apple-amber-deep); border: 1px solid rgba(255, 149, 0, 0.25);">⭐ Primary</span></div>', unsafe_allow_html=True)
                with btn_col2:
                    with st.popover("🗑️ Delete", use_container_width=True):
                        st.markdown(f"Disconnect **{site.name}**?")
                        st.caption("Saved credentials and synced categories will be permanently removed.")
                        if st.button("🔥 Confirm Disconnect", type="primary", use_container_width=True, key=f"confirm_del_site_{site.id}"):
                            delete_wordpress_site(site.id)
                            st.toast(f"🗑️ Disconnected site: {site.name}", icon="🗑️")
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
