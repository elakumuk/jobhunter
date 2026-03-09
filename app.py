#!/usr/bin/env python3
"""
JobHunter Web App — Ela's AI-Powered Job Search Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import csv
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# --- CONFIG ---
BASE_DIR = Path(__file__).parent
JOBS_FILE = BASE_DIR / "jobs_tracker.csv"
CONFIG_FILE = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR / "applications"

st.set_page_config(
    page_title="JobHunter — Ela's Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- HELPERS ---
@st.cache_data(ttl=5)
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    # Fallback: Streamlit Cloud secrets
    try:
        return dict(st.secrets.get("config", {}))
    except Exception:
        return {}

@st.cache_data(ttl=5)
def load_jobs():
    if not JOBS_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(JOBS_FILE)
    if 'match_score' in df.columns:
        df['match_score'] = pd.to_numeric(df['match_score'], errors='coerce').fillna(0).astype(int)
    return df

def save_jobs(df):
    df.to_csv(JOBS_FILE, index=False)
    load_jobs.clear()

def get_gemini():
    try:
        from google import genai
        config = load_config()
        api_key = config.get('gemini_api_key', '')
        if not api_key:
            return None
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def ai_generate(prompt, fallback="AI kullanılamadı."):
    client = get_gemini()
    if not client:
        return fallback
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            if '429' in str(e) and attempt < 2:
                time.sleep((attempt + 1) * 10)
            else:
                return fallback
    return fallback

ELA_PROFILE = """
Candidate Profile:
- Name: Ela Kumuk
- Education: M.S. Business Analytics (MSBA), Brandeis University, graduating May 2026
- Undergrad: Double major in Business & Psychology, Minor in Studio Art
- Technical Skills: Python, R, SQL, Tableau, Excel, MySQL, Jupyter Notebook, Google Colab
- Analytics: Statistical Analysis, Econometrics, Regression, Hypothesis Testing, A/B Testing, Marketing Analytics, Data Visualization
- Coursework: Python for Business Analytics, Econometrics with R, Marketing Analytics, Information Visualization
- Unique: Consumer Psychology background, E-commerce experience (family business), bilingual (Turkish/English)
- Visa: F1 Student (OPT eligible, needs H1B sponsorship)
- Location: Waltham, MA
"""

# --- SMART FILTER LOGIC ---
SKIP_TITLE_KEYWORDS = [
    'clearance', 'secret', 'ts/sci', 'security clearance',
    'principal', 'staff', 'senior', 'lead', 'director', 'manager',
    'phd required', 'phd degree required',
    'nurse', 'nursing', 'clinical', 'physician',
    'bilingual spanish', 'bilingual french', 'hebrew',
]
SKIP_LOCATION_KEYWORDS = [
    'canada', 'united kingdom', 'uk', 'india', 'germany', 'australia',
    'singapore', 'japan', 'brazil', 'mexico', 'ireland',
]

def check_skip_reason(row):
    title_lower = str(row.get('title', '')).lower()
    loc_lower = str(row.get('location', '')).lower()
    company = str(row.get('company', '')).strip()
    score = int(row.get('match_score', 0))

    for kw in SKIP_TITLE_KEYWORDS:
        if kw in title_lower:
            return f"Title: '{kw}'"
    for kw in SKIP_LOCATION_KEYWORDS:
        if kw in loc_lower and 'remote' not in loc_lower:
            return f"Location: international"
    if score < 25:
        return f"Low score: {score}"
    if company in ['↳', '']:
        return "Sub-listing"
    return None


# ==========================================
#  SIDEBAR
# ==========================================
with st.sidebar:
    st.title("🎯 JobHunter")
    st.caption("Ela's AI-Powered Job Search")
    st.divider()

    page = st.radio("Sayfa", [
        "📊 Dashboard",
        "🧹 Smart Filter",
        "🚀 Batch Apply",
        "📝 Tek Başvuru",
        "🎤 Mülakat Hazırlık",
        "🛂 H1B Kontrol",
        "🔍 İlan Detayları",
        "🤖 AI Danışman",
        "⏰ Hatırlatmalar",
        "📅 Günlük Rapor",
        "⚙️ Ayarlar"
    ], label_visibility="collapsed")

    st.divider()
    df = load_jobs()
    if not df.empty:
        total = len(df)
        applied = len(df[df['status'].isin(['applied', 'interview', 'offer'])])
        st.metric("Toplam İş", total)
        st.metric("Başvurulan", applied)
        st.metric("Mülakat", len(df[df['status'] == 'interview']))


# ==========================================
#  DASHBOARD
# ==========================================
if page == "📊 Dashboard":
    st.title("📊 Dashboard")

    df = load_jobs()
    if df.empty:
        st.warning("Henüz iş yok. Terminal'de `python3 job_hunter.py search` çalıştır.")
        st.stop()

    # KPI Row
    col1, col2, col3, col4, col5 = st.columns(5)
    total = len(df)
    new_count = len(df[df['status'] == 'new'])
    preparing = len(df[df['status'] == 'preparing'])
    applied = len(df[df['status'] == 'applied'])
    interview = len(df[df['status'] == 'interview'])

    col1.metric("Toplam", total)
    col2.metric("Yeni", new_count, delta=f"{new_count} incelenmemiş" if new_count > 0 else None)
    col3.metric("Hazırlanan", preparing)
    col4.metric("Başvurulan", applied)
    col5.metric("Mülakat", interview)

    st.divider()

    # Charts row
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        status_counts = df['status'].value_counts().reset_index()
        status_counts.columns = ['Durum', 'Sayı']
        color_map = {
            'new': '#636EFA', 'preparing': '#FFA15A', 'applied': '#00CC96',
            'interview': '#AB63FA', 'offer': '#00D4AA', 'rejected': '#EF553B',
            'skipped': '#BAB0AC', 'saved': '#19D3F3'
        }
        fig = px.pie(status_counts, values='Sayı', names='Durum', title="Durum Dağılımı",
                     color='Durum', color_discrete_map=color_map, hole=0.4)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        score_bins = pd.cut(df['match_score'], bins=[0, 30, 50, 70, 100],
                           labels=['Düşük (0-30)', 'Orta (30-50)', 'İyi (50-70)', 'Yüksek (70-100)'])
        score_dist = score_bins.value_counts().sort_index().reset_index()
        score_dist.columns = ['Aralık', 'Sayı']
        fig2 = px.bar(score_dist, x='Aralık', y='Sayı', title="Match Score Dağılımı",
                      color='Aralık', color_discrete_sequence=['#EF553B', '#FFA15A', '#00CC96', '#636EFA'])
        fig2.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    # Location chart
    def simplify_location(loc):
        loc = str(loc).lower()
        if 'remote' in loc: return 'Remote'
        if any(x in loc for x in ['ma', 'boston', 'cambridge', 'waltham']): return 'Massachusetts'
        if any(x in loc for x in ['ny', 'new york']): return 'New York'
        if any(x in loc for x in ['ca', 'san francisco']): return 'California'
        if 'tx' in loc: return 'Texas'
        if any(x in loc for x in ['il', 'chicago']): return 'Illinois'
        if 'canada' in loc: return 'Canada'
        return 'Diğer ABD'

    df['loc_simple'] = df['location'].apply(simplify_location)
    loc_counts = df['loc_simple'].value_counts().reset_index()
    loc_counts.columns = ['Lokasyon', 'Sayı']
    fig3 = px.bar(loc_counts, x='Sayı', y='Lokasyon', orientation='h', title="Lokasyon Dağılımı",
                  color='Sayı', color_continuous_scale='Blues')
    fig3.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

    # Pipeline funnel
    st.subheader("📈 Başvuru Pipeline")
    funnel_data = {
        'Aşama': ['Toplam İş', 'Filtrelenmemiş', 'Hazırlanan', 'Başvurulan', 'Mülakat', 'Teklif'],
        'Sayı': [
            total,
            len(df[df['status'] != 'skipped']),
            preparing + applied + interview + len(df[df['status'] == 'offer']),
            applied + interview + len(df[df['status'] == 'offer']),
            interview + len(df[df['status'] == 'offer']),
            len(df[df['status'] == 'offer'])
        ]
    }
    fig_funnel = go.Figure(go.Funnel(
        y=funnel_data['Aşama'], x=funnel_data['Sayı'],
        textinfo="value+percent initial",
        marker=dict(color=['#636EFA', '#00CC96', '#FFA15A', '#AB63FA', '#FF6692', '#00D4AA'])
    ))
    fig_funnel.update_layout(height=350)
    st.plotly_chart(fig_funnel, use_container_width=True)

    # Top jobs table
    st.subheader("⭐ En İyi Eşleşmeler")
    active = df[df['status'].isin(['new', 'preparing'])].sort_values('match_score', ascending=False).head(15)
    if not active.empty:
        display_cols = ['job_id', 'company', 'title', 'location', 'match_score', 'status']
        st.dataframe(
            active[display_cols].reset_index(drop=True),
            column_config={
                'job_id': 'ID',
                'company': 'Şirket',
                'title': 'Pozisyon',
                'location': 'Lokasyon',
                'match_score': st.column_config.ProgressColumn('Skor', min_value=0, max_value=100),
                'status': 'Durum'
            },
            hide_index=True,
            use_container_width=True
        )

    # Full table with search
    st.subheader("📋 Tüm İşler")
    search_term = st.text_input("🔍 Ara (şirket, pozisyon, lokasyon)...", key="search_all")
    filtered = df.copy()
    if search_term:
        mask = (
            filtered['company'].str.contains(search_term, case=False, na=False) |
            filtered['title'].str.contains(search_term, case=False, na=False) |
            filtered['location'].str.contains(search_term, case=False, na=False)
        )
        filtered = filtered[mask]

    status_filter = st.multiselect("Durum filtresi", df['status'].unique().tolist(), default=None)
    if status_filter:
        filtered = filtered[filtered['status'].isin(status_filter)]

    st.dataframe(
        filtered[['job_id', 'company', 'title', 'location', 'match_score', 'status', 'date_found']].sort_values('match_score', ascending=False).reset_index(drop=True),
        column_config={
            'match_score': st.column_config.ProgressColumn('Skor', min_value=0, max_value=100),
        },
        hide_index=True,
        use_container_width=True,
        height=400
    )


# ==========================================
#  SMART FILTER
# ==========================================
elif page == "🧹 Smart Filter":
    st.title("🧹 Smart Filter")
    st.markdown("Sana uygun olmayan işleri otomatik eler: yurtdışı, clearance, senior, düşük skor...")

    df = load_jobs()
    new_jobs = df[df['status'] == 'new']

    if new_jobs.empty:
        st.success("Filtrelenecek yeni iş yok!")
        st.stop()

    st.info(f"**{len(new_jobs)}** yeni iş analiz edilecek.")

    # Preview what will be skipped
    skip_preview = []
    keep_preview = []
    for _, row in new_jobs.iterrows():
        reason = check_skip_reason(row)
        if reason:
            skip_preview.append({**row.to_dict(), 'skip_reason': reason})
        else:
            keep_preview.append(row.to_dict())

    col1, col2 = st.columns(2)
    col1.metric("Atlanacak", len(skip_preview), delta=f"-{len(skip_preview)}", delta_color="normal")
    col2.metric("Kalacak", len(keep_preview))

    if skip_preview:
        with st.expander(f"⏭️ Atlanacak işler ({len(skip_preview)})", expanded=False):
            skip_df = pd.DataFrame(skip_preview)
            st.dataframe(
                skip_df[['job_id', 'company', 'title', 'location', 'match_score', 'skip_reason']].reset_index(drop=True),
                hide_index=True, use_container_width=True
            )

    if keep_preview:
        with st.expander(f"✅ Kalacak işler ({len(keep_preview)})", expanded=True):
            keep_df = pd.DataFrame(keep_preview).sort_values('match_score', ascending=False)
            st.dataframe(
                keep_df[['job_id', 'company', 'title', 'location', 'match_score']].reset_index(drop=True),
                column_config={'match_score': st.column_config.ProgressColumn('Skor', min_value=0, max_value=100)},
                hide_index=True, use_container_width=True
            )

    if st.button("🧹 Filtreyi Uygula", type="primary", use_container_width=True):
        with st.spinner("Filtreleniyor..."):
            for item in skip_preview:
                df.loc[df['job_id'] == item['job_id'], 'status'] = 'skipped'
                df.loc[df['job_id'] == item['job_id'], 'notes'] = f"Auto-filtered: {item['skip_reason']}"
            save_jobs(df)
        st.success(f"✅ {len(skip_preview)} iş atlandı, {len(keep_preview)} iş kaldı!")
        st.rerun()


# ==========================================
#  BATCH APPLY
# ==========================================
elif page == "🚀 Batch Apply":
    st.title("🚀 Toplu AI Başvuru")
    st.markdown("En iyi işler için tek tıkla AI cover letter, resume tips ve outreach mesajları.")

    df = load_jobs()
    new_jobs = df[df['status'] == 'new'].sort_values('match_score', ascending=False)

    if new_jobs.empty:
        st.warning("Başvurulacak yeni iş yok. Önce smart-filter çalıştır.")
        st.stop()

    count = st.slider("Kaç işe başvuru paketi hazırlansın?", 1, min(20, len(new_jobs)), min(5, len(new_jobs)))

    top_jobs = new_jobs.head(count)
    st.dataframe(
        top_jobs[['job_id', 'company', 'title', 'location', 'match_score']].reset_index(drop=True),
        column_config={'match_score': st.column_config.ProgressColumn('Skor', min_value=0, max_value=100)},
        hide_index=True, use_container_width=True
    )

    if st.button(f"🚀 {count} İş İçin AI Paket Hazırla", type="primary", use_container_width=True):
        progress = st.progress(0)
        status_text = st.empty()
        results = []

        for i, (_, job) in enumerate(top_jobs.iterrows()):
            company = job['company']
            title = job['title']
            job_id = job['job_id']

            status_text.markdown(f"**[{i+1}/{count}]** {title} @ {company}...")
            progress.progress((i) / count)

            safe_name = re.sub(r'[^\w\-]', '_', f"{company}_{title}")
            out_dir = OUTPUT_DIR / safe_name
            out_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Cover Letter
                prompt_cl = f"""Write a professional cover letter (4 paragraphs, under 400 words).
