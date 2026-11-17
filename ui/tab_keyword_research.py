import streamlit as st
from services.research.keyword_analyst import analyze_keyword, KeywordAnalysisResult
from services.generator.factory import get_llm_client
from core.config import settings

def render_keyword_research_tab():
    active_provider = getattr(settings, "get_active_provider", lambda: getattr(settings, "AI_PROVIDER", "openai"))()
    active_model_name = "GPT-6 Luna" if active_provider == "openai" else "Gemini"

    st.subheader("🔍 Keyword Intent & Editorial Strategy Explorer")
    st.caption(f"Expand seed keywords into search intent, People Also Ask (PAA) queries, and 3 distinct editorial angles powered by **{active_model_name}**. Grounded in truthful search dynamics—no fabricated volume numbers.")

    with st.form("kw_search_form", border=False):
        col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
        with col1:
            keyword_input = st.text_input(
                "Target Seed Keyword",
                value=st.session_state.get("last_researched_kw", ""),
                placeholder="e.g. best ergonomic office chair under 300, quiet air purifier for bedroom",
                help="Enter a product niche or search query to analyze consumer intent and editorial hooks."
            )
        with col2:
            analyze_btn = st.form_submit_button("🚀 Analyze Keyword", type="primary", use_container_width=True)

    if (analyze_btn or st.session_state.pop("trigger_kw_analysis", False)) and keyword_input.strip():
        st.session_state["last_researched_kw"] = keyword_input.strip()
        with st.spinner(f"Analyzing search intent, queries, and editorial angles with {active_model_name}..."):
            client = get_llm_client()
            result: KeywordAnalysisResult = analyze_keyword(keyword_input.strip(), client=client)
            st.session_state["kw_analysis_result"] = result

    result: KeywordAnalysisResult = st.session_state.get("kw_analysis_result")
    if result and result.keyword:
        st.divider()
        col_res_h1, col_res_h2 = st.columns([4, 1], vertical_alignment="center")
        with col_res_h1:
            st.markdown(f"#### 🔍 Editorial Intent Blueprint: **{result.keyword}**")
        with col_res_h2:
            if st.button("✕ Clear", use_container_width=True, help="Clear current keyword analysis"):
                st.session_state.pop("kw_analysis_result", None)
                st.session_state.pop("last_researched_kw", None)
                st.toast("Keyword analysis cleared.", icon="✕")
                st.rerun()

        # Top Intent & Format Summary (Apple Capsule Pills)
        intent_bg, intent_fg, intent_border = {
            "Commercial Investigation": ("rgba(0, 113, 227, 0.09)", "var(--apple-blue)", "rgba(0, 113, 227, 0.25)"),
            "Transactional": ("rgba(52, 199, 89, 0.09)", "var(--apple-green-dark)", "rgba(52, 199, 89, 0.25)"),
            "Informational": ("rgba(255, 149, 0, 0.09)", "var(--apple-amber-deep)", "rgba(255, 149, 0, 0.25)")
        }.get(result.search_intent, ("rgba(100, 116, 139, 0.09)", "var(--apple-slate-dark)", "rgba(100, 116, 139, 0.2)"))

        st.markdown(f"""
        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 14px;">
            <span class="apple-pill-badge" style="background: {intent_bg}; color: {intent_fg}; border: 1px solid {intent_border}; font-size: 0.84rem; padding: 5px 14px;">
                🎯 Search Intent: <strong>{result.search_intent}</strong>
            </span>
            <span class="apple-pill-badge" style="background: rgba(88, 86, 214, 0.09); color: var(--apple-indigo-dark); border: 1px solid rgba(88, 86, 214, 0.25); font-size: 0.84rem; padding: 5px 14px;">
                📄 Format: <strong>{result.recommended_article_type.title()}</strong>
            </span>
            <span style="color: var(--apple-ink-secondary); font-size: 0.88rem; margin-left: 4px;">{result.intent_explanation}</span>
        </div>
        """, unsafe_allow_html=True)

        # PAA & Related Queries in 2 columns
        st.markdown("---")
        q_col, r_col = st.columns(2, vertical_alignment="top")

        with q_col:
            st.markdown("##### ❓ High-Intent Questions (People Also Ask)")
            if result.user_questions:
                for idx, q in enumerate(result.user_questions, 1):
                    with st.expander(f"Q{idx}: {q.question}", expanded=(idx == 1)):
                        st.markdown(f"**Key Editorial Focus:** {q.focal_answer_point}")
            else:
                st.info("No specific user questions generated.")

        with r_col:
            st.markdown("##### 🔗 High-Relevance Related Queries")
            if result.related_queries:
                for qry in result.related_queries:
                    st.markdown(f"- `{qry}`")
                
                # Bulk queue quick-export helper with direct 1-click handoff
                if st.button("➕ Push to Bulk Queue & Open Tab ➔", use_container_width=True, type="secondary"):
                    existing_bulk = st.session_state.get("bulk_keywords_input", "")
                    combined = (existing_bulk.strip() + "\n" + "\n".join(result.related_queries)).strip()
                    st.session_state["bulk_keywords_input"] = combined
                    st.toast(f"Added {len(result.related_queries)} queries! Opening Bulk Queue...", icon="📋")
                    st.session_state["target_nav_tab"] = "Bulk Queue"
                    st.rerun()
            else:
                st.info("No related queries available.")

        # 3 Editorial Angles (Apple Bento Cards)
        st.markdown("---")
        st.markdown("##### 🎯 3 Differentiated Editorial Angles")
        st.caption("Choose an editorial perspective tailored to your audience to avoid generic affiliate copy.")

        cols = st.columns(3, vertical_alignment="top")
        angle_themes = [
            ("💎", "var(--apple-blue)", "rgba(0, 113, 227, 0.08)", "rgba(0, 113, 227, 0.25)"),
            ("⚖️", "var(--apple-purple)", "rgba(175, 82, 222, 0.08)", "rgba(175, 82, 222, 0.25)"),
            ("⚡", "var(--apple-green)", "rgba(52, 199, 89, 0.08)", "rgba(52, 199, 89, 0.25)")
        ]
        for idx, angle in enumerate(result.editorial_angles):
            theme = angle_themes[idx % len(angle_themes)]
            with cols[idx % 3]:
                with st.container(border=True):
                    card_html = (
                        f'<div style="border-left: 3px solid {theme[1]}; padding-left: 10px; margin-bottom: 8px;">'
                        f'<div style="font-size: 1.15rem; font-weight: 700; color: var(--apple-ink-primary);">{theme[0]} {angle.name}</div>'
                        '</div>'
                        '<div style="margin-bottom: 8px;">'
                        f'<span class="apple-pill-badge" style="background: {theme[2]}; color: {theme[1]}; border: 1px solid {theme[3]};">'
                        f'Audience: {angle.target_audience}'
                        '</span>'
                        '</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                    st.markdown(f"**Core Editorial Focus:**\n*{angle.editorial_focus}*")
                    if st.button(f"🚀 Dispatch to Single Workflow", key=f"btn_angle_{idx}", use_container_width=True, type="secondary"):
                        st.session_state["workflow_seed_keyword"] = result.keyword
                        st.session_state["workflow_editorial_angle"] = angle.name
                        st.session_state["workflow_editorial_focus"] = angle.editorial_focus
                        st.session_state["workflow_article_type"] = result.recommended_article_type
                        st.session_state["sw_stage"] = 1
                        st.session_state["target_nav_tab"] = "Single Workflow"
                        st.toast(f"Angle '{angle.name}' applied! Switched to Single Workflow.", icon="🚀")
                        st.rerun()

        # Truthfulness / Policy Footnote
        st.markdown("---")
        st.info(f"💡 **Policy & Data Integrity Note:** {result.metrics_note}")
    else:
        st.markdown("""
        <div class="apple-card-elevated" style="padding: 22px 26px; margin-top: 18px; border-radius: 16px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <span style="font-size: 1.3rem;">💡</span>
                <span style="font-weight: 700; font-size: 1.02rem; color: var(--apple-ink-primary); letter-spacing: -0.01em;">Quick Editorial Blueprint Starters</span>
            </div>
            <div style="font-size: 0.86rem; color: var(--apple-ink-secondary); line-height: 1.5; margin-bottom: 14px;">
                Select a high-intent Amazon affiliate seed query below to immediately analyze search intent, People Also Ask queries, and 3 differentiated editorial angles:
            </div>
        </div>
        """, unsafe_allow_html=True)

        q_s1, q_s2, q_s3 = st.columns(3, vertical_alignment="center")
        with q_s1:
            if st.button("🎧 noise cancelling headphones for flights", use_container_width=True, key="seed_kw_1"):
                st.session_state["last_researched_kw"] = "best noise cancelling headphones for flights"
                st.session_state["trigger_kw_analysis"] = True
                st.rerun()
        with q_s2:
            if st.button("💺 ergonomic office chair under 300", use_container_width=True, key="seed_kw_2"):
                st.session_state["last_researched_kw"] = "best ergonomic office chair under 300"
                st.session_state["trigger_kw_analysis"] = True
                st.rerun()
        with q_s3:
            if st.button("🌿 quiet air purifier for bedroom", use_container_width=True, key="seed_kw_3"):
                st.session_state["last_researched_kw"] = "quiet air purifier for bedroom"
                st.session_state["trigger_kw_analysis"] = True
                st.rerun()
