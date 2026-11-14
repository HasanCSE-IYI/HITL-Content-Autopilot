import streamlit as st
import os
from pathlib import Path
from core.config import settings, BASE_DIR
from services.publisher.wordpress import WordPressPublisher

def render_settings_tab():
    st.subheader("⚙️ System Configuration & Credentials")
    st.caption("Configure your AI model, Amazon affiliate credentials, and WordPress integration.")

    env_path = BASE_DIR / ".env"

    with st.form("settings_form"):
        st.markdown("### 🤖 Google Gemini AI Settings")
        gemini_key = st.text_input(
            "Gemini API Key",
            value=settings.GEMINI_API_KEY,
            type="password",
            help="Get your free or paid API key from Google AI Studio (aistudio.google.com)"
        )
        gemini_model = st.selectbox(
            "Gemini Model",
            options=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
            index=0 if settings.GEMINI_MODEL == "gemini-2.5-flash" else 1
        )

        st.markdown("---")
        st.markdown("### 🛒 Amazon Associates Settings")
        associate_tag = st.text_input(
            "Amazon Associate Tracking Tag",
            value=settings.AMAZON_ASSOCIATE_TAG,
            help="E.g. myaffiliatesite-20"
        )
        country = st.selectbox(
            "Amazon Store Marketplace",
            options=["com", "co.uk", "ca", "de", "fr", "in"],
            index=0
        )

        with st.expander("Optional: Amazon PA-API 5.0 Credentials (if approved)"):
            st.info("If you do not have PA-API 5.0 keys yet, leave these blank. The built-in Smart Scraper will automatically fetch product details!")
            access_key = st.text_input("PA-API Access Key", value=settings.AMAZON_ACCESS_KEY, type="password")
            secret_key = st.text_input("PA-API Secret Key", value=settings.AMAZON_SECRET_KEY, type="password")

        st.markdown("---")
        st.markdown("### 🌐 WordPress REST API Settings")
        st.caption("Use a WordPress Application Password (Users > Profile > Application Passwords).")
        wp_url = st.text_input("WordPress Site URL", value=settings.WORDPRESS_URL, placeholder="https://yourwebsite.com")
        wp_user = st.text_input("WordPress Username", value=settings.WORDPRESS_USERNAME)
        wp_pass = st.text_input("Application Password", value=settings.WORDPRESS_APP_PASSWORD, type="password")

        submitted = st.form_submit_button("💾 Save All Settings", use_container_width=True)

        if submitted:
            # Update in-memory settings
            settings.GEMINI_API_KEY = gemini_key.strip()
            settings.GEMINI_MODEL = gemini_model
            settings.AMAZON_ASSOCIATE_TAG = associate_tag.strip()
            settings.AMAZON_COUNTRY = country
            settings.AMAZON_ACCESS_KEY = access_key.strip()
            settings.AMAZON_SECRET_KEY = secret_key.strip()
            settings.WORDPRESS_URL = wp_url.strip().rstrip("/")
            settings.WORDPRESS_USERNAME = wp_user.strip()
            settings.WORDPRESS_APP_PASSWORD = wp_pass.strip()

            # Save to .env
            env_content = (
                f"GEMINI_API_KEY={settings.GEMINI_API_KEY}\n"
                f"GEMINI_MODEL={settings.GEMINI_MODEL}\n"
                f"AMAZON_ASSOCIATE_TAG={settings.AMAZON_ASSOCIATE_TAG}\n"
                f"AMAZON_COUNTRY={settings.AMAZON_COUNTRY}\n"
                f"AMAZON_ACCESS_KEY={settings.AMAZON_ACCESS_KEY}\n"
                f"AMAZON_SECRET_KEY={settings.AMAZON_SECRET_KEY}\n"
                f"WORDPRESS_URL={settings.WORDPRESS_URL}\n"
                f"WORDPRESS_USERNAME={settings.WORDPRESS_USERNAME}\n"
                f"WORDPRESS_APP_PASSWORD={settings.WORDPRESS_APP_PASSWORD}\n"
            )
            env_path.write_text(env_content, encoding="utf-8")
            st.success("✅ Settings updated successfully!")

    st.markdown("---")
    st.markdown("### 🔍 Test WordPress Connection")
    if st.button("🔌 Test WordPress Credentials"):
        publisher = WordPressPublisher()
        result = publisher.test_connection()
        if result["success"]:
            st.success(f"✅ {result['message']}")
        else:
            st.error(f"❌ {result['message']}")
