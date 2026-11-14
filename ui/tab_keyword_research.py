import streamlit as st
from services.research.keyword_analyst import analyze_keyword, KeywordAnalysisResult
from services.generator.gemini_client import GeminiClient

def render_keyword_research_tab():
    st.markdown("### 🔍 Keyword Intent & Editorial Strategy Explorer")
    st.caption("Expand seed keywords into search intent, People Also Ask (PAA) queries, and 3 distinct editorial angles. Grounded in truthful search dynamics—no fabricated volume numbers.")

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
        with st.spinner("Analyzing search intent, queries, and editorial angles with Gemini..."):
            client = GeminiClient()
            result: KeywordAnalysisResult = analyze_keyword(keyword_input.strip(), client=client)
            st.session_state["kw_analysis_result"] = result

    result: KeywordAnalysisResult = st.session_state.get("kw_analysis_result")
    if result and result.keyword:
        st.divider()
        st.markdown(f"#### Analysis for: **{result.keyword}**")

        # Top Intent & Format Summary
        c1, c2, c3 = st.columns([1.5, 2.5, 1.5])
        with c1:
            intent_color = {
                "Commercial Investigation": "blue",
                "Transactional": "green",
                "Informational": "orange"
            }.get(result.search_intent, "gray")
            st.markdown(f"**Search Intent:** :{intent_color}[**{result.search_intent}**]")
        with c2:
            st.markdown(f"**Intent Context:** {result.intent_explanation}")
        with c3:
            st.markdown(f"**Recommended Format:** `{result.recommended_article_type.title()}`")

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
                if st.button("➕ Push Related Queries to Bulk Queue Input"):
                    existing_bulk = st.session_state.get("bulk_keywords_input", "")
                    combined = (existing_bulk.strip() + "\n" + "\n".join(result.related_queries)).strip()
                    st.session_state["bulk_keywords_input"] = combined
                    st.success(f"Added {len(result.related_queries)} queries to Bulk Queue buffer!")
            else:
                st.info("No related queries available.")

        # 3 Editorial Angles
        st.markdown("---")
        st.markdown("##### 🎯 3 Differentiated Editorial Angles")
        st.caption("Choose an editorial perspective tailored to your audience to avoid generic affiliate copy.")

        cols = st.columns(3)
        for idx, angle in enumerate(result.editorial_angles):
            with cols[idx % 3]:
                st.markdown(f"### Angle {idx+1}: {angle.name}")
                st.markdown(f"**Target Audience:** {angle.target_audience}")
                st.markdown(f"**Focus:** {angle.editorial_focus}")
                
                if st.button(f"Use Angle {idx+1} in Single Workflow", key=f"btn_angle_{idx}"):
                    st.session_state["workflow_seed_keyword"] = result.keyword
                    st.session_state["workflow_editorial_angle"] = angle.name
                    st.session_state["workflow_editorial_focus"] = angle.editorial_focus
                    st.session_state["workflow_article_type"] = result.recommended_article_type
                    st.success(f"Angle '{angle.name}' applied! Switch to the **Single Workflow** tab to build your article.")

        # Truthfulness / Policy Footnote
        st.markdown("---")
        st.info(f"💡 **Policy & Data Integrity Note:** {result.metrics_note}")