Not generic. No cliches. Specific to this company/role.

{ELA_PROFILE}

Job: {title} at {company}, {job.get('location', '')}

Format: Header with name/contact/date, "Dear Hiring Manager,", 4 paragraphs, "Sincerely, Ela Kumuk"
Highlight Psychology+Business+Analytics as differentiator. Mention specific coursework."""

                cover = ai_generate(prompt_cl)
                with open(out_dir / "cover_letter.txt", 'w') as f:
                    f.write(cover)
                time.sleep(2)

                # Resume Tips
                prompt_rt = f"""Give specific resume tailoring advice for this job. Be actionable.
{ELA_PROFILE}
Job: {title} at {company}
Include: what to highlight, keywords to add, 3 new bullet points to write, what to de-emphasize."""

                tips = ai_generate(prompt_rt)
                with open(out_dir / "resume_tips.txt", 'w') as f:
                    f.write(f"Resume Tips: {title} at {company}\n{'='*60}\n\n{tips}")
                time.sleep(2)

                # Outreach
                prompt_out = f"""Write networking messages for this job application. Sound natural.
{ELA_PROFILE}
Job: {title} at {company}
Write: 1) LinkedIn connection request (max 300 chars) 2) Follow-up message 3) Cold email with subject line"""

                outreach = ai_generate(prompt_out)
                with open(out_dir / "outreach_messages.txt", 'w') as f:
                    f.write(outreach)
                time.sleep(2)

                # Update status
                df.loc[df['job_id'] == job_id, 'status'] = 'preparing'
                save_jobs(df)

                results.append({"İş": f"{title} @ {company}", "Durum": "✅", "Klasör": str(out_dir)})

            except Exception as e:
                results.append({"İş": f"{title} @ {company}", "Durum": f"❌ {e}", "Klasör": ""})

        progress.progress(1.0)
        status_text.markdown("**✅ Tamamlandı!**")

        st.divider()
        st.subheader("Sonuçlar")
        st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)

        st.info(f"📁 Dosyalar: `{OUTPUT_DIR}`\n\nŞimdi her klasördeki cover_letter.txt'yi incele ve başvur!")


# ==========================================
#  TEK BAŞVURU
# ==========================================
elif page == "📝 Tek Başvuru":
    st.title("📝 Tek İş İçin AI Başvuru")

    df = load_jobs()
    active = df[df['status'].isin(['new', 'preparing'])].sort_values('match_score', ascending=False)

    if active.empty:
        st.warning("Başvurulacak iş yok.")
        st.stop()

    # Job selector
    job_options = {f"{r['job_id']} — {r['company']} — {r['title']} (Skor: {r['match_score']})": r['job_id']
                   for _, r in active.iterrows()}
    selected = st.selectbox("İş seç", list(job_options.keys()))
    job_id = job_options[selected]
    job = df[df['job_id'] == job_id].iloc[0]

    # Job info
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Şirket:** {job['company']}")
    col2.markdown(f"**Lokasyon:** {job['location']}")
    col3.markdown(f"**Skor:** {job['match_score']}/100")

    if job.get('url') and pd.notna(job['url']):
        st.markdown(f"🔗 [Başvuru Linki]({job['url']})")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["📝 Cover Letter", "📋 Resume Tips", "💬 Outreach", "🔬 Analiz"])

    with tab1:
        if st.button("📝 AI Cover Letter Oluştur", key="gen_cl"):
            with st.spinner("AI yazıyor..."):
                prompt = f"""Write a professional cover letter (4 paragraphs, under 400 words). Not generic.
{ELA_PROFILE}
Job: {job['title']} at {job['company']}, {job['location']}
Format: Header, Dear Hiring Manager, 4 paragraphs, Sincerely Ela Kumuk."""
                result = ai_generate(prompt)
                st.session_state['cover_letter'] = result

        if 'cover_letter' in st.session_state:
            st.text_area("Cover Letter", st.session_state['cover_letter'], height=400)
            # Save button
            if st.button("💾 Kaydet"):
                safe_name = re.sub(r'[^\w\-]', '_', f"{job['company']}_{job['title']}")
                out_dir = OUTPUT_DIR / safe_name
                out_dir.mkdir(parents=True, exist_ok=True)
                with open(out_dir / "cover_letter.txt", 'w') as f:
                    f.write(st.session_state['cover_letter'])
                st.success(f"Kaydedildi: {out_dir / 'cover_letter.txt'}")

    with tab2:
        if st.button("📋 AI Resume Tips Oluştur", key="gen_rt"):
            with st.spinner("AI analiz ediyor..."):
                prompt = f"""Give specific resume tailoring advice. Be actionable.
{ELA_PROFILE}
Job: {job['title']} at {job['company']}
Include: highlights, keywords, 3 new bullet points, what to remove."""
                result = ai_generate(prompt)
                st.session_state['resume_tips'] = result
        if 'resume_tips' in st.session_state:
            st.markdown(st.session_state['resume_tips'])

    with tab3:
        if st.button("💬 AI Outreach Mesajları", key="gen_out"):
            with st.spinner("AI yazıyor..."):
                prompt = f"""Write networking messages. Sound natural, not robotic.
{ELA_PROFILE}
Job: {job['title']} at {job['company']}
Write: 1) LinkedIn request (max 300 chars) 2) Follow-up message 3) Cold email"""
                result = ai_generate(prompt)
                st.session_state['outreach'] = result
        if 'outreach' in st.session_state:
            st.markdown(st.session_state['outreach'])

    with tab4:
        if st.button("🔬 AI İş Analizi", key="gen_an"):
            with st.spinner("AI analiz ediyor..."):
                prompt = f"""Analyze this job for the candidate. Write in Turkish+English mix.
{ELA_PROFILE}
Job: {job['title']} at {job['company']}, {job['location']}
Include: company analysis, fit score (1-10), strengths/weaknesses, H1B likelihood, daily tasks, application strategy, red flags."""
                result = ai_generate(prompt)
                st.session_state['analysis'] = result
        if 'analysis' in st.session_state:
            st.markdown(st.session_state['analysis'])

    # Status update
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        new_status = st.selectbox("Durumu güncelle", ['new', 'preparing', 'applied', 'interview', 'rejected', 'offer'])
    with col2:
        if st.button("✅ Güncelle", use_container_width=True):
            df.loc[df['job_id'] == job_id, 'status'] = new_status
            if new_status == 'applied':
                df.loc[df['job_id'] == job_id, 'date_applied'] = datetime.now().strftime('%Y-%m-%d')
            save_jobs(df)
            st.success(f"{job_id} → '{new_status}' olarak güncellendi!")
            st.rerun()


# ==========================================
#  MÜLAKAT HAZIRLIK
# ==========================================
elif page == "🎤 Mülakat Hazırlık":
    st.title("🎤 AI Mülakat Hazırlık")

    df = load_jobs()
    active = df[df['status'].isin(['preparing', 'applied', 'interview'])].sort_values('match_score', ascending=False)

    if active.empty:
        st.warning("Mülakat hazırlığı yapılacak iş yok. Önce başvuru yap.")
        st.stop()

    job_options = {f"{r['job_id']} — {r['company']} — {r['title']}": r['job_id'] for _, r in active.iterrows()}
    selected = st.selectbox("İş seç", list(job_options.keys()))
    job_id = job_options[selected]
    job = df[df['job_id'] == job_id].iloc[0]

    st.markdown(f"**{job['title']}** @ **{job['company']}** | {job['location']}")

    if st.button("🎤 AI Mülakat Soruları Hazırla", type="primary", use_container_width=True):
        with st.spinner("AI mülakat soruları hazırlıyor... (30 saniye kadar sürebilir)"):
            prompt = f"""Prepare interview questions and answers. Write in Turkish+English mix.
{ELA_PROFILE}
Job: {job['title']} at {job['company']}

