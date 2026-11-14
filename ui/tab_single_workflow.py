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
    list_wordpress_sites,
    get_wordpress_site
)
from services.amazon.extractor import fetch_products_hybrid
from services.research.product_scorer import score_product, ProductScore
from services.media.image_policy import validate_product_image_policy
from services.generator.roundup import generate_roundup_article
from services.generator.review import generate_single_review_article
from services.generator.comparison import generate_comparison_article
from services.generator.category_recommender import recommend_category_and_tags
from services.generator.gemini_client import GeminiClient, SUPPORTED_GEMINI_MODELS

SAMPLE_ASINS = """B0CX23V2ZT
B09V3HN1KC
B0BSHF7WHW"""

SAMPLE_MANUAL_FACTS = """Product: Keychron K2 Pro Wireless Mechanical Keyboard
Price: $89.99
Specs: 75% Layout, QMK/VIA Programmable, Hot-Swappable, Bluetooth 5.1 & Wired, RGB Backlight
Pros: Superb typing feel, durable PBT keycaps, easy multi-device switching
Cons: Higher front height requires wrist rest
Link: https://www.amazon.com/dp/B08N5WRWNW

Product: Logitech MX Mechanical Mini
Price: $149.99
Specs: Low-Profile Tactile Switches, Smart Illumination, Multi-OS, USB-C Fast Charging
Pros: Sleek modern design, quiet switches, outstanding battery life
Cons: Premium price tag, non-swappable switches
Link: https://www.amazon.com/dp/B09V3HN1KC"""

