import streamlit as st
import importlib
import core.config
import core.database

# Hot-reload guard for running Streamlit server sessions
if not hasattr(core.config.Settings, "get_openai_api_key") or not hasattr(core.config, "ENABLE_LLM_CACHE"):
    importlib.reload(core.config)
if not hasattr(core.database, "get_token_usage_summary"):
    importlib.reload(core.database)

from core.config import settings
from core.database import list_drafts, list_wordpress_sites, get_token_usage_summary, get_draft_status_counts
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

# Custom CSS for Apple Design Award-Caliber Look & Feel
st.markdown("""
<style>
    /* -------------------------------------------------------------
       🍎 Apple Human Interface Guidelines (HIG) Master Design System
       ------------------------------------------------------------- */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    :root {
        --apple-bg: #fbfbfd;
        --apple-surface: rgba(255, 255, 255, 0.86);
        --apple-surface-card: #ffffff;
        --apple-blue: #0071e3;
        --apple-blue-hover: #0077ed;
        --apple-green: #34c759;
        --apple-amber: #ff9500;
        --apple-indigo: #5856d6;
        --apple-purple: #af52de;
        --apple-ink-primary: #1d1d1f;
        --apple-ink-secondary: #6e6e73;
        --apple-border: rgba(0, 0, 0, 0.08);
        --apple-border-focus: rgba(0, 113, 227, 0.4);
        --apple-shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.04);
        --apple-shadow-md: 0 8px 24px rgba(0, 0, 0, 0.06);
        --apple-shadow-hover: 0 14px 34px -4px rgba(0, 0, 0, 0.09), 0 4px 12px -2px rgba(0, 0, 0, 0.04);
        --apple-ease: cubic-bezier(0.16, 1, 0.3, 1);
    }

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif !important;
        background-color: var(--apple-bg);
        color: var(--apple-ink-primary);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* Full width optimization with generous breathing room */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 95% !important;
        animation: appleFadeIn 0.45s var(--apple-ease);
    }

    /* Keyframe Animations */
    @keyframes appleFadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes applePulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(0.97); }
    }

    @keyframes shimmerSlide {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    /* Header styling with optical kerning */
    .brand-container {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 4px;
    }
    .brand-logo-badge {
        background: linear-gradient(135deg, #0071e3 0%, #4338ca 100%);
        color: white;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.4rem;
        box-shadow: 0 6px 16px rgba(0, 113, 227, 0.3);
    }
    .main-header {
        font-size: 2.25rem !important;
        font-weight: 800 !important;
        color: var(--apple-ink-primary) !important;
        letter-spacing: -0.03em !important;
        line-height: 1.15 !important;
    }
    .sub-header {
        font-size: 1.0rem !important;
        color: var(--apple-ink-secondary) !important;
        margin-bottom: 1.5rem !important;
        line-height: 1.5 !important;
        letter-spacing: -0.01em !important;
        max-width: 920px;
    }

    /* Apple Bento Metric Cards */
    [data-testid="stMetric"] {
        background: var(--apple-surface-card) !important;
        border: 1px solid var(--apple-border) !important;
        border-radius: 14px !important;
        padding: 16px 20px !important;
        box-shadow: var(--apple-shadow-sm) !important;
        transition: transform 0.22s var(--apple-ease), box-shadow 0.22s var(--apple-ease), border-color 0.22s var(--apple-ease) !important;
        backdrop-filter: blur(16px);
        position: relative;
        overflow: hidden;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: var(--apple-shadow-hover) !important;
        border-color: rgba(0, 113, 227, 0.28) !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: var(--apple-ink-secondary) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        margin-bottom: 4px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 800 !important;
        color: var(--apple-ink-primary) !important;
        letter-spacing: -0.03em !important;
    }

    /* Apple Segmented Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px !important;
        margin-bottom: 24px !important;
        background: rgba(0, 0, 0, 0.04) !important;
        padding: 6px !important;
        border-radius: 14px !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px !important;
        white-space: pre-wrap !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        border-radius: 10px !important;
        padding: 0 18px !important;
        border: none !important;
        color: var(--apple-ink-secondary) !important;
        background: transparent !important;
        transition: all 0.18s var(--apple-ease) !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--apple-ink-primary) !important;
        background: rgba(255, 255, 255, 0.5) !important;
    }
    .stTabs [aria-selected="true"] {
        background: #ffffff !important;
        color: var(--apple-blue) !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08) !important;
        font-weight: 700 !important;
    }

    /* Tactile Button System */
    button {
        border-radius: 980px !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        transition: all 0.2s var(--apple-ease) !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    button:active {
        transform: scale(0.975) !important;
    }
    button[kind="primary"] {
        background: linear-gradient(180deg, #0077ed 0%, #0066cc 100%) !important;
        border: 1px solid rgba(0, 113, 227, 0.8) !important;
        color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(0, 113, 227, 0.35), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(180deg, #1a85f2 0%, #0071e3 100%) !important;
        box-shadow: 0 6px 16px rgba(0, 113, 227, 0.45) !important;
        transform: translateY(-1px) !important;
    }
    button[kind="secondary"] {
        background: rgba(0, 0, 0, 0.035) !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        color: var(--apple-ink-primary) !important;
    }
    button[kind="secondary"]:hover {
        background: rgba(0, 0, 0, 0.065) !important;
        border-color: rgba(0, 0, 0, 0.16) !important;
    }

    /* Inputs & Textareas */
    input, textarea, select {
        border-radius: 10px !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        background: #ffffff !important;
        font-size: 0.94rem !important;
        transition: all 0.18s var(--apple-ease) !important;
    }
    input:focus, textarea:focus {
        border-color: var(--apple-blue) !important;
        box-shadow: 0 0 0 3.5px rgba(0, 113, 227, 0.18) !important;
        outline: none !important;
    }

    /* Expanders with Frosted Glass */
    [data-testid="stExpander"] {
        background: var(--apple-surface-card) !important;
        border: 1px solid var(--apple-border) !important;
        border-radius: 14px !important;
        box-shadow: var(--apple-shadow-sm) !important;
        overflow: hidden !important;
        transition: border-color 0.2s var(--apple-ease), box-shadow 0.2s var(--apple-ease) !important;
        margin-bottom: 14px !important;
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(0, 113, 227, 0.2) !important;
        box-shadow: var(--apple-shadow-md) !important;
    }

    /* macOS Floating Telemetry Dock */
    .bottom-status-container {
        background: rgba(255, 255, 255, 0.88) !important;
        border: 1px solid rgba(0, 0, 0, 0.09) !important;
        border-radius: 20px !important;
        padding: 18px 24px !important;
        margin-top: 36px !important;
        box-shadow: 0 16px 36px -4px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.02) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
    }

    /* Apple-style Progress Bars */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #0071e3 0%, #38bdf8 50%, #0071e3 100%) !important;
        background-size: 200% 100% !important;
        animation: shimmerSlide 2.5s infinite linear !important;
        border-radius: 9999px !important;
    }

    /* Apple Bento Metrics Grid */
    .apple-bento-card {
        background: #ffffff !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 16px !important;
        padding: 16px 20px !important;
        box-shadow: 0 3px 12px rgba(0, 0, 0, 0.03), 0 1px 3px rgba(0, 0, 0, 0.02) !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        height: 100% !important;
        position: relative !important;
    }
    .apple-bento-card:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 28px -4px rgba(0, 0, 0, 0.08), 0 4px 8px -2px rgba(0, 0, 0, 0.03) !important;
        border-color: rgba(0, 113, 227, 0.28) !important;
    }
    .bento-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .bento-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6e6e73;
    }
    .bento-icon-badge {
        width: 28px;
        height: 28px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.95rem;
    }
    .bento-value {
        font-size: 2.15rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #1d1d1f;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    .bento-subtitle {
        font-size: 0.8rem;
        color: #86868b;
        font-weight: 500;
    }

    /* macOS Status Cards */
    .apple-status-card {
        background: #ffffff !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 14px !important;
        padding: 14px 16px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        height: 100% !important;
    }
    .apple-status-card:hover {
        border-color: rgba(0, 113, 227, 0.3) !important;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06) !important;
        transform: translateY(-1px) !important;
    }
    .status-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
    }
    .status-card-label {
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #86868b;
    }
    .status-card-title {
        font-size: 0.96rem;
        font-weight: 700;
        color: #1d1d1f;
        letter-spacing: -0.01em;
        margin-bottom: 2px;
    }
    .status-card-meta {
        font-size: 0.79rem;
        color: #6e6e73;
        line-height: 1.35;
    }

    /* Apple Prose Styling for Markdown Preview */
    .apple-prose-container {
        font-family: -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", "SF Pro Text", sans-serif;
        color: #1d1d1f;
        line-height: 1.72;
        font-size: 1.02rem;
        background: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 16px;
        padding: 24px 30px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    }
    .apple-prose-container h1 {
        font-size: 1.85rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #111827;
        margin-top: 1.2rem;
        margin-bottom: 0.8rem;
        border-bottom: 1px solid rgba(0, 0, 0, 0.07);
        padding-bottom: 8px;
    }
    .apple-prose-container h2 {
        font-size: 1.45rem;
        font-weight: 700;
        letter-spacing: -0.025em;
        color: #1f2937;
        margin-top: 1.5rem;
        margin-bottom: 0.6rem;
    }
    .apple-prose-container h3 {
        font-size: 1.2rem;
        font-weight: 600;
        letter-spacing: -0.015em;
        color: #374151;
        margin-top: 1.2rem;
        margin-bottom: 0.5rem;
    }
    .apple-prose-container p {
        margin-bottom: 1.1rem;
        color: #374151;
    }
    .apple-prose-container blockquote {
        background: linear-gradient(135deg, rgba(0, 113, 227, 0.05) 0%, rgba(0, 113, 227, 0.02) 100%) !important;
        border-left: 4px solid #0071e3 !important;
        border-radius: 0 12px 12px 0 !important;
        padding: 14px 20px !important;
        margin: 20px 0 !important;
        color: #1e293b !important;
        font-style: italic;
    }
    .apple-prose-container table {
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border: 1px solid rgba(0, 0, 0, 0.09) !important;
        border-radius: 14px !important;
        overflow: hidden !important;
        width: 100% !important;
        margin: 22px 0 !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02) !important;
    }
    .apple-prose-container th {
        background: #f8fafc !important;
        padding: 12px 16px !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        color: #1e293b !important;
        border-bottom: 1px solid rgba(0, 0, 0, 0.09) !important;
        letter-spacing: 0.01em !important;
    }
    .apple-prose-container td {
        padding: 12px 16px !important;
        border-bottom: 1px solid rgba(0, 0, 0, 0.05) !important;
        font-size: 0.92rem !important;
        color: #334155 !important;
    }
    .apple-prose-container tr:last-child td {
        border-bottom: none !important;
    }
    .apple-prose-container tr:nth-child(even) {
        background-color: rgba(248, 250, 252, 0.6);
    }
    .apple-prose-container img {
        border-radius: 12px;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
        max-width: 100%;
        margin: 14px 0;
    }

    /* Apple Action Dock (Control Center Styling) */
    .apple-action-dock {
        background: rgba(255, 255, 255, 0.92) !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 18px !important;
        padding: 18px 24px !important;
        margin-top: 26px !important;
        margin-bottom: 14px !important;
        box-shadow: 0 10px 30px -4px rgba(0, 0, 0, 0.06), 0 2px 6px rgba(0, 0, 0, 0.02) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
    }

    /* Apple Elevated Card */
    .apple-card-elevated {
        background: #ffffff !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 16px !important;
        padding: 18px 22px !important;
        box-shadow: 0 3px 14px rgba(0, 0, 0, 0.03) !important;
        transition: transform 0.22s var(--apple-ease), box-shadow 0.22s var(--apple-ease) !important;
    }
    .apple-card-elevated:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 28px -4px rgba(0, 0, 0, 0.07) !important;
    }

    /* Pill Badges */
    .apple-pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .apple-beacon-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        animation: applePulse 2s infinite ease-in-out;
    }

    /* Adaptive Dark Mode Support (Apple Dark HIG) */
    @media (prefers-color-scheme: dark) {
        .apple-bento-card, .apple-status-card, .apple-action-dock, .apple-card-elevated, .apple-prose-container {
            background: #1c1c1e !important;
            border-color: rgba(255, 255, 255, 0.12) !important;
            color: #f5f5f7 !important;
        }
        .apple-prose-container th {
            background: #2c2c2e !important;
            color: #f5f5f7 !important;
            border-bottom-color: rgba(255, 255, 255, 0.12) !important;
        }
        .apple-prose-container td {
            color: #e5e7eb !important;
            border-bottom-color: rgba(255, 255, 255, 0.06) !important;
        }
        .bento-value, .status-card-title, .main-header {
            color: #f5f5f7 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Fetch system configurations
active_gemini_key = getattr(settings, "get_gemini_api_key", lambda: getattr(settings, "GEMINI_API_KEY", ""))() or st.session_state.get("gemini_api_key", "")
active_openai_key = getattr(settings, "get_openai_api_key", lambda: getattr(settings, "OPENAI_API_KEY", ""))() or st.session_state.get("openai_api_key", "")
active_provider = getattr(settings, "get_active_provider", lambda: getattr(settings, "AI_PROVIDER", "openai"))()

sites = list_wordpress_sites()
draft_counts = get_draft_status_counts()
total_count = draft_counts["total"]
needs_review = draft_counts["needs_review"]
approved = draft_counts["approved"]
scheduled = draft_counts["scheduled"]
published = draft_counts["published"]

# Top API Key Banner if neither is configured
if not active_gemini_key and not active_openai_key:
    st.warning(
        "⚠️ **AI API Key Missing:** Neither Google Gemini nor OpenAI API key is configured. "
        "You can quickly set your keys in the **System Status Bar at the bottom** or in the **Settings** tab."
    )

# Main Brand Header (Apple Studio Aesthetic)
st.markdown("""
<div class="brand-container">
    <div class="brand-logo-badge">🛒</div>
    <div>
        <div class="main-header">HITL Content Autopilot <span style="font-size: 0.95rem; color: #0071e3; font-weight: 700; vertical-align: middle; background: rgba(0, 113, 227, 0.09); padding: 3px 12px; border-radius: 9999px; border: 1px solid rgba(0, 113, 227, 0.2);">v2.0 Pro</span></div>
    </div>
</div>
<div class="sub-header">
    Enterprise Human-in-the-Loop Amazon Content Engine &nbsp;•&nbsp; Intelligent Routing: <strong>Google Gemini</strong> & <strong>OpenAI GPT-6 Luna</strong> &nbsp;•&nbsp; 48h Offline Cache Guard
</div>
""", unsafe_allow_html=True)

# Top Metrics Ribbon (Apple Bento Cards)
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f"""
    <div class="apple-bento-card">
        <div class="bento-header">
            <span class="bento-title">Total Articles</span>
            <span class="bento-icon-badge" style="background: rgba(0, 113, 227, 0.09); color: #0071e3;">📦</span>
        </div>
        <div class="bento-value">{total_count}</div>
        <div class="bento-subtitle">All drafts in database</div>
    </div>
    """, unsafe_allow_html=True)
with m2:
    st.markdown(f"""
    <div class="apple-bento-card">
        <div class="bento-header">
            <span class="bento-title">Needs Review</span>
            <span class="bento-icon-badge" style="background: rgba(255, 149, 0, 0.1); color: #ff9500;">🟡</span>
        </div>
        <div class="bento-value" style="color: #d97706;">{needs_review}</div>
        <div class="bento-subtitle">Awaiting HITL audit</div>
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div class="apple-bento-card">
        <div class="bento-header">
            <span class="bento-title">Approved</span>
            <span class="bento-icon-badge" style="background: rgba(52, 199, 89, 0.1); color: #34c759;">🟢</span>
        </div>
        <div class="bento-value" style="color: #15803d;">{approved}</div>
        <div class="bento-subtitle">Ready for publishing</div>
    </div>
    """, unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div class="apple-bento-card">
        <div class="bento-header">
            <span class="bento-title">Scheduled</span>
            <span class="bento-icon-badge" style="background: rgba(88, 86, 214, 0.1); color: #5856d6;">📅</span>
        </div>
        <div class="bento-value" style="color: #4338ca;">{scheduled}</div>
        <div class="bento-subtitle">Auto-publish queue</div>
    </div>
    """, unsafe_allow_html=True)