Provide:
## TEKNİK SORULAR (8 soru) - SQL, Python, stats, with strong answers
## BEHAVIORAL SORULAR (6 soru) - STAR format answers
## ŞİRKETE ÖZEL SORULAR (4 soru) - about {job['company']}
## ELA'NIN SORMASI GEREKEN SORULAR (5 soru)
## MÜLAKAT İPUÇLARI - dress code, format, common pitfalls"""
            result = ai_generate(prompt)
            st.session_state['interview_prep'] = result

            # Save
            safe_name = re.sub(r'[^\w\-]', '_', f"{job['company']}_{job['title']}")
            out_dir = OUTPUT_DIR / safe_name
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / "interview_prep.txt", 'w') as f:
                f.write(result)

    if 'interview_prep' in st.session_state:
        st.markdown(st.session_state['interview_prep'])


# ==========================================
#  AI DANIŞMAN
# ==========================================
elif page == "🤖 AI Danışman":
    st.title("🤖 AI Kariyer Danışmanı")
    st.markdown("İş arama sürecinde aklına takılan her şeyi sor.")

    # Quick suggestions
    st.markdown("**Hızlı sorular:**")
    quick_cols = st.columns(3)
    quick_questions = [
        "H1B sponsor eden şirketleri nasıl bulurum?",
        "Cover letter'ımda neleri vurgulamalıyım?",
        "Data Analyst mülakat süreci nasıl oluyor?",
        "LinkedIn profilimi nasıl optimize ederim?",
        "Networking mesajı nasıl yazmalıyım?",
        "Boston'da en iyi data analyst şirketleri?"
    ]
    for i, q in enumerate(quick_questions):
        col = quick_cols[i % 3]
        if col.button(q, key=f"quick_{i}", use_container_width=True):
            st.session_state['ai_question'] = q

    question = st.text_area("Sorunuz:", value=st.session_state.get('ai_question', ''), height=100)

    if st.button("🤖 AI'ya Sor", type="primary") and question:
        with st.spinner("AI düşünüyor..."):
            df = load_jobs()
            stats = f"Jobs tracked: {len(df)}, Applied: {len(df[df['status']=='applied'])}, Interviews: {len(df[df['status']=='interview'])}"
            prompt = f"""You are a career advisor. Answer helpfully in Turkish (technical terms in English OK).
{ELA_PROFILE}
Job search status: {stats}
Question: {question}
Give specific, actionable advice."""
            result = ai_generate(prompt)
            st.session_state['ai_answer'] = result

    if 'ai_answer' in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state['ai_answer'])


