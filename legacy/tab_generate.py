import streamlit as st
from typing import List
from core.models import ArticleType
from core.config import settings
from core.database import (
    save_draft,
    get_setting,
    set_setting,
    save_asin_preset,
    get_asin_presets,
    delete_asin_preset
)
from services.amazon.extractor import fetch_products_hybrid
from services.generator.roundup import generate_roundup_article
from services.generator.review import generate_single_review_article
from services.generator.comparison import generate_comparison_article
from services.generator.gemini_client import GeminiClient, SUPPORTED_GEMINI_MODELS

SAMPLE_ASINS = """B0CX23V2ZT
B09V3HN1KC
B0BSHF7WHW"""

def render_generate_tab():
    st.subheader("🚀 Generate Affiliate Article")
    st.caption("Enter your target keyword and Amazon ASINs or URLs. The system will extract product specs and draft an SEO-optimized article.")

    # 1. API Key Quick Check & Banner
    current_key = settings.get_gemini_api_key() or st.session_state.get("gemini_api_key", "")
    if not current_key:
        st.warning("⚠️ **Gemini API Key Required**")
        col_k1, col_k2 = st.columns([3, 1])
        with col_k1:
            quick_key = st.text_input(
                "Enter Gemini API Key",
                type="password",
                placeholder="Paste AIzaSy... key here",
                key="quick_gemini_key",
                label_visibility="collapsed"
            )
        with col_k2:
            if st.button("💾 Save Key", use_container_width=True, type="primary"):
                if quick_key.strip():
                    settings.save(gemini_api_key=quick_key.strip())
                    st.session_state["gemini_api_key"] = quick_key.strip()
                    st.success("API Key saved permanently!")
                    st.rerun()
                else:
                    st.error("Please enter a key.")
        st.caption("Need a key? Get one for free at [Google AI Studio](https://aistudio.google.com/).")
        st.markdown("---")

    col1, col2 = st.columns([2, 1])

    # Load previously saved default keyword & asins
    saved_default_kw = get_setting("LAST_KEYWORD", "Best Wireless Mechanical Keyboards")
    saved_default_asins = get_setting("LAST_ASINS", SAMPLE_ASINS)

    with col1:
        keyword = st.text_input(
            "Target Primary Keyword",
            value=saved_default_kw,
            placeholder="e.g. Best Wireless Mechanical Keyboards, Ergonomic Office Chairs",
            help="The primary search term your article should rank for."
        )

        article_type = st.radio(
            "Article Format",
            options=[
                ("Top X Best Roundup", ArticleType.ROUNDUP),
                ("In-Depth Single Product Review", ArticleType.SINGLE_REVIEW),
                ("Product A vs Product B Comparison", ArticleType.COMPARISON)
            ],
            format_func=lambda x: x[0],
            horizontal=True
        )[1]

        # ASIN Presets Dropdown
        presets = get_asin_presets()
        if presets:
            preset_options = {"none": "Select a saved ASIN preset..."}
            for p in presets:
                preset_options[str(p["id"])] = f"📁 {p['name']} ({len(p['asins'].splitlines())} items)"
            
            chosen_preset_id = st.selectbox(
                "📂 Load Saved ASIN Preset",
                options=list(preset_options.keys()),
                format_func=lambda x: preset_options[x],
                index=0
            )
            if chosen_preset_id != "none":
                match = next((p for p in presets if str(p["id"]) == chosen_preset_id), None)
                if match:
                    saved_default_asins = match["asins"]
                    if match.get("keyword"):
                        keyword = match["keyword"]

        asins_input = st.text_area(
            "Amazon ASINs or Product URLs (One per line or comma-separated)",
            value=saved_default_asins,
            height=140,
            placeholder="Paste URLs or ASINs, e.g.:\nhttps://www.amazon.com/dp/B08N5WRWNW\nB09V3HN1KC\nhttps://amazon.com/gp/product/B0BSHF7WHW"
        )

        col_save_asins, col_sample = st.columns([1, 1])
        with col_save_asins:
            if st.button("💾 Save as Default ASINs", use_container_width=True):
                set_setting("LAST_ASINS", asins_input.strip())
                set_setting("LAST_KEYWORD", keyword.strip())
                st.success("✅ Saved ASINs & Keyword as default for future sessions!")

        with col_sample:
            if st.button("📋 Load Sample ASINs", use_container_width=True):
                st.session_state["asins_input_sample"] = SAMPLE_ASINS
                st.rerun()

        if "asins_input_sample" in st.session_state:
            asins_input = st.session_state.pop("asins_input_sample")

    with col2:
        st.markdown("### ⚙️ Generation Options")

        # Select Gemini Model
        curr_model = settings.GEMINI_MODEL
        model_idx = SUPPORTED_GEMINI_MODELS.index(curr_model) if curr_model in SUPPORTED_GEMINI_MODELS else 0
        selected_model = st.selectbox(
            "Gemini Model",
            options=SUPPORTED_GEMINI_MODELS,
            index=model_idx,
            help="gemini-3.8-flash is the updated flagship fast model."
        )

        tone = st.selectbox(
            "Writing Tone",
            options=[
                "Authoritative, engaging, and unbiased (Recommended)",
                "Conversational, witty, and personal",
                "Deeply technical, analytical, and spec-focused"
            ],
            index=0
        )

        affiliate_tag = st.text_input(
            "Amazon Associate Tag",
            value=settings.AMAZON_ASSOCIATE_TAG,
            help="Your affiliate tracking tag for links."
        )

        country = st.selectbox(
            "Amazon Marketplace",
            options=["com", "co.uk", "ca", "de", "fr", "in"],
            index=["com", "co.uk", "ca", "de", "fr", "in"].index(settings.AMAZON_COUNTRY) if settings.AMAZON_COUNTRY in ["com", "co.uk", "ca", "de", "fr", "in"] else 0
        )

        if st.button("💾 Save Tag & Marketplace"):
            settings.save(amazon_associate_tag=affiliate_tag.strip(), amazon_country=country)
            st.success("✅ Associate Tag & Marketplace saved!")

    st.markdown("---")
    generate_btn = st.button("✨ Run Autopilot & Generate Draft", type="primary", use_container_width=True)

    if generate_btn:
        active_key = settings.get_gemini_api_key() or st.session_state.get("gemini_api_key", "")
        if not active_key:
            st.error("⚠️ GEMINI_API_KEY is not configured! Please enter your key in the box above or in Settings.")
            return

        if not keyword.strip():
            st.error("⚠️ Please provide a target keyword.")
            return

        # Split input into lines or commas
        raw_items = [item.strip() for item in asins_input.replace(",", "\n").split("\n") if item.strip()]
        if not raw_items:
            st.error("⚠️ Please provide at least one Amazon ASIN or product URL.")
            return

        if article_type == ArticleType.COMPARISON and len(raw_items) < 2:
            st.error("⚠️ Comparison articles require at least 2 products.")
            return

        # Automatically remember last used keyword & ASINs
        set_setting("LAST_KEYWORD", keyword.strip())
        set_setting("LAST_ASINS", asins_input.strip())

        # Initialize Gemini Client with active key and selected model
        client = GeminiClient(api_key=active_key, model=selected_model)

        with st.status(f"🤖 Running Content Autopilot with {selected_model}...", expanded=True) as status:
            st.write("🔍 Extracting product data from Amazon (Hybrid Scraper / PA-API)...")
            products = fetch_products_hybrid(raw_items, affiliate_tag=affiliate_tag, country=country)

            if not products:
                status.update(label="❌ Failed to extract any products from Amazon.", state="error")
                st.error("Could not fetch product details. Please check the URLs or ASINs.")
                return

            st.write(f"✅ Successfully extracted {len(products)} product(s):")
            for p in products:
                st.write(f"- **{p.title[:60]}...** ({p.price})")

            st.write(f"✍️ Drafting high-converting SEO content with Google {selected_model} (with auto-retry)...")
            try:
                if article_type == ArticleType.ROUNDUP:
                    draft = generate_roundup_article(keyword=keyword, products=products, client=client, tone=tone)
                elif article_type == ArticleType.SINGLE_REVIEW:
                    draft = generate_single_review_article(keyword=keyword, product=products[0], client=client, tone=tone)
                else:
                    draft = generate_comparison_article(keyword=keyword, product_a=products[0], product_b=products[1], client=client)

                st.write("🛡️ Injected FTC affiliate disclosure & Amazon price disclaimers.")
                st.write("📊 Built JSON-LD Schema markup (ItemList, Product, FAQPage).")

                # Save to database
                save_draft(draft)

                status.update(label=f"🎉 Successfully generated draft: '{draft.title}'!", state="complete")
                st.success(f"Article saved! Draft ID: **{draft.id}**. Switch to the **'HITL Review Queue'** tab to review, edit, and approve.")
            except Exception as e:
                status.update(label=f"❌ Error during content generation: {e}", state="error")
                st.error(f"Generation error: {e}")