with m5:
    st.markdown(f"""
    <div class="apple-bento-card">
        <div class="bento-header">
            <span class="bento-title">Published</span>
            <span class="bento-icon-badge" style="background: rgba(175, 82, 222, 0.1); color: #af52de;">🟣</span>
        </div>
        <div class="bento-value" style="color: #7e22ce;">{published}</div>
        <div class="bento-subtitle">Live on WordPress</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Navigation Tabs (7 Structured Tabs)
TAB_OPTIONS = [
    "🔍 1. Keyword Intent Explorer",
    "🚀 2. Single Workflow",
    "⚡ 3. Bulk Queue (20–50 KWs)",
    f"📝 4. HITL Review Studio ({needs_review})",
    f"🌐 5. Multi-Site WordPress ({len(sites)})",
    "📈 6. Monitor & Freshness Alerts",
    "⚙️ 7. Settings, Proxies & Credentials"
]

# Programmatic Tab Navigation Controller
target_nav = st.session_state.pop("target_nav_tab", None)
if target_nav:
    matched = next((t for t in TAB_OPTIONS if target_nav.lower() in t.lower()), None)
    if matched:
        st.session_state["main_navigation_tabs"] = matched

# Defensive synchronization if dynamic badge counts change
if "main_navigation_tabs" in st.session_state and st.session_state["main_navigation_tabs"] not in TAB_OPTIONS:
    curr_val = st.session_state["main_navigation_tabs"]
    prefix = curr_val[:6]
    matched = next((t for t in TAB_OPTIONS if t.startswith(prefix)), TAB_OPTIONS[0])
    st.session_state["main_navigation_tabs"] = matched

(
    tab_kw,
    tab_single,
    tab_bulk,
    tab_rev,
    tab_sites,
    tab_mon,
    tab_set
) = st.tabs(TAB_OPTIONS, key="main_navigation_tabs")

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
# ⚙️ macOS Floating Telemetry Dock
# =========================================================================
st.markdown("---")
st.markdown("""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
    <div style="display: flex; align-items: center; gap: 8px;">
        <span class="apple-beacon-dot" style="background: #34c759;"></span>
        <span style="font-weight: 700; font-size: 0.95rem; color: #1d1d1f; letter-spacing: -0.01em;">macOS System Telemetry & Engine Dock</span>
    </div>
    <span style="font-size: 0.8rem; color: #86868b; font-weight: 500;">Live Local-First SQLite</span>
</div>
""", unsafe_allow_html=True)

b1, b2, b3, b4, b5 = st.columns([1.3, 1.3, 1.1, 1.2, 1.1])

with b1:
    if active_provider == "openai":
        is_ok = bool(active_openai_key)
        beacon_color = "#34c759" if is_ok else "#ef4444"
        st.markdown(f"""
        <div class="apple-status-card">
            <div class="status-card-header">
                <span class="apple-beacon-dot" style="background: {beacon_color};"></span>
                <span class="status-card-label">AI Engine</span>
            </div>
            <div class="status-card-title">OpenAI Active</div>
            <div class="status-card-meta">GPT-6 Luna • Image 2.5 Flare</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        is_ok = bool(active_gemini_key)
        beacon_color = "#34c759" if is_ok else "#ef4444"
        st.markdown(f"""
        <div class="apple-status-card">
            <div class="status-card-header">
                <span class="apple-beacon-dot" style="background: {beacon_color};"></span>
                <span class="status-card-label">AI Engine</span>
            </div>
            <div class="status-card-title">Gemini Active</div>
            <div class="status-card-meta">{settings.GEMINI_MODEL} • Connected</div>
        </div>
        """, unsafe_allow_html=True)

    with st.popover("🔑 Manage Provider & Keys", use_container_width=True):
        st.markdown("**Update Provider Keys**")
        gk = st.text_input("Gemini API Key", value=active_gemini_key, type="password", key="pop_gemini_key", placeholder="AIzaSy...")
        ok = st.text_input("OpenAI API Key", value=active_openai_key, type="password", key="pop_openai_key", placeholder="sk-proj-...")
        prov = st.selectbox("Default Provider", options=["gemini", "openai"], index=0 if active_provider == "gemini" else 1, key="pop_prov_select", format_func=lambda x: "✨ Google Gemini" if x == "gemini" else "🤖 OpenAI")
        if st.button("Save AI Settings", use_container_width=True, type="primary", key="pop_save_btn"):
            settings.save(
                gemini_api_key=gk.strip() if gk.strip() else None,
                openai_api_key=ok.strip() if ok.strip() else None,
                ai_provider=prov
            )
            if gk.strip():
                st.session_state["gemini_api_key"] = gk.strip()
            if ok.strip():
                st.session_state["openai_api_key"] = ok.strip()
            st.success("AI Configuration updated!")
            st.rerun()

with b2:
    if sites:
        default_site = next((s for s in sites if s.is_default), sites[0])
        st.markdown(f"""
        <div class="apple-status-card">
            <div class="status-card-header">
                <span class="apple-beacon-dot" style="background: #34c759;"></span>
                <span class="status-card-label">WordPress Sync</span>
            </div>
            <div class="status-card-title">{len(sites)} Connected Site(s)</div>
            <div class="status-card-meta">Active: <strong>{default_site.name}</strong></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="apple-status-card">
            <div class="status-card-header">
                <span class="apple-beacon-dot" style="background: #f59e0b;"></span>
                <span class="status-card-label">WordPress Sync</span>
            </div>
            <div class="status-card-title">0 Sites Connected</div>
            <div class="status-card-meta">Connect in Multi-Site tab</div>
        </div>
        """, unsafe_allow_html=True)

with b3:
    st.markdown(f"""
    <div class="apple-status-card">
        <div class="status-card-header">
            <span class="apple-beacon-dot" style="background: #0071e3;"></span>
            <span class="status-card-label">Amazon Associate</span>
        </div>
        <div class="status-card-title"><code>{settings.AMAZON_ASSOCIATE_TAG}</code></div>
        <div class="status-card-meta">Marketplace: <strong>.{settings.AMAZON_COUNTRY} Store</strong></div>
    </div>
    """, unsafe_allow_html=True)

with b4:
    tok_stats = get_token_usage_summary()
    tot_k = round(tok_stats["total_tokens"] / 1000.0, 1)
    hits = tok_stats["cache_hits"]
    saved_k = round(tok_stats["estimated_tokens_saved"] / 1000.0, 1)
    st.markdown(f"""
    <div class="apple-status-card">
        <div class="status-card-header">
            <span class="apple-beacon-dot" style="background: #0071e3;"></span>
            <span class="status-card-label">Token Telemetry</span>
        </div>
        <div class="status-card-title">{tot_k}k Tokens Used</div>
        <div class="status-card-meta">Hits: {hits} • Saved: ~{saved_k}k (${tok_stats['estimated_cost_saved_usd']})</div>
    </div>
    """, unsafe_allow_html=True)

with b5:
    st.markdown("""
    <div class="apple-status-card">
        <div class="status-card-header">
            <span class="apple-beacon-dot" style="background: #34c759;"></span>
            <span class="status-card-label">Compliance Guard</span>
        </div>
        <div class="status-card-title">SQLite WAL Guard</div>
        <div class="status-card-meta">FTC & Amazon Associates Safe</div>
    </div>
    """, unsafe_allow_html=True)

# Footer Caption
st.caption(
    "🛡️ Enterprise Policy Guard: FTC Affiliate Disclosures, rel='nofollow sponsored' validation, authorized Amazon product asset policy, and local-first SQLite persistence."
)
