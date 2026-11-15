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
from services.generator.openai_client import OpenAIClient
from services.generator.factory import get_llm_client
from services.media.image_generator import create_article_hero_image
from services.amazon.csv_importer import generate_product_facts_csv_template, parse_product_facts_csv
from services.compliance.rules import enforce_nofollow_sponsored
from services.compliance.quality_checker import audit_article_quality
from core.config import SUPPORTED_OPENAI_MODELS, DEFAULT_OPENAI_MODEL

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
    st.caption("End-to-end workflow: Keyword → Product Sourcing & Scoring → SEO Drafting → AI Taxonomy Recommendation.")

    current_stage = st.session_state.get("sw_stage", 1)

    def render_step_chip(step_num: int, label: str, active: bool, completed: bool) -> str:
        if completed:
            badge_html = '<span style="background: var(--apple-green); color: white; border-radius: 50%; width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700;">✓</span>'
            text_color = "var(--apple-ink-primary)"
        elif active:
            badge_html = f'<span style="background: var(--apple-blue); color: white; border-radius: 50%; width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; box-shadow: 0 2px 6px rgba(0,113,227,0.3);">{step_num}</span>'
            text_color = "var(--apple-blue)"
        else:
            badge_html = f'<span style="background: var(--apple-surface-secondary); color: var(--apple-ink-tertiary); border-radius: 50%; width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700;">{step_num}</span>'
            text_color = "var(--apple-ink-secondary)"

        font_weight = "700" if active else ("600" if completed else "500")
        return f'<div style="display: flex; align-items: center; gap: 8px;">{badge_html}<span style="font-weight: {font_weight}; font-size: 0.88rem; color: {text_color}; letter-spacing: -0.01em;">{label}</span></div>'

    s1_html = render_step_chip(1, "Topic & Format", active=current_stage == 1, completed=current_stage > 1)
    s2_html = render_step_chip(2, "Sourcing & 0–100 Audit", active=current_stage == 2, completed=current_stage > 2)
    s3_html = render_step_chip(3, "AI Drafting & Visuals", active=current_stage == 3, completed=current_stage > 3)
    s4_html = render_step_chip(4, "HITL Studio Approval", active=current_stage == 4, completed=False)

    arrow_sep = '<span style="color: var(--apple-ink-tertiary); font-weight: bold; user-select: none;">➔</span>'
    stepper_html = (
        '<div style="background: var(--apple-surface-secondary); border: 1px solid var(--apple-border); '
        'border-radius: 14px; padding: 12px 20px; margin-bottom: 22px; display: flex; gap: 10px; '
        f'align-items: center; justify-content: space-between; flex-wrap: wrap;">'
        f'{s1_html}{arrow_sep}{s2_html}{arrow_sep}{s3_html}{arrow_sep}{s4_html}'
        '</div>'
    )
    st.markdown(stepper_html, unsafe_allow_html=True)

    # 1. AI Provider & API Key Quick Check
    active_provider = settings.get_active_provider()
    col_prov1, _ = st.columns([1.5, 1])
    with col_prov1:
        chosen_provider = st.radio(
            "AI Engine Provider",
            options=["gemini", "openai"],
            format_func=lambda x: "✨ Google Gemini" if x == "gemini" else "🤖 OpenAI",
            index=0 if active_provider == "gemini" else 1,
            horizontal=True,
            key="sw_active_provider_radio"
        )

    if chosen_provider == "gemini":
        current_key = getattr(settings, "get_gemini_api_key", lambda: getattr(settings, "GEMINI_API_KEY", ""))() or st.session_state.get("gemini_api_key", "")
        key_label = "Gemini API Key"
        key_placeholder = "Paste AIzaSy... key here"
    else:
        current_key = getattr(settings, "get_openai_api_key", lambda: getattr(settings, "OPENAI_API_KEY", ""))() or st.session_state.get("openai_api_key", "")
        key_label = "OpenAI API Key"
        key_placeholder = "Paste sk-proj-... key here"

    if not current_key:
        st.warning(f"⚠️ **{chosen_provider.upper()} API Key Required**")
        col_k1, col_k2 = st.columns([3, 1])
        with col_k1:
            quick_key = st.text_input(
                f"Enter {key_label}",
                type="password",
                placeholder=key_placeholder,
                key=f"quick_{chosen_provider}_key_sw",
                label_visibility="collapsed"
            )
        with col_k2:
            if st.button("💾 Save Key", use_container_width=True, type="primary", key=f"save_key_{chosen_provider}_sw"):
                st.toast("API Key saved permanently!", icon="💾")
                if quick_key.strip():
                    if chosen_provider == "gemini":
                        settings.save(gemini_api_key=quick_key.strip())
                        st.session_state["gemini_api_key"] = quick_key.strip()
                    else:
                        settings.save(openai_api_key=quick_key.strip())
                        st.session_state["openai_api_key"] = quick_key.strip()
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

    # Clean empty-by-default inputs unless pushed from Keyword Research or requested sample
    persisted_kw = get_setting("LAST_KEYWORD", "")
    if persisted_kw == "Best Wireless Mechanical Keyboards":
        persisted_kw = ""
    saved_default_kw = pushed_kw or persisted_kw

    sample_asins_requested = st.session_state.pop("sw_asins_sample", None)
    persisted_asins = get_setting("LAST_ASINS", "")
    if persisted_asins.strip() == SAMPLE_ASINS.strip():
        persisted_asins = ""
    saved_default_asins = sample_asins_requested or persisted_asins

    if pushed_angle:
        st.info(f"🎯 **Applied Editorial Angle:** **{pushed_angle}** — Focus: *{pushed_focus}*")

    col1, col2 = st.columns([2, 1])

    with col1:
        keyword = st.text_input(
            "Target Primary Keyword",
            value=saved_default_kw,
            placeholder="e.g. Best Ergonomic Office Chairs, Quiet Air Purifiers",
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
                placeholder="Paste Amazon URLs or ASINs (one per line)...\nExample:\nhttps://www.amazon.com/dp/B08N5WRWNW\nB09V3HN1KC"
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
                    st.toast("Loaded sample ASINs for Keychron & Logitech!", icon="📋")
                    st.rerun()

            manual_facts_input = None

        else:
            # Manual facts entry
            sample_facts_requested = st.session_state.pop("sw_facts_sample", None)
            persisted_facts = get_setting("LAST_MANUAL_FACTS", "")
            if persisted_facts.strip() == SAMPLE_MANUAL_FACTS.strip():
                persisted_facts = ""
            saved_facts_val = sample_facts_requested or persisted_facts

            st.info("ℹ️ Enter product details directly without calling Amazon APIs or scraping. Separate multiple products with a blank line.")

            # CSV Product Importer (Section 4 & 5 Compliance)
            with st.expander("📂 Import Products from CSV Spreadsheet", expanded=False):
                st.caption("Upload a CSV file containing your product research (ASIN, Title, Price, Specs, Pros, Cons, URL).")
                csv_c1, csv_c2 = st.columns([1.5, 1])
                with csv_c2:
                    st.download_button(
                        "📥 Download CSV Template",
                        data=generate_product_facts_csv_template(),
                        file_name="amazon_product_sourcing_template.csv",
                        mime="text/csv",
                        key="sw_dl_csv_tpl",
                        use_container_width=True
                    )
                with csv_c1:
                    uploaded_csv = st.file_uploader("Choose CSV File", type=["csv"], key="sw_csv_upload")
                    if uploaded_csv:
                        csv_content = uploaded_csv.getvalue().decode("utf-8", errors="ignore")
                        parsed_prods = parse_product_facts_csv(csv_content, affiliate_tag=affiliate_tag if "affiliate_tag" in locals() else "tag-20")
                        if parsed_prods:
                            st.toast(f"✅ Imported {len(parsed_prods)} products from CSV!", icon="📦")
                            lines_acc = []
                            for p in parsed_prods:
                                lines_acc.append(
                                    f"Product: {p.title}\nPrice: {p.price}\nSpecs: {', '.join(p.features)}\nPros: {', '.join(p.pros)}\nCons: {', '.join(p.cons)}\nLink: {p.affiliate_url}"
                                )
                            saved_facts_val = "\n\n".join(lines_acc)

            manual_facts_input = st.text_area(
                "Product Facts (Title, Price, Specs, Pros/Cons, Link)",
                value=saved_facts_val,
                height=180,
                placeholder="Product: Name\nPrice: $XX\nSpecs: ...\nPros: ...\nCons: ...\nLink: https://..."
            )
            col_save_facts, col_sample_facts = st.columns([1, 1])
            with col_save_facts:
                if st.button("💾 Save as Default Facts", use_container_width=True, key="save_facts_btn_sw"):
                    set_setting("LAST_MANUAL_FACTS", manual_facts_input.strip())
                    st.success("✅ Saved Product Facts as default!")
            with col_sample_facts:
                if st.button("📋 Load Sample Product Facts", use_container_width=True, key="sample_facts_btn_sw"):
                    st.session_state["sw_facts_sample"] = SAMPLE_MANUAL_FACTS
                    st.toast("Loaded sample product facts for Keychron & Logitech!", icon="📋")
                    st.rerun()
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

        if chosen_provider == "gemini":
            selected_model = st.selectbox(
                "Gemini Model",
                options=SUPPORTED_GEMINI_MODELS,
                index=0,
                key="sw_model_select"
            )
        else:
            selected_model = "gpt-6-luna"
            st.info("🎯 **Configured Text Model:** `GPT-6 Luna (gpt-6-luna)`")

        # Image Generation Options with Image 2.5 Flare
        st.markdown("---")
        st.markdown("### 🎨 Editorial Hero Image (Image 2.5 Flare)")
        gen_hero = st.checkbox(
            "Generate Editorial Hero Graphic (Image 2.5 Flare)",
            value=True,
            help="Creates an original lifestyle / conceptual hero illustration for the article header (strictly compliant with Amazon image policies)."
        )
        hero_quality = "medium"
        if gen_hero:
            q_idx = 0 if settings.IMAGE_QUALITY == "low" else 1
            hero_quality = st.radio(
                "Image 2.5 Flare Quality Setting",
                options=["low", "medium"],
                index=q_idx,
                format_func=lambda x: "⚡ Low Quality (Faster)" if x == "low" else "✨ Medium Quality (Higher Fidelity)",
                horizontal=True,
                key="sw_hero_quality_radio"
            )

        st.markdown("---")
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
        st.session_state["sw_stage"] = 2
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

                    grade_badge = {
                        "Excellent": ("rgba(52, 199, 89, 0.1)", "var(--apple-green-dark)", "rgba(52, 199, 89, 0.3)", "🟢 Excellent"),
                        "Good": ("rgba(0, 113, 227, 0.1)", "var(--apple-blue)", "rgba(0, 113, 227, 0.3)", "🔵 Good"),
                        "Fair": ("rgba(255, 149, 0, 0.1)", "var(--apple-amber-deep)", "rgba(255, 149, 0, 0.3)", "🟡 Fair"),
                        "Needs Attention": ("rgba(239, 68, 68, 0.1)", "var(--apple-red-dark)", "rgba(239, 68, 68, 0.3)", "🔴 Needs Attention")
                    }.get(score.grade, ("var(--apple-surface-secondary)", "var(--apple-ink-secondary)", "var(--apple-border)", score.grade))

                    with st.expander(f"📦 {p.title[:60]}... — Score: {score.total_score}/100 ({score.grade})", expanded=True):
                        comp_badge_bg = 'rgba(52, 199, 89, 0.08)' if img_check['is_compliant'] else 'rgba(239, 68, 68, 0.08)'
                        comp_badge_fg = 'var(--apple-green-dark)' if img_check['is_compliant'] else 'var(--apple-red-dark)'
                        comp_badge_border = 'rgba(52, 199, 89, 0.2)' if img_check['is_compliant'] else 'rgba(239, 68, 68, 0.2)'
                        comp_badge_text = '✅ Amazon Asset Compliant' if img_check['is_compliant'] else '⚠️ Asset Flagged'

                        pill_html = (
                            '<div style="display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap;">'
                            f'<span class="apple-pill-badge" style="background: {grade_badge[0]}; color: {grade_badge[1]}; border: 1px solid {grade_badge[2]}; font-size: 0.84rem; padding: 4px 12px;">{grade_badge[3]} ({score.total_score}/100)</span>'
                            f'<span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.08); color: var(--apple-blue); border: 1px solid rgba(0, 113, 227, 0.2);">Price: {p.price or "N/A"}</span>'
                            f'<span class="apple-pill-badge" style="background: {comp_badge_bg}; color: {comp_badge_fg}; border: 1px solid {comp_badge_border};">{comp_badge_text}</span>'
                            '</div>'
                        )
                        st.markdown(pill_html, unsafe_allow_html=True)

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
                            st.caption(f"Image Rule: {img_check['reason']}")

    st.markdown("---")
    generate_btn = st.button("✨ Run Autopilot & Generate Draft", type="primary", use_container_width=True, key="sw_run_btn")

    if generate_btn:
        st.toast("Autopilot generating draft...", icon="✨")
        active_key = (
            getattr(settings, "get_gemini_api_key", lambda: getattr(settings, "GEMINI_API_KEY", ""))() or st.session_state.get("gemini_api_key", "")
            if chosen_provider == "gemini"
            else getattr(settings, "get_openai_api_key", lambda: getattr(settings, "OPENAI_API_KEY", ""))() or st.session_state.get("openai_api_key", "")
        )
        if not active_key:
            st.error(f"⚠️ {chosen_provider.upper()}_API_KEY is not configured! Please enter your key in the box above.")
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

            st.write(f"✍️ Drafting SEO article with {chosen_provider.upper()} ({selected_model})...")
            client = get_llm_client(provider=chosen_provider, model=selected_model, api_key=active_key)

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

                # Generate Hero Image with Image 2.5 Flare if enabled
                if gen_hero:
                    st.write(f"🎨 Generating editorial hero graphic with Image 2.5 Flare ({hero_quality} quality)...")
                    hero_res = create_article_hero_image(
                        keyword=keyword,
                        article_angle=pushed_angle or "",
                        quality=hero_quality
                    )
                    if hero_res.get("success") and (hero_res.get("local_path") or hero_res.get("image_url")):
                        hero_url = hero_res.get("local_path") or hero_res.get("image_url")
                        draft.featured_image = hero_url
                        draft.content_markdown = f"![{keyword} - Editorial Guide]({hero_url})\n\n" + draft.content_markdown
                        import markdown
                        html_body = markdown.markdown(draft.content_markdown, extensions=["tables", "fenced_code", "nl2br"])
                        draft.content_html = enforce_nofollow_sponsored(html_body)
                        draft.quality_scorecard = audit_article_quality(draft)
                        st.write("✅ Created and embedded Image 2.5 Flare hero graphic into Markdown, HTML, and Featured Media!")
                    elif not hero_res.get("success"):
                        st.caption(f"ℹ️ Image notice: {hero_res.get('message')}")

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
                st.session_state["sw_stage"] = 4
                st.session_state["review_selected_draft_id"] = draft.id
                
                score_val = draft.quality_scorecard.total_score if draft.quality_scorecard else 95
                
                col_res1, col_res2 = st.columns([1.6, 1])
                with col_res1:
                    st.success(f"🎉 Successfully generated draft: **'{draft.title}'** (Quality Score: **{score_val}/100**)")
                with col_res2:
                    if st.button("👉 Open in HITL Review Studio ➔", type="primary", use_container_width=True, key="sw_goto_review_btn"):
                        st.toast("Opening Review Studio...", icon="👉")
                        st.session_state["target_nav_tab"] = "HITL Review Studio"
                        st.session_state["review_selected_draft_id"] = draft.id
                        st.rerun()
            except Exception as e:
                status.update(label=f"❌ Error during generation: {e}", state="error")
                st.error(f"Generation error: {e}")