# ==========================================
#  HATIRLATMALAR
# ==========================================
elif page == "⏰ Hatırlatmalar":
    st.title("⏰ Takip Hatırlatmaları")

    df = load_jobs()
    today = datetime.now()

    preparing = df[df['status'] == 'preparing']
    applied = df[df['status'] == 'applied']
    interview = df[df['status'] == 'interview']

    if preparing.empty and applied.empty and interview.empty:
        st.info("Henüz takip edilecek başvuru yok. Önce batch apply çalıştır!")
        st.stop()

    # Preparing — need to actually apply
    if not preparing.empty:
        st.subheader(f"📝 Başvuru Bekliyor ({len(preparing)})")
        for _, j in preparing.iterrows():
            days = (today - datetime.strptime(str(j['date_found']), '%Y-%m-%d')).days
            urgency = "🔴" if days > 7 else "🟡" if days > 3 else "🟢"
            col1, col2, col3 = st.columns([4, 1, 1])
            col1.markdown(f"{urgency} **{j['company']}** — {j['title']}")
            col2.markdown(f"`{days} gün`")
            if pd.notna(j.get('url')) and j['url']:
                col3.markdown(f"[Başvur]({j['url']})")

            # Quick status update
            if st.button(f"✅ Başvurdum → applied", key=f"prep_{j['job_id']}"):
                df.loc[df['job_id'] == j['job_id'], 'status'] = 'applied'
                df.loc[df['job_id'] == j['job_id'], 'date_applied'] = today.strftime('%Y-%m-%d')
                save_jobs(df)
                st.rerun()

    # Applied — follow-up needed?
    if not applied.empty:
        st.subheader(f"📨 Başvurulan İşler ({len(applied)})")
        for _, j in applied.iterrows():
            try:
                applied_date = datetime.strptime(str(j['date_applied']), '%Y-%m-%d')
                days_since = (today - applied_date).days
            except (ValueError, TypeError):
                days_since = 0

            if days_since >= 14:
                urgency = "🔴 Follow-up at!"
            elif days_since >= 7:
                urgency = "🟡 Yakında follow-up"
            else:
                urgency = "🟢 Bekleniyor"

            col1, col2 = st.columns([5, 1])
            col1.markdown(f"{urgency} **{j['company']}** — {j['title']} ({days_since} gün)")

            bcol1, bcol2 = st.columns(2)
            if bcol1.button(f"🎤 Mülakat aldım", key=f"int_{j['job_id']}"):
                df.loc[df['job_id'] == j['job_id'], 'status'] = 'interview'
                save_jobs(df)
                st.rerun()
            if bcol2.button(f"❌ Reddedildi", key=f"rej_{j['job_id']}"):
                df.loc[df['job_id'] == j['job_id'], 'status'] = 'rejected'
                save_jobs(df)
                st.rerun()

    # Interviews
    if not interview.empty:
        st.subheader(f"🎤 Mülakat Aşaması ({len(interview)})")
        for _, j in interview.iterrows():
            st.markdown(f"⭐ **{j['company']}** — {j['title']}")
            col1, col2 = st.columns(2)
            if col1.button(f"🎉 Teklif aldım!", key=f"off_{j['job_id']}"):
                df.loc[df['job_id'] == j['job_id'], 'status'] = 'offer'
                save_jobs(df)
                st.balloons()
                st.rerun()
            if col2.button(f"❌ Reddedildi", key=f"intrej_{j['job_id']}"):
                df.loc[df['job_id'] == j['job_id'], 'status'] = 'rejected'
                save_jobs(df)
                st.rerun()


