import streamlit as st
from services.research.keyword_analyst import analyze_keyword, KeywordAnalysisResult
from services.generator.factory import get_llm_client
from core.config import settings

def render_keyword_research_tab():
    active_provider = getattr(settings, "get_active_provider", lambda: getattr(settings, "AI_PROVIDER", "openai"))()
    active_model_name = "GPT-6 Luna" if active_provider == "openai" else "Gemini"

    st.markdown("### 🔍 Keyword Intent & Editorial Strategy Explorer")
    st.caption(f"Expand seed keywords into search intent, People Also Ask (PAA) queries, and 3 distinct editorial angles powered by **{active_model_name}**. Grounded in truthful search dynamics—no fabricated volume numbers.")

    col1, col2 = st.columns([3, 1])
    with col1:
        keyword_input = st.text_input(
            "Target Seed Keyword",
            value=st.session_state.get("last_researched_kw", ""),
            placeholder="e.g. best ergonomic office chair under 300, quiet air purifier for bedroom",
            help="Enter a product niche or search query to analyze consumer intent and editorial hooks."
        )
    with col2:
        st.write("")
        st.write("")
        analyze_btn = st.button("🚀 Analyze Keyword", type="primary", use_container_width=True)

    if analyze_btn and keyword_input.strip():
        st.session_state["last_researched_kw"] = keyword_input.strip()
        with st.spinner(f"Analyzing search intent, queries, and editorial angles with {active_model_name}..."):
            client = get_llm_client()
            result: KeywordAnalysisResult = analyze_keyword(keyword_input.strip(), client=client)
            st.session_state["kw_analysis_result"] = result

    result: KeywordAnalysisResult = st.session_state.get("kw_analysis_result")
    if result and result.keyword:
        st.divider()
        st.markdown(f"#### 🔍 Editorial Intent Blueprint: **{result.keyword}**")

        # Top Intent & Format Summary (Apple Capsule Pills)
        intent_bg, intent_fg, intent_border = {
            "Commercial Investigation": ("rgba(0, 113, 227, 0.09)", "#0071e3", "rgba(0, 113, 227, 0.25)"),
            "Transactional": ("rgba(52, 199, 89, 0.09)", "#15803d", "rgba(52, 199, 89, 0.25)"),
            "Informational": ("rgba(255, 149, 0, 0.09)", "#b45309", "rgba(255, 149, 0, 0.25)")
        }.get(result.search_intent, ("rgba(100, 116, 139, 0.09)", "#475569", "rgba(100, 116, 139, 0.2)"))

        st.markdown(f"""
        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 14px;">
            <span class="apple-pill-badge" style="background: {intent_bg}; color: {intent_fg}; border: 1px solid {intent_border}; font-size: 0.84rem; padding: 5px 14px;">
                🎯 Search Intent: <strong>{result.search_intent}</strong>
            </span>
            <span class="apple-pill-badge" style="background: rgba(88, 86, 214, 0.09); color: #4338ca; border: 1px solid rgba(88, 86, 214, 0.25); font-size: 0.84rem; padding: 5px 14px;">
                📄 Format: <strong>{result.recommended_article_type.title()}</strong>
            </span>
            <span style="color: #64748b; font-size: 0.88rem; margin-left: 4px;">{result.intent_explanation}</span>
        </div>
        """, unsafe_allow_html=True)

        # PAA & Related Queries in 2 columns
        st.markdown("---")
        q_col, r_col = st.columns(2)

        with q_col:
            st.markdown("##### ❓ High-Intent Questions (People Also Ask)")
            if result.user_questions:
                for idx, q in enumerate(result.user_questions, 1):
                    with st.expander(f"Q{idx}: {q.question}", expanded=True):
                        st.markdown(f"**Key Editorial Focus:** {q.focal_answer_point}")
            else:
                st.info("No specific user questions generated.")

        with r_col:
            st.markdown("##### 🔗 High-Relevance Related Queries")
            if result.related_queries:
                for qry in result.related_queries:
                    st.markdown(f"- `{qry}`")
                
                # Bulk queue quick-export helper
                if st.button("➕ Push Related Queries to Bulk Queue Input", use_container_width=True):
                    existing_bulk = st.session_state.get("bulk_keywords_input", "")
                    combined = (existing_bulk.strip() + "\n" + "\n".join(result.related_queries)).strip()
                    st.session_state["bulk_keywords_input"] = combined
                    st.toast(f"Added {len(result.related_queries)} queries to Bulk Queue buffer!", icon="📋")
            else:
                st.info("No related queries available.")

        # 3 Editorial Angles (Apple Bento Cards)
        st.markdown("---")
        st.markdown("##### 🎯 3 Differentiated Editorial Angles")
        st.caption("Choose an editorial perspective tailored to your audience to avoid generic affiliate copy.")

        cols = st.columns(3)
        angle_icons = ["💎", "⚖️", "⚡"]
        for idx, angle in enumerate(result.editorial_angles):
            with cols[idx % 3]:
                with st.container(border=True):
                    icon = angle_icons[idx % len(angle_icons)]
                    st.markdown(f"#### {icon} {angle.name}")
                    st.markdown(f"""
                    <div style="margin-bottom: 8px;">
                        <span class="apple-pill-badge" style="background: rgba(0, 113, 227, 0.08); color: #0071e3; border: 1px solid rgba(0, 113, 227, 0.2);">
                            Audience: {angle.target_audience}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"**Core Editorial Focus:**\n*{angle.editorial_focus}*")
                    st.write("")
                    if st.button(f"🚀 Dispatch to Single Workflow", key=f"btn_angle_{idx}", use_container_width=True, type="secondary"):
                        st.session_state["workflow_seed_keyword"] = result.keyword
                        st.session_state["workflow_editorial_angle"] = angle.name
                        st.session_state["workflow_editorial_focus"] = angle.editorial_focus
                        st.session_state["workflow_article_type"] = result.recommended_article_type
                        st.session_state["target_nav_tab"] = "Single Workflow"
                        st.toast(f"Angle '{angle.name}' applied! Switched to Single Workflow.", icon="🚀")
                        st.rerun()

        # Truthfulness / Policy Footnote
        st.markdown("---")
        st.info(f"💡 **Policy & Data Integrity Note:** {result.metrics_note}")
