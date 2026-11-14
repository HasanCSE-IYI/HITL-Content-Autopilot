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
    initial_sidebar_state="expanded"
)

# Custom CSS for polished SaaS look
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a202c;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4a5568;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 16px;
        margin-bottom: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 52px;
        white-space: pre-wrap;
        font-weight: 600;
        font-size: 0.98rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Quick Status & Configuration
with st.sidebar:
    st.markdown("### ⚙️ Quick System Status")
    active_key = settings.get_gemini_api_key() or st.session_state.get("gemini_api_key", "")
    
    if active_key:
        st.success(f"🟢 **Gemini AI:** Connected\n\nModel: `{settings.GEMINI_MODEL}`")
    else:
        st.error("🔴 **Gemini AI:** Key Missing")
        sb_key = st.text_input("Enter Gemini Key", type="password", key="sidebar_gemini_key", placeholder="AIzaSy...")
        if st.button("Save Key in Sidebar", use_container_width=True):
            if sb_key.strip():
                settings.save(gemini_api_key=sb_key.strip())
                st.session_state["gemini_api_key"] = sb_key.strip()
                st.success("Saved!")
                st.rerun()

    st.markdown("---")
    sites = list_wordpress_sites()
    st.markdown(f"**Connected Sites:** `{len(sites)}`")
    if sites:
        default_site = next((s for s in sites if s.is_default), sites[0])
        st.caption(f"Default: **{default_site.name}**\n({len(default_site.categories)} cats, {len(default_site.tags)} tags)")
    else:
        st.caption("No sites connected yet.")

    st.markdown("---")
    st.markdown(f"**Associate Tag:** `{settings.AMAZON_ASSOCIATE_TAG}`")
    st.markdown(f"**Marketplace:** `amazon.{settings.AMAZON_COUNTRY}`")

# Main Title & Description
st.markdown('<div class="main-header">🛒 HITL Content Autopilot v2</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Local-First Amazon Affiliate Content Engine with Keyword Intent Analysis, Safe Anti-Block Sourcing, Multi-Site WordPress Sync, Bulk Queue, and Quality Audits</div>',
    unsafe_allow_html=True
)

# Metrics Ribbon
all_drafts = list_drafts()
total_count = len(all_drafts)
needs_review = len([d for d in all_drafts if d.status == ArticleStatus.NEEDS_REVIEW])
approved = len([d for d in all_drafts if d.status == ArticleStatus.APPROVED])
scheduled = len([d for d in all_drafts if d.status == ArticleStatus.SCHEDULED])
published = len([d for d in all_drafts if d.status == ArticleStatus.PUBLISHED])

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

# Footer
st.markdown("---")
st.caption(
    "🛡️ Enterprise Policy Guard: FTC Disclosures, rel='nofollow sponsored' link tagging, authorized Amazon product asset policy & local-first SQLite persistence."
)