# ==========================================
#  AYARLAR
# ==========================================
elif page == "⚙️ Ayarlar":
    st.title("⚙️ Ayarlar")

    config = load_config()

    st.subheader("Profil")
    col1, col2 = st.columns(2)
    name = col1.text_input("İsim", config.get('name', ''))
    email = col2.text_input("Email", config.get('email', ''))
    location = col1.text_input("Lokasyon", config.get('location', ''))
    graduation = col2.text_input("Mezuniyet", config.get('graduation', ''))

    st.subheader("Gemini API")
    api_key = st.text_input("API Key", config.get('gemini_api_key', ''), type="password")

    st.subheader("Hedef Roller")
    roles = st.text_area("Roller (her satıra bir tane)", "\n".join(config.get('target_roles', [])))

    st.subheader("Hedef Şirketler")
    companies = st.text_area("Şirketler (her satıra bir tane)", "\n".join(config.get('target_companies', [])))

    if st.button("💾 Kaydet", type="primary"):
        config['name'] = name
        config['email'] = email
        config['location'] = location
        config['graduation'] = graduation
        config['gemini_api_key'] = api_key
        config['target_roles'] = [r.strip() for r in roles.strip().split('\n') if r.strip()]
        config['target_companies'] = [c.strip() for c in companies.strip().split('\n') if c.strip()]
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        load_config.clear()
        st.success("✅ Ayarlar kaydedildi!")


