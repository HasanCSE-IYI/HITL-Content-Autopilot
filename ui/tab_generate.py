import streamlit as st
from typing import List
from core.models import ArticleType
from core.config import settings
from core.database import save_draft
from services.amazon.extractor import fetch_products_hybrid
from services.generator.roundup import generate_roundup_article
from services.generator.review import generate_single_review_article
from services.generator.comparison import generate_comparison_article
from services.generator.gemini_client import GeminiClient

SAMPLE_ASINS = """B0CX23V2ZT
B09V3HN1KC
B0BSHF7WHW"""

def render_generate_tab():
    st.subheader("🚀 Generate Affiliate Article")
    st.caption("Enter your target keyword and Amazon ASINs or URLs. The system will extract product specs and draft an SEO-optimized article.")

    col1, col2 = st.columns([2, 1])

    with col1:
        keyword = st.text_input(
            "Target Primary Keyword",
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

        asins_input = st.text_area(
            "Amazon ASINs or Product URLs (One per line or comma-separated)",
            height=140,
            placeholder="Paste URLs or ASINs, e.g.:\nhttps://www.amazon.com/dp/B08N5WRWNW\nB09V3HN1KC\nhttps://amazon.com/gp/product/B0BSHF7WHW"
        )

        col_sample, col_clear = st.columns([1, 1])
        with col_sample:
            if st.button("📋 Load Sample ASINs", use_container_width=True):
                st.session_state["asins_input_sample"] = SAMPLE_ASINS
                st.rerun()

        if "asins_input_sample" in st.session_state:
            asins_input = st.session_state.pop("asins_input_sample")

    with col2:
        st.markdown("### ⚙️ Generation Options")
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
            index=0
        )

    st.markdown("---")
    generate_btn = st.button("✨ Run Autopilot & Generate Draft", type="primary", use_container_width=True)

    if generate_btn:
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

        # Verify Gemini key
        client = GeminiClient()
        if not client.is_configured():
            st.warning("⚠️ GEMINI_API_KEY is not configured! Please set it in the 'Settings' tab.")
            return

        with st.status("🤖 Running Content Autopilot...", expanded=True) as status:
            st.write("🔍 Extracting product data from Amazon (Hybrid Scraper / PA-API)...")
            products = fetch_products_hybrid(raw_items, affiliate_tag=affiliate_tag, country=country)

            if not products:
                status.update(label="❌ Failed to extract any products from Amazon.", state="error")
                st.error("Could not fetch product details. Please check the URLs or ASINs.")
                return

            st.write(f"✅ Successfully extracted {len(products)} product(s):")
            for p in products:
                st.write(f"- **{p.title[:60]}...** ({p.price})")

            st.write("✍️ Drafting high-converting SEO content with Google Gemini...")
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
