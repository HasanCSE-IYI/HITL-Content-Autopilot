import streamlit as st
from core.config import settings
from core.database import list_drafts
from core.models import ArticleStatus
from ui.tab_generate import render_generate_tab
from ui.tab_review import render_review_tab
from ui.tab_publish import render_publish_tab
from ui.tab_settings import render_settings_tab

st.set_page_config(
    page_title="HITL Content Autopilot | Amazon Affiliate",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
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
        gap: 24px;
        margin-bottom: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        font-weight: 600;
        font-size: 1.05rem;
    }
</style>
""", unsafe_allow_html=True)

# Main Title & Description
st.markdown('<div class="main-header">🛒 HITL Content Autopilot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">AI-Powered Amazon Affiliate Content Engine with Human-in-the-Loop Review & WordPress Publishing</div>',
    unsafe_allow_html=True
)

# Metrics Ribbon
all_drafts = list_drafts()
total_count = len(all_drafts)
needs_review = len([d for d in all_drafts if d.status == ArticleStatus.NEEDS_REVIEW])
approved = len([d for d in all_drafts if d.status == ArticleStatus.APPROVED])
published = len([d for d in all_drafts if d.status == ArticleStatus.PUBLISHED])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Articles", total_count)
m2.metric("🟡 Needs Review", needs_review)
m3.metric("🟢 Approved", approved)
m4.metric("🟣 Published", published)

st.markdown("---")

# Navigation Tabs
tab_gen, tab_rev, tab_pub, tab_set = st.tabs([
    "🚀 1. Generate Article",
    f"📝 2. HITL Review Queue ({needs_review})",
    "🌐 3. WordPress Publish",
    "⚙️ 4. Settings & Credentials"
])

with tab_gen:
    render_generate_tab()

with tab_rev:
    render_review_tab()

with tab_pub:
    render_publish_tab()

with tab_set:
    render_settings_tab()

# Footer
st.markdown("---")
st.caption(
    "🛡️ Amazon Associates Compliance Guaranteed: Automatic FTC Disclosures, NoFollow/Sponsored Tags & Dynamic Price Disclaimers."
)