# ==========================================
#  H1B KONTROL
# ==========================================
elif page == "🛂 H1B Kontrol":
    st.title("🛂 H1B Sponsorship Kontrolü")
    st.markdown("Şirketlerin H1B sponsor olma durumunu otomatik kontrol eder.")

    df = load_jobs()
    if df.empty:
        st.warning("Henüz iş yok.")
        st.stop()

    try:
        from h1b_checker import check_h1b_sponsor, KNOWN_H1B_SPONSORS
        h1b_available = True
    except ImportError:
        h1b_available = False
        st.error("h1b_checker.py bulunamadı. Lütfen dosyanın JobHunter klasöründe olduğundan emin ol.")
        st.stop()

    # Show current status
    h1b_counts = df['h1b_sponsor'].value_counts()
    col1, col2, col3 = st.columns(3)
    col1.metric("Sponsor ✅", int(h1b_counts.get('yes', 0)) + int(h1b_counts.get('likely', 0)))
    col2.metric("Bilinmiyor ❓", int(h1b_counts.get('check', 0)) + int(h1b_counts.get('unknown', 0)))
    col3.metric("Sponsor Değil ❌", int(h1b_counts.get('unlikely', 0)))

    if st.button("🛂 Tüm Şirketleri Kontrol Et", type="primary", use_container_width=True):
        with st.spinner("H1B sponsorship kontrol ediliyor..."):
            results = []
            for idx, row in df.iterrows():
                company = str(row.get('company', ''))
                status = check_h1b_sponsor(company)
                df.loc[idx, 'h1b_sponsor'] = status
                results.append({'Şirket': company, 'H1B': status})
            save_jobs(df)

        st.success("✅ H1B kontrolü tamamlandı!")

        result_df = pd.DataFrame(results)
        sponsor_counts = result_df['H1B'].value_counts()

        fig = px.pie(values=sponsor_counts.values, names=sponsor_counts.index,
                     title="H1B Sponsorship Dağılımı",
                     color=sponsor_counts.index,
                     color_discrete_map={'yes': '#00CC96', 'likely': '#636EFA', 'unknown': '#FFA15A', 'unlikely': '#EF553B'})
        st.plotly_chart(fig, use_container_width=True)
        st.rerun()

    # Show sponsor jobs
    st.divider()
    sponsor_jobs = df[df['h1b_sponsor'].isin(['yes', 'likely'])].sort_values('match_score', ascending=False)
    if not sponsor_jobs.empty:
        st.subheader(f"✅ H1B Sponsor Olan Şirketler ({len(sponsor_jobs)})")
        st.dataframe(
            sponsor_jobs[['job_id', 'company', 'title', 'location', 'match_score', 'h1b_sponsor', 'status']].reset_index(drop=True),
            column_config={'match_score': st.column_config.ProgressColumn('Skor', min_value=0, max_value=100)},
            hide_index=True, use_container_width=True
        )

    unknown_jobs = df[df['h1b_sponsor'].isin(['check', 'unknown'])]
    if not unknown_jobs.empty:
        with st.expander(f"❓ H1B Durumu Bilinmeyen ({len(unknown_jobs)})"):
            st.dataframe(
                unknown_jobs[['job_id', 'company', 'title', 'match_score']].reset_index(drop=True),
                hide_index=True, use_container_width=True
            )

    st.info(f"📊 Bilinen H1B sponsor veritabanında **{len(KNOWN_H1B_SPONSORS)}** şirket var.")