def render_single_workflow_tab():
    st.subheader("🚀 Single Keyword Research & Generation Workflow")
    st.caption("End-to-end workflow: Keyword $\rightarrow$ Product Sourcing & Scoring $\rightarrow$ SEO Drafting $\rightarrow$ AI Taxonomy Recommendation.")

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
                key="quick_gemini_key_sw",
                label_visibility="collapsed"
            )
        with col_k2:
            if st.button("💾 Save Key", use_container_width=True, type="primary", key="save_key_sw"):
                if quick_key.strip():
                    settings.save(gemini_api_key=quick_key.strip())
                    st.session_state["gemini_api_key"] = quick_key.strip()
                    st.success("API Key saved permanently!")
                    st.rerun()
                else:
                    st.error("Please enter a key.")
        st.markdown("---")

    sites = list_wordpress_sites()
    
    # Check if keyword pushed from Keyword Research Explorer
    pushed_kw = st.session_state.get("workflow_seed_keyword")
    pushed_angle = st.session_state.get("workflow_editorial_angle")
    pushed_focus = st.session_state.get("workflow_editorial_focus")
    pushed_format = st.session_state.get("workflow_article_type")

    saved_default_kw = pushed_kw or get_setting("LAST_KEYWORD", "Best Wireless Mechanical Keyboards")
    saved_default_asins = get_setting("LAST_ASINS", SAMPLE_ASINS)

    if pushed_angle:
        st.info(f"🎯 **Applied Editorial Angle:** **{pushed_angle}** — Focus: *{pushed_focus}*")

    col1, col2 = st.columns([2, 1])

    with col1:
        keyword = st.text_input(
            "Target Primary Keyword",
            value=saved_default_kw,
            placeholder="e.g. Best Wireless Mechanical Keyboards",
            help="The primary search term you want this article to rank for."
        )

        format_index = 0
        if pushed_format == "single_review":
            format_index = 1
        elif pushed_format == "comparison":
            format_index = 2

        article_type = st.radio(
            "Article Format",
            options=[
                ("Top X Best Roundup", ArticleType.ROUNDUP),
                ("In-Depth Single Product Review", ArticleType.SINGLE_REVIEW),
                ("Product A vs Product B Comparison", ArticleType.COMPARISON)
            ],
            index=format_index,
            format_func=lambda x: x[0],
            horizontal=True
        )[1]

        # Sourcing Mode Selector
        sourcing_mode = st.radio(
            "Product Sourcing Method",
            options=[
                "🛒 Automated Amazon Sourcing (URLs / ASINs via Safe Scraper / PA-API)",
                "📝 Manual Product Facts (Zero API / Zero Network Input)"
            ],
            index=0
        )

        if "Automated" in sourcing_mode:
            # Presets Loader
            presets = get_asin_presets()
            if presets:
                preset_options = {"none": "Select a saved ASIN preset..."}
                for p in presets:
                    preset_options[str(p["id"])] = f"📁 {p['name']} ({len(p['asins'].splitlines())} items)"
                
                chosen_preset_id = st.selectbox(
                    "📂 Load Saved ASIN Preset",
                    options=list(preset_options.keys()),
                    format_func=lambda x: preset_options[x],
                    index=0,
                    key="sw_preset_select"
                )
                if chosen_preset_id != "none":
                    match = next((p for p in presets if str(p["id"]) == chosen_preset_id), None)
                    if match:
                        saved_default_asins = match["asins"]
                        if match.get("keyword"):
                            keyword = match["keyword"]

            asins_input = st.text_area(
                "Amazon ASINs or Product URLs (One per line)",
                value=saved_default_asins,
                height=130,
                placeholder="https://www.amazon.com/dp/B08N5WRWNW\nB09V3HN1KC..."
            )
            col_save_asins, col_sample = st.columns([1, 1])
            with col_save_asins:
                if st.button("💾 Save as Default ASINs", use_container_width=True, key="save_asins_btn_sw"):
                    set_setting("LAST_ASINS", asins_input.strip())
                    set_setting("LAST_KEYWORD", keyword.strip())
                    st.success("✅ Saved ASINs & Keyword as default!")
            with col_sample:
                if st.button("📋 Load Sample ASINs", use_container_width=True, key="sample_asins_btn_sw"):
                    st.session_state["sw_asins_sample"] = SAMPLE_ASINS
                    st.rerun()

            if "sw_asins_sample" in st.session_state:
                asins_input = st.session_state.pop("sw_asins_sample")
            manual_facts_input = None

        else:
            # Manual facts entry
            st.info("ℹ️ Enter product details directly without calling Amazon APIs or scraping. Separate multiple products with a blank line.")
            manual_facts_input = st.text_area(
                "Product Facts (Title, Price, Specs, Pros/Cons, Link)",
                value=SAMPLE_MANUAL_FACTS,
                height=180,
                placeholder="Product: Name\nPrice: $XX\nSpecs: ...\nPros: ...\nCons: ...\nLink: https://..."
            )
            asins_input = ""

        # Score & Preview button before generation
        col_preview, _ = st.columns([1.5, 1])
        with col_preview:
            preview_btn = st.button("🔍 Preview & Score Products (0–100 Audit)", use_container_width=True)

    with col2:
        st.markdown("### 🌐 Target WordPress Site")
        chosen_site_id = None
        target_site_obj = None

        if sites:
            site_opts = {s.id: f"{s.name} ({s.url})" for s in sites}
            default_idx = next((i for i, s in enumerate(sites) if s.is_default), 0)
            chosen_site_id = st.selectbox(
                "Target WordPress Site",
                options=list(site_opts.keys()),
                format_func=lambda x: site_opts[x],
                index=default_idx,
                key="sw_target_site"
            )
            target_site_obj = get_wordpress_site(chosen_site_id)
            if target_site_obj:
                st.caption(f"Synced Taxonomies: {len(target_site_obj.categories)} Categories, {len(target_site_obj.tags)} Tags")
        else:
            st.caption("No WordPress sites connected. Connect one in 'Multi-Site WordPress' tab.")

        st.markdown("---")
        st.markdown("### ⚙️ Model & Writing Options")

        curr_model = settings.GEMINI_MODEL
        model_idx = SUPPORTED_GEMINI_MODELS.index(curr_model) if curr_model in SUPPORTED_GEMINI_MODELS else 0
        selected_model = st.selectbox(
            "Gemini Model",
            options=SUPPORTED_GEMINI_MODELS,
            index=model_idx,
            key="sw_model_select"
        )

        tone = st.selectbox(
            "Writing Tone",
            options=[
                "Authoritative, engaging, and unbiased (Recommended)",
                "Conversational, witty, and personal",
                "Deeply technical, analytical, and spec-focused"
            ],
            index=0,
            key="sw_tone_select"
        )

        affiliate_tag = st.text_input(
            "Associate Tag",
            value=settings.AMAZON_ASSOCIATE_TAG,
            key="sw_tag_input"
        )

        country = st.selectbox(
            "Amazon Marketplace",
            options=["com", "co.uk", "ca", "de", "fr", "in"],
            index=["com", "co.uk", "ca", "de", "fr", "in"].index(settings.AMAZON_COUNTRY) if settings.AMAZON_COUNTRY in ["com", "co.uk", "ca", "de", "fr", "in"] else 0,
            key="sw_country_select"
        )

    # Preview & Score execution
    if preview_btn:
        with st.spinner("Sourcing and scoring candidate products..."):
            if manual_facts_input:
                preview_prods = fetch_products_hybrid([], affiliate_tag=affiliate_tag, country=country, manual_facts_text=manual_facts_input)
            else:
                raw_items = [item.strip() for item in asins_input.replace(",", "\n").splitlines() if item.strip()]
                preview_prods = fetch_products_hybrid(raw_items, affiliate_tag=affiliate_tag, country=country)

            if not preview_prods:
                st.error("No valid products could be sourced. Please verify your ASINs or manual product facts.")
            else:
                st.markdown("#### 📊 Product Transparency & Scoring Audit (0–100)")
                for p in preview_prods:
                    score: ProductScore = score_product(p, keyword=keyword)
                    img_check = validate_product_image_policy(p.main_image or "")

                    score_color = {
                        "Excellent": "green",
                        "Good": "blue",
                        "Fair": "orange",
                        "Needs Attention": "red"
                    }.get(score.grade, "gray")

                    with st.expander(f"📦 {p.title[:65]}... — :{score_color}[**Score: {score.total_score}/100 ({score.grade})**]", expanded=True):
                        sc_col1, sc_col2 = st.columns([2, 1])
                        with sc_col1:
                            st.markdown(f"**ASIN:** `{p.asin}` | **Price:** `{p.price}` | **Brand:** `{p.brand or 'N/A'}`")
                            st.markdown(f"**Verdict:** {score.verdict}")
                            if score.missing_data:
                                st.warning("**Missing Data Gaps:**\n- " + "\n- ".join(score.missing_data))
                            if score.strengths:
                                st.success("**Strengths Identified:**\n- " + "\n- ".join(score.strengths))
                        with sc_col2:
                            st.markdown("**Points Breakdown:**")
                            for k, v in score.breakdown.items():
                                st.caption(f"- {k}: **{v} pts**")
                            st.markdown(f"**Image Compliance:** `{'✅ Authorized' if img_check['is_compliant'] else '⚠️ Flagged'}`")
                            st.caption(img_check['reason'])

    st.markdown("---")
    generate_btn = st.button("✨ Run Autopilot & Generate Draft", type="primary", use_container_width=True, key="sw_run_btn")

    if generate_btn:
        active_key = settings.get_gemini_api_key() or st.session_state.get("gemini_api_key", "")
        if not active_key:
            st.error("⚠️ GEMINI_API_KEY is not configured! Please enter your key in the box above.")
            return

        if not keyword.strip():
            st.error("⚠️ Please provide a target keyword.")
            return

        # Sourcing
        with st.status("🤖 Running Content Autopilot Workflow...", expanded=True) as status:
            st.write("🔍 Sourcing product details (Safe Scraper / PA-API / Manual Facts)...")
            if manual_facts_input:
                products = fetch_products_hybrid([], affiliate_tag=affiliate_tag, country=country, manual_facts_text=manual_facts_input)
            else:
                raw_items = [item.strip() for item in asins_input.replace(",", "\n").splitlines() if item.strip()]
                if not raw_items:
                    status.update(label="❌ Please provide at least one Amazon URL or ASIN.", state="error")
                    st.error("No ASINs provided.")
                    return
                products = fetch_products_hybrid(raw_items, affiliate_tag=affiliate_tag, country=country)

            if not products:
                status.update(label="❌ Failed to extract product details.", state="error")
                st.error("Could not extract products.")
                return

            st.write(f"✅ Sourced {len(products)} product(s):")
            for p in products:
                st.write(f"- **{p.title[:60]}...** ({p.price}) [{p.provenance}]")

            st.write(f"✍️ Drafting SEO article with Google {selected_model}...")
            client = GeminiClient(api_key=active_key, model=selected_model)

            try:
                # Include editorial angle in tone if set
                generation_tone = tone
                if pushed_angle and pushed_focus:
                    generation_tone += f". Editorial Focus: {pushed_angle} ({pushed_focus})"

                if article_type == ArticleType.ROUNDUP:
                    draft = generate_roundup_article(keyword=keyword, products=products, client=client, tone=generation_tone)
                elif article_type == ArticleType.SINGLE_REVIEW:
                    draft = generate_single_review_article(keyword=keyword, product=products[0], client=client, tone=generation_tone)
                else:
                    p1 = products[0]
                    p2 = products[1] if len(products) > 1 else products[0]
                    draft = generate_comparison_article(keyword=keyword, product_a=p1, product_b=p2, client=client)

                st.write("🛡️ Injected FTC disclosures, price disclaimer & JSON-LD schema.")
                
                # Multi-site taxonomy matching
                if chosen_site_id:
                    draft.wp_site_id = chosen_site_id
                    site_data = get_wordpress_site(chosen_site_id)
                    if site_data and site_data.categories:
                        st.write("🏷️ Analyzing target site categories with AI...")
                        cat_rec = recommend_category_and_tags(
                            keyword=keyword,
                            title=draft.title,
                            categories=site_data.categories,
                            tags=site_data.tags,
                            client=client
                        )
                        draft.suggested_category_id = cat_rec.get("category_id")
                        draft.suggested_category_name = cat_rec.get("category_name")
                        draft.selected_category_id = cat_rec.get("category_id")
                        draft.selected_tags = cat_rec.get("tag_ids", [])
                        st.write(f"💡 Recommended Category: **{cat_rec.get('category_name')}** (Confidence: {int(cat_rec.get('confidence', 0)*100)}%)")

                # Save to database
                save_draft(draft)
                set_setting("LAST_KEYWORD", keyword.strip())
                if asins_input.strip():
                    set_setting("LAST_ASINS", asins_input.strip())

                status.update(label=f"🎉 Successfully generated draft: '{draft.title}'!", state="complete")
                
                score_val = draft.quality_scorecard.total_score if draft.quality_scorecard else 95
                st.success(f"Draft saved! (Quality Score: **{score_val}/100**). Go to the **'HITL Review Studio'** to review, adjust categories, and publish/schedule.")
            except Exception as e:
                status.update(label=f"❌ Error during generation: {e}", state="error")
                st.error(f"Generation error: {e}")
