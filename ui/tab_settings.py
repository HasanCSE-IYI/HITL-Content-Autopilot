import streamlit as st
from core.config import settings
from core.database import (
    save_asin_preset,
    get_asin_presets,
    delete_asin_preset,
    get_setting,
    set_setting
)
from services.publisher.wordpress import WordPressPublisher
from services.generator.gemini_client import GeminiClient, SUPPORTED_GEMINI_MODELS

def render_settings_tab():
    st.subheader("⚙️ System Configuration & Credentials")
    st.caption("All settings are permanently saved to the local database and persist across reboots.")

    # 1. Gemini AI Settings
    st.markdown("### 🤖 Google Gemini AI Settings")
    st.caption("Get your free API key from [Google AI Studio](https://aistudio.google.com/).")

    current_key = settings.get_gemini_api_key()
    gemini_key = st.text_input(
        "Gemini API Key",
        value=current_key,
        type="password",
        placeholder="AIzaSy...",
        help="Paste your Google Gemini API Key here.",
        key="settings_gemini_key_input"
    )

    current_model = settings.GEMINI_MODEL
    model_index = SUPPORTED_GEMINI_MODELS.index(current_model) if current_model in SUPPORTED_GEMINI_MODELS else 0
    gemini_model = st.selectbox(
        "Gemini Model",
        options=SUPPORTED_GEMINI_MODELS,
        index=model_index,
        help="gemini-3.8-flash is the latest recommended model.",
        key="settings_gemini_model_select"
    )

    timeout_val = st.slider(
        "API Request Timeout (seconds)",
        min_value=30,
        max_value=180,
        value=getattr(settings, "GEMINI_TIMEOUT", 60),
        step=15,
        help="Increase this if you experience 'Read timed out' errors due to slow internet or VPN."
    )

    col_save_gemini, col_test_gemini = st.columns([1, 1])
    with col_save_gemini:
        if st.button("💾 Save Gemini Key & Model", use_container_width=True, type="primary"):
            if gemini_key.strip():
                settings.save(
                    gemini_api_key=gemini_key.strip(),
                    gemini_model=gemini_model,
                    gemini_timeout=timeout_val
                )
                st.session_state["gemini_api_key"] = gemini_key.strip()
                st.success("✅ Gemini API Key, Model & Timeout permanently saved!")
            else:
                st.warning("Please enter a valid API key.")

    with col_test_gemini:
        if st.button("🔌 Test Gemini Connection", use_container_width=True):
            test_client = GeminiClient(
                api_key=gemini_key.strip(),
                model=gemini_model,
                timeout=timeout_val
            )
            with st.spinner("Testing connection to Google Gemini (with auto-retry)..."):
                res = test_client.test_api_key()
                if res["success"]:
                    st.success(f"✅ {res['message']}")
                    # Auto-save verified key
                    settings.save(
                        gemini_api_key=gemini_key.strip(),
                        gemini_model=gemini_model,
                        gemini_timeout=timeout_val
                    )
                    st.session_state["gemini_api_key"] = gemini_key.strip()
                else:
                    st.error(f"❌ {res['message']}")

    st.markdown("---")

    # 2. Amazon Associates Settings
    st.markdown("### 🛒 Amazon Associates Settings")
    associate_tag = st.text_input(
        "Amazon Associate Tracking Tag",
        value=settings.AMAZON_ASSOCIATE_TAG,
        help="E.g. myaffiliatesite-20",
        key="settings_amazon_tag_input"
    )
    country = st.selectbox(
        "Amazon Store Marketplace",
        options=["com", "co.uk", "ca", "de", "fr", "in"],
        index=["com", "co.uk", "ca", "de", "fr", "in"].index(settings.AMAZON_COUNTRY) if settings.AMAZON_COUNTRY in ["com", "co.uk", "ca", "de", "fr", "in"] else 0,
        key="settings_amazon_country_select"
    )

    with st.expander("Optional: Amazon PA-API 5.0 Credentials (if approved)"):
        st.info("If you do not have PA-API 5.0 keys yet, leave these blank. The built-in Smart Scraper will automatically fetch product details!")
        access_key = st.text_input("PA-API Access Key", value=settings.AMAZON_ACCESS_KEY, type="password", key="settings_paapi_access_key")
        secret_key = st.text_input("PA-API Secret Key", value=settings.AMAZON_SECRET_KEY, type="password", key="settings_paapi_secret_key")

    if st.button("💾 Save Amazon Settings", type="primary"):
        settings.save(
            amazon_associate_tag=associate_tag.strip(),
            amazon_country=country,
            amazon_access_key=access_key.strip(),
            amazon_secret_key=secret_key.strip()
        )
        st.success("✅ Amazon Associate Tag & settings permanently saved!")

    st.markdown("---")

    # 3. ASIN Presets Manager
    st.markdown("### 📦 Saved ASIN & Product Presets")
    st.caption("Save frequently used lists of ASINs and target keywords so you can load them anytime.")

    with st.expander("➕ Save New ASIN Preset"):
        p_name = st.text_input("Preset Name", placeholder="e.g. Ergonomic Office Chairs 2026")
        p_kw = st.text_input("Default Keyword", placeholder="e.g. Best Ergonomic Office Chairs")
        p_asins = st.text_area("ASINs or URLs (one per line)", placeholder="B08N5WRWNW\nB09V3HN1KC...")
        if st.button("💾 Save Preset"):
            if p_name.strip() and p_asins.strip():
                save_asin_preset(p_name.strip(), p_asins.strip(), p_kw.strip())
                st.success(f"Preset '{p_name}' saved!")
                st.rerun()
            else:
                st.error("Please enter a preset name and at least one ASIN.")

    existing_presets = get_asin_presets()
    if existing_presets:
        st.markdown("#### Existing Presets:")
        for ep in existing_presets:
            col_p1, col_p2 = st.columns([4, 1])
            with col_p1:
                st.markdown(f"**{ep['name']}** (Keyword: `{ep.get('keyword', 'N/A')}`) - {len(ep['asins'].splitlines())} items")
            with col_p2:
                if st.button("🗑️ Delete", key=f"del_preset_{ep['id']}"):
                    delete_asin_preset(ep["id"])
                    st.success("Preset deleted.")
                    st.rerun()

    st.markdown("---")

    # 4. WordPress Settings
    st.markdown("### 🌐 WordPress REST API Settings")
    st.caption("Use a WordPress Application Password (Users > Profile > Application Passwords).")
    wp_url = st.text_input("WordPress Site URL", value=settings.WORDPRESS_URL, placeholder="https://yourwebsite.com", key="settings_wp_url")
    wp_user = st.text_input("WordPress Username", value=settings.WORDPRESS_USERNAME, key="settings_wp_user")
    wp_pass = st.text_input("Application Password", value=settings.WORDPRESS_APP_PASSWORD, type="password", key="settings_wp_pass")

    col_save_wp, col_test_wp = st.columns([1, 1])
    with col_save_wp:
        if st.button("💾 Save WordPress Settings", use_container_width=True, type="primary"):
            settings.save(
                wordpress_url=wp_url.strip(),
                wordpress_username=wp_user.strip(),
                wordpress_app_password=wp_pass.strip()
            )
            st.success("✅ WordPress settings permanently saved!")

    with col_test_wp:
        if st.button("🔌 Test WordPress Connection", use_container_width=True):
            publisher = WordPressPublisher(
                wp_url=wp_url.strip(),
                username=wp_user.strip(),
                app_password=wp_pass.strip()
            )
            result = publisher.test_connection()
            if result["success"]:
                st.success(f"✅ {result['message']}")
            else:
                st.error(f"❌ {result['message']}")