# ==========================================
#  İLAN DETAYLARI (SCRAPER)
# ==========================================
elif page == "🔍 İlan Detayları":
    st.title("🔍 İş İlanı Detayları")
    st.markdown("İlan URL'lerinden job description çeker ve AI ile analiz eder.")

    df = load_jobs()
    active = df[df['status'].isin(['new', 'preparing'])].sort_values('match_score', ascending=False)

    if active.empty:
        st.warning("Aktif iş yok.")
        st.stop()

    try:
        from job_scraper import fetch_job_description, extract_requirements
        scraper_available = True
    except ImportError:
        scraper_available = False

    if not scraper_available:
        st.error("job_scraper.py bulunamadı.")
        st.stop()

    # Single job scrape
    st.subheader("Tek İlan Analizi")
    job_options = {f"{r['job_id']} — {r['company']} — {r['title']}": r['job_id'] for _, r in active.iterrows()}
    selected = st.selectbox("İş seç", list(job_options.keys()), key="scrape_select")
    job_id = job_options[selected]
    job = df[df['job_id'] == job_id].iloc[0]

    url = str(job.get('url', ''))
    st.markdown(f"**{job['title']}** @ **{job['company']}**")
    if url and url != 'nan':
        st.markdown(f"🔗 {url}")

    if st.button("🔍 İlan Detayını Çek", type="primary"):
        if not url or url == 'nan':
            st.error("Bu ilanın URL'si yok.")
        else:
            with st.spinner("İlan çekiliyor..."):
                description = fetch_job_description(url)
                if description:
                    st.session_state['job_desc'] = description
                    reqs = extract_requirements(description)
                    st.session_state['job_reqs'] = reqs

                    # Save
                    safe_name = re.sub(r'[^\w\-]', '_', f"{job['company']}_{job['title']}")
                    out_dir = OUTPUT_DIR / safe_name
                    out_dir.mkdir(parents=True, exist_ok=True)
                    with open(out_dir / "job_description.txt", 'w') as f:
                        f.write(description)
                else:
                    st.warning("İlan detayı çekilemedi. Site erişimi engelliyor olabilir.")

    if 'job_desc' in st.session_state:
        tab1, tab2, tab3 = st.tabs(["📄 İlan Metni", "📋 Gereksinimler", "🤖 AI Analiz"])

        with tab1:
            st.text_area("Job Description", st.session_state['job_desc'], height=400)

        with tab2:
            reqs = st.session_state.get('job_reqs', {})
            if reqs:
                col1, col2 = st.columns(2)
                col1.markdown("**Gerekli Beceriler:**")
                for s in reqs.get('required_skills', []):
                    col1.markdown(f"- {s}")
                col2.markdown(f"**Deneyim:** {reqs.get('experience_years', 'Belirtilmemiş')}")
                col2.markdown(f"**Eğitim:** {reqs.get('education', 'Belirtilmemiş')}")
                col2.markdown(f"**Entry-level:** {'✅ Evet' if reqs.get('is_entry_level') else '❌ Hayır'}")
                col2.markdown(f"**Vize/H1B bahsi:** {'✅ Evet' if reqs.get('mentions_visa') else '❌ Yok'}")
                if reqs.get('visa_friendly') is True:
                    col2.markdown("**Vize dostu:** ✅ Olumlu")
                elif reqs.get('visa_friendly') is False:
                    col2.markdown("**Vize dostu:** ❌ Olumsuz (sponsorship yok deniyor olabilir)")

        with tab3:
            if st.button("🤖 AI ile İlan Analizi", key="ai_desc_analyze"):
                with st.spinner("AI analiz ediyor..."):
                    desc_text = st.session_state['job_desc'][:2000]
                    prompt = f"""Analyze this job description for the candidate. Turkish+English mix.
{ELA_PROFILE}
Job: {job['title']} at {job['company']}
Job Description: {desc_text}

Provide: 1) Fit score 1-10 with explanation 2) Matching skills 3) Missing skills 4) Red flags 5) Application tips"""
                    result = ai_generate(prompt)
                    st.markdown(result)

    # Batch scrape
    st.divider()
    st.subheader("Toplu İlan Çekme")
    batch_count = st.slider("Kaç ilan çekilsin?", 5, 30, 10, key="scrape_batch_count")
    if st.button(f"🔍 En İyi {batch_count} İlanı Çek"):
        top = active.head(batch_count)
        progress = st.progress(0)
        results = []
        for i, (_, row) in enumerate(top.iterrows()):
            progress.progress(i / batch_count)
            url = str(row.get('url', ''))
            if url and url != 'nan':
                desc = fetch_job_description(url)
                if desc:
                    safe_name = re.sub(r'[^\w\-]', '_', f"{row['company']}_{row['title']}")
                    out_dir = OUTPUT_DIR / safe_name
                    out_dir.mkdir(parents=True, exist_ok=True)
                    with open(out_dir / "job_description.txt", 'w') as f:
                        f.write(desc)
                    reqs = extract_requirements(desc)
                    results.append({"Şirket": row['company'], "Pozisyon": row['title'],
                                   "Entry-level": "✅" if reqs.get('is_entry_level') else "❌",
                                   "H1B bahsi": "✅" if reqs.get('mentions_visa') else "—",
                                   "Durum": "✅ Çekildi"})
                else:
                    results.append({"Şirket": row['company'], "Pozisyon": row['title'],
                                   "Entry-level": "?", "H1B bahsi": "?", "Durum": "❌ Erişilemedi"})
                time.sleep(2)
            else:
                results.append({"Şirket": row['company'], "Pozisyon": row['title'],
                               "Entry-level": "?", "H1B bahsi": "?", "Durum": "⚠️ URL yok"})
        progress.progress(1.0)
        st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)


