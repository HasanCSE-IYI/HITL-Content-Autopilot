import streamlit as st
from core.config import settings
from core.database import list_drafts, list_wordpress_sites
from core.models import ArticleStatus
from services.generator.gemini_client import SUPPORTED_GEMINI_MODELS
from ui.tab_keyword_research import render_keyword_research_tab
from ui.tab_single_workflow import render_single_workflow_tab
from ui.tab_bulk_queue import render_bulk_queue_tab
from ui.tab_review import render_review_tab
from ui.tab_multisite import render_multisite_tab
from ui.tab_monitor import render_monitor_tab
from ui.tab_settings import render_settings_tab

st.set_page_config(
    page_title="HITL Content Autopilot | Amazon Affiliate Enterprise",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for polished SaaS look & status bottom bar
st.markdown("""
<style>
    /* Full width optimization */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 96% !important;
    }
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1a202c;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.02rem;
        color: #4a5568;
        margin-bottom: 1.4rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 14px;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        font-weight: 600;
        font-size: 0.96rem;
    }
    /* Status bottom dock styling */
    .bottom-status-container {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 30px;
    }
    .status-badge-title {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Fetch system configurations
active_key = settings.get_gemini_api_key() or st.session_state.get("gemini_api_key", "")
sites = list_wordpress_sites()
all_drafts = list_drafts()
total_count = len(all_drafts)
needs_review = len([d for d in all_drafts if d.status == ArticleStatus.NEEDS_REVIEW])
approved = len([d for d in all_drafts if d.status == ArticleStatus.APPROVED])
scheduled = len([d for d in all_drafts if d.status == ArticleStatus.SCHEDULED])
published = len([d for d in all_drafts if d.status == ArticleStatus.PUBLISHED])

# Top API Key Banner if unconfigured
if not active_key:
    st.warning(
        "⚠️ **Gemini API Key Missing:** AI generation features require an active key. "
        "You can quickly set it in the **System Status Bar at the bottom** or in the **Settings** tab."
    )

# Main Title & Subtitle Header
st.markdown('<div class="main-header">🛒 HITL Content Autopilot v2</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Local-First Amazon Affiliate Content Engine with Keyword Intent Analysis, Safe Anti-Block Sourcing, Multi-Site WordPress Sync, Bulk Queue, and Quality Audits</div>',
    unsafe_allow_html=True
)

# Top Metrics Ribbon
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Articles", total_count)
m2.metric("🟡 Needs Review", needs_review)
m3.metric("🟢 Approved", approved)
m4.metric("📅 Scheduled", scheduled)
m5.metric("🟣 Published", published)

st.markdown("---")

# Navigation Tabs (7 Structured Tabs)
(
    tab_kw,
    tab_single,
    tab_bulk,
    tab_rev,
    tab_sites,
    tab_mon,
    tab_set
) = st.tabs([
    "🔍 1. Keyword Intent Explorer",
    "🚀 2. Single Workflow",
    "⚡ 3. Bulk Queue (20–50 KWs)",
    f"📝 4. HITL Review Studio ({needs_review})",
    f"🌐 5. Multi-Site WordPress ({len(sites)})",
    "📈 6. Monitor & Freshness Alerts",
    "⚙️ 7. Settings, Proxies & Credentials"
])

with tab_kw:
    render_keyword_research_tab()

with tab_single:
    render_single_workflow_tab()

with tab_bulk:
    render_bulk_queue_tab()

with tab_rev:
    render_review_tab()

with tab_sites:
    render_multisite_tab()

with tab_mon:
    render_monitor_tab()

with tab_set:
    render_settings_tab()

# =========================================================================
# ⚙️ Bottom System Status & Telemetry Bar (Best Practice Layout)
# =========================================================================
st.markdown("---")
st.markdown("##### ⚙️ Quick System Status & Telemetry")

b1, b2, b3, b4 = st.columns([1.5, 1.5, 1.3, 1.7])

with b1:
    if active_key:
        st.success(f"🟢 **Gemini AI:** Connected\n\nModel: `{settings.GEMINI_MODEL}`", icon="🤖")
        with st.popover("⚙️ Update Key", use_container_width=True):
            upd_key = st.text_input("New Gemini API Key", type="password", key="bottom_gemini_key_upd", placeholder="AIzaSy...")
            if st.button("Update Key", use_container_width=True, key="btn_upd_key_bottom", type="primary"):
                if upd_key.strip():
                    settings.save(gemini_api_key=upd_key.strip())
                    st.session_state["gemini_api_key"] = upd_key.strip()
                    st.success("API key updated!")
                    st.rerun()
    else:
        st.error("🔴 **Gemini AI:** Key Missing", icon="⚠️")
        with st.popover("🔑 Set Gemini API Key", use_container_width=True):
            quick_key_bottom = st.text_input("Enter Gemini API Key", type="password", key="bottom_gemini_key", placeholder="AIzaSy...")
            if st.button("Save Key Permanently", use_container_width=True, key="btn_save_key_bottom", type="primary"):
                if quick_key_bottom.strip():
                    settings.save(gemini_api_key=quick_key_bottom.strip())
                    st.session_state["gemini_api_key"] = quick_key_bottom.strip()
                    st.success("API key saved!")
                    st.rerun()

with b2:
    if sites:
        default_site = next((s for s in sites if s.is_default), sites[0])
        st.info(f"🌐 **WP Network:** `{len(sites)}` Sites\n\nActive: **{default_site.name}**", icon="🌐")
    else:
        st.warning("🌐 **WP Network:** No Sites Connected\n\nAdd site in 'Multi-Site' tab", icon="🌐")

with b3:
    st.info(f"🏷️ **Associate Tag:**\n\n`{settings.AMAZON_ASSOCIATE_TAG}` (`.{settings.AMAZON_COUNTRY}`)", icon="🛒")

with b4:
    st.info("🛡️ **Storage & Compliance Guard:**\n\nLocal SQLite • 24h Cache • FTC Verified", icon="🔒")

# Footer Caption
st.caption(
    "🛡️ Enterprise Policy Guard: FTC Affiliate Disclosures, rel='nofollow sponsored' validation, authorized Amazon product asset policy, and local-first SQLite persistence."
)
