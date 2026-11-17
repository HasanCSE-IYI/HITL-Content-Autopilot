import os
import streamlit as st
from core.config import (
    settings,
    SUPPORTED_OPENAI_MODELS,
    DEFAULT_OPENAI_MODEL,
    IMAGE_MODEL,
    SUPPORTED_IMAGE_QUALITIES,
    DEFAULT_IMAGE_QUALITY,
    SUPPORTED_AI_PROVIDERS
)
from core.database import (
    DB_PATH,
    save_asin_preset,
    get_asin_presets,
    delete_asin_preset,
    list_wordpress_sites,
    list_drafts,
    get_token_usage_summary,
    clear_llm_cache,
    purge_all_drafts,
    purge_mock_test_drafts
)
from services.publisher.wordpress import WordPressPublisher
from services.generator.gemini_client import GeminiClient, SUPPORTED_GEMINI_MODELS
from services.generator.openai_client import OpenAIClient
from services.media.image_generator import create_article_hero_image
from services.amazon.csv_importer import generate_product_facts_csv_template, generate_bulk_keywords_csv_template
from ui.ui_utils import render_safe_image

def render_settings_tab():
    st.subheader("⚙️ System Configuration & Credentials")
    st.caption("All settings are permanently saved to the local SQLite database and persist across reboots.")

    # 0. Active AI Provider Selector
    st.markdown("### 🧠 Default AI Engine Provider")
    curr_provider = settings.AI_PROVIDER
    provider_idx = 0 if curr_provider == "openai" else 1
    selected_provider = st.radio(
        "Active AI Provider for Article Generation & Research",
        options=["openai", "gemini"],
        format_func=lambda x: "🤖 OpenAI (Text: GPT-6 Luna | Image: Image 2.5 Flare)" if x == "openai" else "✨ Google Gemini (Gemini 3.8 Flash / Pro)",
        index=provider_idx,
        horizontal=True,
        key="settings_active_provider_radio"
    )
    if selected_provider != curr_provider:
        settings.save(ai_provider=selected_provider)
        st.success(f"Default AI Provider set to **{selected_provider.upper()}**!")
        st.rerun()

    st.markdown("---")

    # 1. AI Provider Tabs: OpenAI & Gemini
    ai_tab_openai, ai_tab_gemini = st.tabs(["🤖 OpenAI Settings (GPT-6 Luna & Image 2.5 Flare)", "✨ Google Gemini Settings"])

    with ai_tab_openai:
        st.caption("Get your API key from the [OpenAI Platform](https://platform.openai.com/api-keys).")
        current_openai_key = getattr(settings, "get_openai_api_key", lambda: getattr(settings, "OPENAI_API_KEY", ""))()
        openai_key = st.text_input(
            "OpenAI API Key",
            value=current_openai_key,
            type="password",
            placeholder="sk-proj-...",
            help="Paste your OpenAI API Key here.",
            key="settings_openai_key_input"
        )

        st.markdown("#### 📝 Text Model Configuration")
        st.markdown("""
        <div style="background: rgba(0, 113, 227, 0.06); border: 1px solid rgba(0, 113, 227, 0.2); border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
            <span class="apple-beacon-dot" style="background: var(--apple-blue);"></span>
            <div>
                <strong style="color: var(--apple-blue); font-size: 0.95rem;">GPT-6 Luna (gpt-6-luna)</strong>
                <div style="font-size: 0.8rem; color: var(--apple-ink-secondary);">Fast 1M+ context window, optimized token compression & affiliate schema generation.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🎨 Image Model & Quality Configuration")
        st.markdown("""
        <div style="background: rgba(168, 85, 247, 0.06); border: 1px solid rgba(168, 85, 247, 0.2); border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
            <span class="apple-beacon-dot" style="background: var(--apple-purple-light);"></span>
            <div>
                <strong style="color: var(--apple-purple-dark); font-size: 0.95rem;">Image 2.5 Flare (gpt-image-2.5-flare)</strong>
                <div style="font-size: 0.8rem; color: var(--apple-ink-secondary);">Exclusive editorial concept engine with low/medium fidelity speed modes.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        curr_img_q = settings.IMAGE_QUALITY
        q_idx = 0 if curr_img_q == "low" else 1
        img_quality = st.radio(
            "Image Creation Quality Setting",
            options=["low", "medium"],
            index=q_idx,
            format_func=lambda x: "⚡ Low Quality (High speed & lowest latency)" if x == "low" else "✨ Medium Quality (Balanced editorial fidelity)",
            horizontal=True,
            key="settings_image_quality_radio"
        )

        o_timeout_val = st.slider(
            "OpenAI Request Timeout (seconds)",
            min_value=30,
            max_value=180,
            value=getattr(settings, "OPENAI_TIMEOUT", 60),
            step=15,
            help="Timeout for generation requests to OpenAI.",
            key="settings_openai_timeout_slider"
        )

        col_save_openai, col_test_openai, col_test_img = st.columns([1, 1, 1], vertical_alignment="bottom")
        with col_save_openai:
            if st.button("💾 Save OpenAI & Image Settings", use_container_width=True, type="primary", key="btn_save_openai"):
                if openai_key.strip():
                    settings.save(
                        openai_api_key=openai_key.strip(),
                        openai_model="gpt-6-luna",
                        image_quality=img_quality,
                        openai_timeout=o_timeout_val
                    )
                    st.session_state["openai_api_key"] = openai_key.strip()
                    st.toast("💾 OpenAI & Image settings saved!", icon="✅")
                    st.success("✅ OpenAI Key, GPT-6 Luna & Image 2.5 Flare settings saved!")
                else:
                    st.warning("Please enter a valid OpenAI API key.")

        with col_test_openai:
            if st.button("🔌 Test GPT-6 Luna Text", use_container_width=True, key="btn_test_openai"):
                st.toast("Testing connection with GPT-6 Luna...", icon="🔌")
                test_client = OpenAIClient(
                    api_key=openai_key.strip(),
                    model="gpt-6-luna",
                    timeout=o_timeout_val
                )
                with st.spinner("Testing connection with GPT-6 Luna..."):
                    res = test_client.test_api_key()
                    if res["success"]:
                        st.success(f"✅ {res['message']}")
                        settings.save(
                            openai_api_key=openai_key.strip(),
                            openai_model="gpt-6-luna",
                            image_quality=img_quality,
                            openai_timeout=o_timeout_val
                        )
                        st.session_state["openai_api_key"] = openai_key.strip()
                    else:
                        st.error(f"❌ {res['message']}")

        with col_test_img:
            if st.button("🎨 Test Image 2.5 Flare", use_container_width=True, key="btn_test_flare"):
                st.toast("Testing Image 2.5 Flare generation...", icon="🎨")
                test_client = OpenAIClient(
                    api_key=openai_key.strip(),
                    timeout=o_timeout_val
                )
                with st.spinner(f"Generating test graphic with Image 2.5 Flare ({img_quality} quality)..."):
                    img_res = test_client.generate_image(
                        prompt="Clean modern flat vector editorial illustration of a cozy ergonomic workspace, soft pastel lighting",
                        quality=img_quality
                    )
                    if img_res.get("success"):
                        st.success(f"✅ {img_res['message']}")
                        if img_res.get("image_url"):
                            render_safe_image(img_res["image_url"], caption=f"Image 2.5 Flare Sample ({img_quality} quality)", width=320)
                    else:
                        st.error(f"❌ {img_res.get('message')}")

    with ai_tab_gemini:
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
            "Gemini Request Timeout (seconds)",
            min_value=30,
            max_value=180,
            value=getattr(settings, "GEMINI_TIMEOUT", 60),
            step=15,
            help="Increase this if you experience read timeout errors.",
            key="settings_gemini_timeout_slider"
        )

        col_save_gemini, col_test_gemini = st.columns([1, 1], vertical_alignment="bottom")
        with col_save_gemini:
            if st.button("💾 Save Gemini Key & Model", use_container_width=True, type="primary", key="btn_save_gemini"):
                if gemini_key.strip():
                    settings.save(
                        gemini_api_key=gemini_key.strip(),
                        gemini_model=gemini_model,
                        gemini_timeout=timeout_val
                    )
                    st.session_state["gemini_api_key"] = gemini_key.strip()
                    st.toast("💾 Gemini settings permanently saved!", icon="✨")
                    st.success("✅ Gemini API Key & Model permanently saved!")
                else:
                    st.warning("Please enter a valid Gemini API key.")

        with col_test_gemini:
            if st.button("🔌 Test Gemini Connection", use_container_width=True, key="btn_test_gemini"):
                st.toast("Testing Gemini connection...", icon="🔌")
                test_client = GeminiClient(
                    api_key=gemini_key.strip(),
                    model=gemini_model,
                    timeout=timeout_val
                )
                with st.spinner("Testing connection to Google Gemini..."):
                    res = test_client.test_api_key()
                    if res["success"]:
                        st.success(f"✅ {res['message']}")
                        settings.save(
                            gemini_api_key=gemini_key.strip(),
                            gemini_model=gemini_model,
                            gemini_timeout=timeout_val
                        )
                        st.session_state["gemini_api_key"] = gemini_key.strip()
                    else:
                        st.error(f"❌ {res['message']}")

    st.markdown("---")

    # 2. Amazon Associates & Sourcing Settings
    st.markdown("### 🛒 Amazon Associates & Sourcing")
    associate_tag = st.text_input(
        "Default Amazon Associate Tracking Tag",
        value=settings.AMAZON_ASSOCIATE_TAG,
        help="E.g. myaffiliatesite-20",
        key="settings_amazon_tag_input"
    )
    country = st.selectbox(
        "Default Amazon Store Marketplace",
        options=["com", "co.uk", "ca", "de", "fr", "in"],
        index=["com", "co.uk", "ca", "de", "fr", "in"].index(settings.AMAZON_COUNTRY) if settings.AMAZON_COUNTRY in ["com", "co.uk", "ca", "de", "fr", "in"] else 0,
        key="settings_amazon_country_select"
    )

    with st.expander("🔑 Official Amazon PA-API 5.0 Credentials (Optional)"):
        st.info("If you do not have PA-API 5.0 keys yet, leave these blank. The built-in Smart Scraper and Manual Facts mode will automatically source product details without API keys!")
        access_key = st.text_input("PA-API Access Key", value=settings.AMAZON_ACCESS_KEY, type="password", key="settings_paapi_access_key")
        secret_key = st.text_input("PA-API Secret Key", value=settings.AMAZON_SECRET_KEY, type="password", key="settings_paapi_secret_key")

    with st.expander("🌐 HTTP/HTTPS Rotating Proxy Pool (Anti-Block & High-Volume)", expanded=bool(getattr(settings, "AMAZON_SCRAPER_PROXY", ""))):
        st.caption("Add one or multiple proxy IPs/URLs (one per line). The scraper will automatically rotate proxies across requests.")
        current_proxy_val = getattr(settings, "AMAZON_SCRAPER_PROXY", "")
        proxy_input = st.text_area(
            "Proxy List (HTTP / HTTPS / SOCKS5)",
            value=current_proxy_val,
            placeholder="http://user:pass@123.45.67.89:8080\nhttp://98.76.54.32:3128...",
            help="Supports single proxy or multi-line rotating proxies (one per line).",
            key="settings_scraper_proxy_input",
            height=90
        )
        col_prx_test, col_prx_info = st.columns([1, 2], vertical_alignment="center")
        with col_prx_test:
            if st.button("🔌 Test Proxy Connection", use_container_width=True, key="btn_test_proxy"):
                st.toast("Testing proxy connection...", icon="🔌")
                from services.amazon.scraper import parse_proxy_pool, check_proxy_connection
                pool = parse_proxy_pool(proxy_input)
                if not pool:
                    st.warning("Please enter at least one proxy URL to test.")
                else:
                    target_proxy = pool[0]
                    with st.spinner(f"Pinging external network via {target_proxy}..."):
                        res = check_proxy_connection(target_proxy)
                        if res["success"]:
                            st.success(f"✅ {res['message']}")
                        else:
                            st.error(f"❌ {res['message']}")
        with col_prx_info:
            from services.amazon.scraper import parse_proxy_pool
            active_count = len(parse_proxy_pool(proxy_input))
            if active_count > 0:
                st.info(f"🔄 Rotating Pool: **{active_count} active proxies configured**.")
            else:
                st.caption("Direct connection (No proxy). Uses local IP with browser fingerprinting.")

    if st.button("💾 Save Amazon & Sourcing Settings", type="primary", key="btn_save_amazon"):
        settings.save(
            amazon_associate_tag=associate_tag.strip(),
            amazon_country=country,
            amazon_access_key=access_key.strip(),
            amazon_secret_key=secret_key.strip(),
            amazon_scraper_proxy=proxy_input.strip()
        )
        st.toast("💾 Amazon Associate & Sourcing settings saved!", icon="🛒")
        st.success("✅ Amazon Associate, PA-API & Proxy settings permanently saved!")

    st.markdown("---")

    # 3. ASIN Presets Manager
    st.markdown("### 📦 Saved ASIN & Product Presets")
    st.caption("Save frequently used lists of ASINs and target keywords so you can load them anytime.")

    with st.expander("➕ Save New ASIN Preset"):
        p_name = st.text_input("Preset Name", placeholder="e.g. Ergonomic Office Chairs 2026")
        p_kw = st.text_input("Default Keyword", placeholder="e.g. Best Ergonomic Office Chairs")
        p_asins = st.text_area("ASINs or URLs (one per line)", placeholder="B08N5WRWNW\nB09V3HN1KC...")
        if st.button("💾 Save Preset", key="btn_save_preset"):
            if p_name.strip() and p_asins.strip():
                save_asin_preset(p_name.strip(), p_asins.strip(), p_kw.strip())
                st.toast(f"💾 Preset '{p_name}' saved!", icon="📦")
                st.success(f"Preset '{p_name}' saved!")
                st.rerun()
            else:
                st.error("Please enter a preset name and at least one ASIN.")

    existing_presets = get_asin_presets()
    if existing_presets:
        st.markdown("#### Existing Presets:")
        for ep in existing_presets:
            col_p1, col_p2 = st.columns([4, 1], vertical_alignment="center")
            with col_p1:
                st.markdown(f"**{ep['name']}** (Keyword: `{ep.get('keyword', 'N/A')}`) - {len(ep['asins'].splitlines())} items")
            with col_p2:
                with st.popover("🗑️ Delete", use_container_width=True):
                    st.markdown(f"Delete preset **{ep['name']}**?")
                    st.caption("This will permanently remove this saved ASIN preset.")
                    if st.button("🔥 Confirm Delete", type="primary", use_container_width=True, key=f"confirm_del_preset_{ep['id']}"):
                        delete_asin_preset(ep["id"])
                        st.toast(f"🗑️ Preset '{ep['name']}' deleted.", icon="🗑️")
                        st.rerun()

    st.markdown("---")

    # 4. Token Optimization & Response Cache Controls
    st.markdown("### ⚡ AI Token Optimization & Response Cache")
    st.caption("Deterministic prompt caching and title minification prevent unnecessary token burn and reduce API costs.")

    tok_stats = get_token_usage_summary()

    t_c1, t_c2, t_c3, t_c4 = st.columns(4)
    t_c1.metric("Total Tokens Used", f"{tok_stats['total_tokens']:,}")
    t_c2.metric("Cache Hits (100% Free)", f"{tok_stats['cache_hits']}")
    t_c3.metric("Tokens Saved", f"~{tok_stats['estimated_tokens_saved']:,}")
    t_c4.metric("Est. Savings", f"${tok_stats['estimated_cost_saved_usd']}")

    col_cache_tog, col_cache_btn = st.columns([2, 1], vertical_alignment="center")
    with col_cache_tog:
        curr_cache_enabled = getattr(settings, "ENABLE_LLM_CACHE", True)
        enable_cache = st.checkbox(
            "Enable Deterministic LLM Response Caching (Recommended)",
            value=curr_cache_enabled,
            help="When enabled, identical prompts hit local SQLite cache instantly with 0 token spend.",
            key="settings_enable_llm_cache_chk"
        )
        if enable_cache != curr_cache_enabled:
            settings.save(enable_llm_cache=enable_cache)
            st.toast(f"Response cache {'ENABLED' if enable_cache else 'DISABLED'}", icon="⚡")
            st.success(f"Response cache set to **{'ENABLED' if enable_cache else 'DISABLED'}**!")
            st.rerun()

    with col_cache_btn:
        with st.popover("🗑️ Clear LLM Cache", use_container_width=True):
            st.markdown("⚠️ **Clear Cached LLM Responses?**")
            st.caption("This purges all deterministic cache entries from SQLite. Future identical prompts will call the LLM API.")
            if st.button("🔥 Yes, Clear Cache", type="primary", use_container_width=True, key="btn_confirm_clear_llm_cache"):
                cleared = clear_llm_cache()
                st.toast(f"🗑️ Cleared {cleared} cached entries!", icon="⚡")
                st.success(f"Cleared {cleared} cached LLM response entries!")
                st.rerun()

    st.markdown("---")

    # 5. Local Database & System Status
    st.markdown("### 📊 Local-First Database Status")
    sites_count = len(list_wordpress_sites())
    drafts_count = len(list_drafts())
    presets_count = len(existing_presets)

    db_c1, db_c2, db_c3 = st.columns(3)
    db_c1.metric("Connected WP Sites", sites_count)
    db_c2.metric("Saved Drafts", drafts_count)
    db_c3.metric("Saved ASIN Presets", presets_count)

    col_purge1, col_purge2 = st.columns(2, vertical_alignment="center")
    with col_purge1:
        if st.button("🧹 Purge Mock/Test Drafts", use_container_width=True, key="btn_purge_mock_drafts"):
            purged = purge_mock_test_drafts()
            st.toast(f"🧹 Purged {purged} mock drafts!", icon="🧹")
            st.success(f"Purged {purged} mock/test drafts!")
            st.rerun()
    with col_purge2:
        with st.popover("🗑️ Reset All Drafts to Zero", use_container_width=True):
            st.markdown("⚠️ **Danger Zone:** This will permanently delete all article drafts in your local database. This cannot be undone.")
            if st.button("🔥 Yes, Permanently Delete All Drafts", type="primary", use_container_width=True, key="btn_confirm_purge_all"):
                purged = purge_all_drafts()
                st.toast(f"🗑️ Reset: {purged} drafts deleted.", icon="🗑️")
                st.success(f"Reset complete: Deleted {purged} drafts.")
                st.rerun()

    st.caption("All application data is securely hosted locally in SQLite.")

    st.markdown("---")
    st.markdown("### 📦 Project Data Backup & Sourcing Templates (Section 13 & 19)")
    st.caption("Export full SQLite database snapshots for offline safety, and download standardized CSV templates for manual product data & bulk queues.")

    b_col1, b_col2, b_col3 = st.columns(3, vertical_alignment="center")
    with b_col1:
        db_bytes = b""
        if os.path.exists(DB_PATH):
            try:
                with open(DB_PATH, "rb") as f:
                    db_bytes = f.read()
            except Exception:
                pass

        st.download_button(
            "💾 Export Database Backup (.db)",
            data=db_bytes,
            file_name="content_autopilot_backup.db",
            mime="application/x-sqlite3",
            use_container_width=True,
            help="Full local SQLite database backup containing all connected sites, drafts, settings, and cache."
        )

    with b_col2:
        st.download_button(
            "📥 Product Sourcing CSV Template",
            data=generate_product_facts_csv_template(),
            file_name="amazon_product_sourcing_template.csv",
            mime="text/csv",
            use_container_width=True,
            help="Standard CSV template for manual product research (asin, title, price, specs, pros, cons, url)."
        )

    with b_col3:
        st.download_button(
            "📥 Bulk Keywords CSV Template",
            data=generate_bulk_keywords_csv_template(),
            file_name="bulk_keywords_template.csv",
            mime="text/csv",
            use_container_width=True,
            help="Standard CSV template for bulk keyword queue (keyword, asins, article_type)."
        )