# ==========================================
#  GÜNLÜK RAPOR
# ==========================================
elif page == "📅 Günlük Rapor":
    st.title("📅 Günlük Rapor & Otomatik Arama")

    # Show last report if exists
    report_file = BASE_DIR / "daily_report.html"
    if report_file.exists():
        st.subheader("Son Rapor")
        report_time = datetime.fromtimestamp(report_file.stat().st_mtime)
        st.caption(f"Son güncelleme: {report_time.strftime('%Y-%m-%d %H:%M')}")
        with open(report_file, 'r') as f:
            st.components.v1.html(f.read(), height=600, scrolling=True)

    st.divider()

    # Manual trigger
    st.subheader("Manuel Arama")
    if st.button("🔄 Şimdi Yeni İş Ara", type="primary", use_container_width=True):
        with st.spinner("GitHub repo'ları taranıyor..."):
            import subprocess
            result = subprocess.run(
                ['python3', str(BASE_DIR / 'daily_digest.py')],
                capture_output=True, text=True, timeout=60, cwd=str(BASE_DIR)
            )
            if result.returncode == 0:
                st.success("✅ Arama tamamlandı!")
                st.text(result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout)
                load_jobs.clear()
                st.rerun()
            else:
                st.error(f"Hata: {result.stderr[-500:]}")

    # Cron setup instructions
    st.divider()
    st.subheader("⏰ Otomatik Günlük Arama Kurulumu")

    plist_file = BASE_DIR / "com.ela.jobhunter.daily.plist"
    installed = Path("~/Library/LaunchAgents/com.ela.jobhunter.daily.plist").expanduser().exists()

    if installed:
        st.success("✅ Günlük otomatik arama aktif! (Her gün 09:00)")
        if st.button("❌ Otomatik Aramayı Kapat"):
            import subprocess
            subprocess.run(['launchctl', 'unload', str(Path("~/Library/LaunchAgents/com.ela.jobhunter.daily.plist").expanduser())])
            Path("~/Library/LaunchAgents/com.ela.jobhunter.daily.plist").expanduser().unlink(missing_ok=True)
            st.success("Otomatik arama kapatıldı.")
            st.rerun()
    else:
        st.warning("Günlük otomatik arama henüz kurulmamış.")
        if plist_file.exists():
            if st.button("✅ Otomatik Aramayı Kur (Her gün 09:00)", type="primary"):
                import shutil, subprocess
                target = Path("~/Library/LaunchAgents/com.ela.jobhunter.daily.plist").expanduser()
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plist_file, target)
                subprocess.run(['launchctl', 'load', str(target)])
                st.success("✅ Günlük otomatik arama kuruldu! Her gün 09:00'da çalışacak.")
                st.rerun()
        else:
            st.info("Plist dosyası bulunamadı. Terminal'de `python3 daily_digest.py` ile test et.")
