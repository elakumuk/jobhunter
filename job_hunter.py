#!/usr/bin/env python3
"""
JobHunter - Ela's AI-Powered Job Search System
===============================================
Finds matching jobs, tailors resumes, writes AI cover letters,
analyzes job descriptions, prepares for interviews, and finds hiring managers.

Usage:
    python3 job_hunter.py search              # Search for new jobs
    python3 job_hunter.py dashboard           # View application tracker
    python3 job_hunter.py analytics           # Detailed progress & analytics
    python3 job_hunter.py apply <job_id>      # AI cover letter + resume tips + LinkedIn
    python3 job_hunter.py interview <job_id>  # AI interview prep questions
    python3 job_hunter.py analyze <job_id>    # AI job description analysis
    python3 job_hunter.py linkedin <job_id>   # Find hiring managers + AI outreach
    python3 job_hunter.py ai <question>       # Ask AI anything about job search
"""

import json
import csv
import os
import sys
import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# --- GEMINI AI ---
_gemini_client = None

def get_gemini():
    """Initialize Gemini AI client (new SDK)."""
    global _gemini_client
    if _gemini_client:
        return _gemini_client
    try:
        from google import genai
        config = load_config()
        api_key = config.get('gemini_api_key', '')
        if not api_key:
            print("⚠️  Gemini API key not found in config.json")
            return None
        _gemini_client = genai.Client(api_key=api_key)
        return _gemini_client
    except ImportError:
        print("⚠️  google-genai not installed. Run: pip3 install google-genai")
        return None
    except Exception as e:
        print(f"⚠️  Gemini error: {e}")
        return None

def ai_generate(prompt, fallback="AI kullanılamadı."):
    """Send prompt to Gemini with retry logic for rate limits."""
    import time
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
            error_str = str(e)
            if '429' in error_str and attempt < 2:
                wait = (attempt + 1) * 10
                print(f"  ⏳ Rate limit, {wait}s bekleniyor... (deneme {attempt+2}/3)")
                time.sleep(wait)
            else:
                print(f"  ⚠️  Gemini API error: {e}")
                return fallback
    return fallback

ELA_PROFILE = """
Candidate Profile:
- Name: Ela Kumuk
- Education: M.S. Business Analytics (MSBA), Brandeis University, graduating December 2026
- Undergrad: Double major in Business & Psychology, Minor in Studio Art
- Technical Skills: Python, R, SQL, Tableau, Excel, MySQL, Jupyter Notebook, Google Colab
- Analytics: Statistical Analysis, Econometrics, Regression, Hypothesis Testing, A/B Testing, Marketing Analytics, Data Visualization
- Coursework: Python for Business Analytics, Econometrics with R, Marketing Analytics, Information Visualization, Intro to Data Analytics
- Unique strengths: Consumer Psychology background, E-commerce experience (family business), Brand Strategy, bilingual (Turkish/English)
- Visa: F1 Student (OPT eligible, needs H1B sponsorship)
- Location: Waltham, MA (open to relocation)
- Contact: elakumuk@icloud.com, linkedin.com/in/elakumuk
"""

# --- CONFIG ---
BASE_DIR = Path(__file__).parent
JOBS_FILE = BASE_DIR / "jobs_tracker.csv"
RESUME_BASE = BASE_DIR / "base_resume.json"
OUTPUT_DIR = BASE_DIR / "applications"
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_CONFIG = {
    "name": "Ela Kumuk",
    "email": "elakumuk@icloud.com",
    "phone": "[YOUR PHONE]",
    "linkedin": "linkedin.com/in/elakumuk",
    "location": "Waltham, MA",
    "university": "Brandeis University",
    "degree": "M.S. Business Analytics (MSBA)",
    "graduation": "December 2026",
    "target_roles": [
        "Data Analyst",
        "Business Analyst",
        "Marketing Analyst",
        "Business Intelligence Analyst",
        "Analytics Associate",
        "Quantitative Analyst",
        "Research Analyst",
        "Strategy Analyst",
        "Operations Analyst",
        "Product Analyst"
    ],
    "target_companies": [
        "PwC", "Fidelity", "Amazon", "Google", "Meta", "Apple", "Intel",
        "Tata Consultancy Services", "Amazon Web Services", "Bank of America",
        "EY", "Deloitte", "IBM", "Microsoft", "Walmart", "JPMorgan Chase",
        "Boston Consulting Group", "Oracle", "Citibank", "Goldman Sachs",
        "American Express", "Morgan Stanley", "Mphasis", "Bloomberg", "McKinsey",
        "KPMG", "Accenture", "Bain", "Capital One", "Wayfair", "HubSpot",
        "Spotify", "Airbnb", "Netflix", "Salesforce", "Adobe", "Uber", "Lyft",
        "DoorDash", "Stripe", "Databricks", "Snowflake", "Palantir"
    ],
    "skills": {
        "programming": ["Python", "R", "SQL"],
        "tools": ["Tableau", "Excel", "Jupyter Notebook", "Google Colab", "VS Code"],
        "analytics": ["Statistical Analysis", "Data Visualization", "Econometrics",
                      "Regression Analysis", "Hypothesis Testing", "A/B Testing",
                      "Marketing Analytics", "Business Intelligence"],
        "databases": ["MySQL"],
        "other": ["Consumer Psychology", "E-commerce", "Brand Strategy"]
    }
}

# --- CSV TRACKER ---
CSV_HEADERS = [
    "job_id", "company", "title", "location", "url", "date_found",
    "status", "date_applied", "contact_name", "contact_linkedin",
    "contact_email", "notes", "match_score", "h1b_sponsor"
]

def init_tracker():
    if not JOBS_FILE.exists():
        with open(JOBS_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        print(f"Created job tracker: {JOBS_FILE}")

def load_jobs():
    if not JOBS_FILE.exists():
        return []
    with open(JOBS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)

def save_job(job):
    existing = load_jobs()
    # Check for duplicates
    for j in existing:
        if j.get('url') == job.get('url') or (
            j.get('company') == job.get('company') and j.get('title') == job.get('title')
        ):
            return False
    with open(JOBS_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(job)
    return True

def update_job_status(job_id, status, notes=""):
    jobs = load_jobs()
    updated = False
    for j in jobs:
        if j['job_id'] == job_id:
            j['status'] = status
            if notes:
                j['notes'] = notes
            if status == "applied":
                j['date_applied'] = datetime.now().strftime('%Y-%m-%d')
            updated = True
    if updated:
        with open(JOBS_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(jobs)
    return updated

# --- JOB SEARCH ---
def calculate_match_score(title, company, description=""):
    """Score 0-100 how well a job matches Ela's profile."""
    score = 0
    config = load_config()
    title_lower = title.lower()
    desc_lower = description.lower()

    # Title match
    for role in config['target_roles']:
        if role.lower() in title_lower:
            score += 40
            break

    # Keyword matches in title
    keywords = ['data', 'analytics', 'analyst', 'business', 'intelligence',
                'marketing', 'quantitative', 'insights', 'strategy']
    for kw in keywords:
        if kw in title_lower:
            score += 5

    # Company match
    for comp in config['target_companies']:
        if comp.lower() in company.lower():
            score += 20
            break

    # Entry level / new grad indicators
    entry_keywords = ['entry', 'junior', 'associate', 'new grad', 'early career',
                      'graduate', 'rotational', 'analyst i', 'level 1']
    for kw in entry_keywords:
        if kw in title_lower or kw in desc_lower:
            score += 10
            break

    # Skill matches in description
    if description:
        skill_keywords = ['python', 'r ', 'sql', 'tableau', 'excel',
                         'statistics', 'econometrics', 'visualization']
        for sk in skill_keywords:
            if sk in desc_lower:
                score += 3

    return min(score, 100)

def search_jobs_github():
    """Fetch jobs from GitHub new-grad repos."""
    import urllib.request

    urls = [
        "https://raw.githubusercontent.com/jobright-ai/2026-Data-Analysis-New-Grad/master/README.md",
        "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/master/README.md",
    ]

    jobs_found = []
    config = load_config()

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode('utf-8')

            # Parse markdown table rows
            lines = content.split('\n')
            for line in lines:
                if '|' not in line or line.startswith('|--') or line.startswith('| Company'):
                    continue

                cols = [c.strip() for c in line.split('|') if c.strip()]
                if len(cols) < 3:
                    continue

                company = re.sub(r'\[([^\]]+)\].*', r'\1', cols[0]).strip()
                company = re.sub(r'\*+', '', company).strip()
                title = re.sub(r'\[([^\]]+)\].*', r'\1', cols[1]).strip() if len(cols) > 1 else ""
                title = re.sub(r'\*+', '', title).strip()
                location = re.sub(r'\*+', '', cols[2]).strip() if len(cols) > 2 else ""

                # Extract URL if present
                url_match = re.search(r'\((https?://[^\)]+)\)', line)
                job_url = url_match.group(1) if url_match else ""

                # Check relevance
                match_score = calculate_match_score(title, company)
                if match_score < 20:
                    continue

                job = {
                    'job_id': f"GH-{len(jobs_found)+1:04d}",
                    'company': company,
                    'title': title,
                    'location': location,
                    'url': job_url,
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'new',
                    'date_applied': '',
                    'contact_name': '',
                    'contact_linkedin': '',
                    'contact_email': '',
                    'notes': '',
                    'match_score': str(match_score),
                    'h1b_sponsor': 'check'
                }
                jobs_found.append(job)

        except Exception as e:
            print(f"  Warning: Could not fetch {url}: {e}")

    return jobs_found

def search_jobs_web():
    """Generate search URLs for manual browsing."""
    config = load_config()
    role_query = " OR ".join([f'"{r}"' for r in config['target_roles'][:5]])

    searches = {
        "LinkedIn": f"https://www.linkedin.com/jobs/search/?keywords=data%20analyst%20entry%20level&location=United%20States&f_E=2&f_TPR=r604800",
        "Indeed - Data Analyst Boston": "https://www.indeed.com/jobs?q=entry+level+data+analyst&l=Boston%2C+MA&fromage=7",
        "Indeed - Business Analyst H1B": "https://www.indeed.com/q-h1b-visa-sponsorship-data-analyst-jobs.html",
        "Glassdoor - Entry Level DA Boston": "https://www.glassdoor.com/Job/boston-entry-level-data-analyst-jobs-SRCH_IL.0,6_IC1154532_KO7,31.htm",
        "Glassdoor - Marketing Analyst": "https://www.glassdoor.com/Job/boston-marketing-analyst-jobs-SRCH_IL.0,6_IC1154532_KO7,24.htm",
        "GitHub - 2026 New Grad Data": "https://github.com/jobright-ai/2026-Data-Analysis-New-Grad",
        "GitHub - SimplifyJobs New Grad": "https://github.com/SimplifyJobs/New-Grad-Positions",
        "NewGrad-Jobs.com": "https://www.newgrad-jobs.com",
        "H1BGrader - Check Sponsors": "https://h1bgrader.com/job-titles/data-analyst-x30q6dpz2q",
    }

    # Company career pages
    career_pages = {
        "PwC": "https://jobs.us.pwc.com/entry-level-data-and-technology",
        "Deloitte": "https://apply.deloitte.com/careers/SearchJobs/?524=2966&524_format=1482&listFilterMode=1",
        "EY": "https://careers.ey.com/ey/search/?q=data+analyst&startrow=1",
        "KPMG": "https://www.kpmguscareers.com/early-career/",
        "Goldman Sachs": "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/new-analyst-program",
        "JPMorgan": "https://careers.jpmorgan.com/us/en/students/programs",
        "Amazon": "https://www.amazon.jobs/en/search?base_query=data+analyst&loc_query=&latitude=&longitude=&loc_group_id=&invalid_location=false&country=USA&city=&region=&county=",
        "Google": "https://www.google.com/about/careers/applications/jobs/results?q=data%20analyst&employment_type=FULL_TIME&target_level=EARLY",
        "Meta": "https://www.metacareers.com/jobs?q=data%20analyst&is_leadership=0&teams[0]=Internship%20-%20Emerging%20Talent",
        "Microsoft": "https://careers.microsoft.com/v2/global/en/search?q=data%20analyst&lc=United%20States&el=3",
    }

    return searches, career_pages

# --- AI COVER LETTER GENERATOR ---
def generate_cover_letter(job, resume_data=None):
    """Generate an AI-tailored cover letter using Gemini."""
    config = load_config()
    company = job.get('company', '[Company]')
    title = job.get('title', '[Position]')
    location = job.get('location', '')

    prompt = f"""Write a professional, compelling cover letter for this job application.
Keep it to 4 paragraphs, under 400 words. Be specific, not generic. Sound confident but not arrogant.
Do NOT use cliches like "I am writing to express my interest" or "I am excited about the opportunity".
Start with something engaging and specific to the company/role.

{ELA_PROFILE}

Job Details:
- Company: {company}
- Position: {title}
- Location: {location}

Format the letter with:
- Header: Ela Kumuk | Waltham, MA | {config['email']} | {datetime.now().strftime('%B %d, %Y')}
- "Dear Hiring Manager,"
- 4 paragraphs (opening hook, skills/coursework match, unique value from psych+business combo, closing with call to action)
- "Sincerely, Ela Kumuk"

Important:
- Highlight the Psychology + Business + Analytics combination as a unique differentiator
- Mention specific relevant coursework
- If it's a finance company, emphasize quantitative skills
- If it's a tech company, emphasize Python/SQL/data engineering
- If it's consulting, emphasize client communication and business acumen
- Keep it genuine and personal, not template-like
"""

    ai_letter = ai_generate(prompt)
    if ai_letter and "AI kullanılamadı" not in ai_letter:
        return ai_letter

    # Fallback to template
    return _template_cover_letter(job, config)

def _template_cover_letter(job, config):
    """Fallback template cover letter if AI is unavailable."""
    company = job.get('company', '[Company]')
    title = job.get('title', '[Position]')
    return f"""{config['name']}
{config['location']} | {config['email']}
{datetime.now().strftime('%B %d, %Y')}

Dear Hiring Manager,

I am writing to express my interest in the {title} position at {company}. I am completing my M.S. in Business Analytics at Brandeis University (December 2026), with a background in Business and Psychology.

My coursework in Python, Econometrics with R, Marketing Analytics, and Data Visualization has prepared me with strong technical skills. I am proficient in Python, R, SQL, and Tableau.

What sets me apart is my combination of quantitative analytics training with a deep understanding of consumer behavior from my Psychology background. This allows me to not just analyze data, but understand the human story behind it.

I would welcome the chance to discuss how my skills align with your needs. Thank you for your consideration.

Sincerely,
{config['name']}
"""

# --- LINKEDIN HIRING MANAGER FINDER ---
def get_linkedin_search(job):
    """Generate LinkedIn search URLs to find hiring managers."""
    company = job.get('company', '')
    title = job.get('title', '')

    searches = []

    # Hiring manager search
    manager_titles = [
        "Head of Analytics",
        "Director of Analytics",
        "Analytics Manager",
        "Data Science Manager",
        "Hiring Manager",
        "VP Analytics",
        "Director Business Intelligence",
        "Head of Data",
        "Talent Acquisition",
        "University Recruiter"
    ]

    for mt in manager_titles:
        query = urllib.parse.quote(f"{mt} {company}")
        url = f"https://www.linkedin.com/search/results/people/?keywords={query}&origin=GLOBAL_SEARCH_HEADER"
        searches.append((mt, url))

    # Recruiter search
    recruiter_query = urllib.parse.quote(f"recruiter {company} data analytics")
    searches.append(("Recruiter - Data Analytics",
                     f"https://www.linkedin.com/search/results/people/?keywords={recruiter_query}&origin=GLOBAL_SEARCH_HEADER"))

    # Brandeis alumni at company
    alumni_query = urllib.parse.quote(f"Brandeis {company}")
    searches.append(("Brandeis Alumni",
                     f"https://www.linkedin.com/search/results/people/?keywords={alumni_query}&school=Brandeis%20University&origin=GLOBAL_SEARCH_HEADER"))

    return searches

def generate_cold_message(job, contact_name="[Name]"):
    """Generate cold outreach message for LinkedIn/email."""
    config = load_config()
    company = job.get('company', '[Company]')
    title = job.get('title', '[Position]')

    linkedin_msg = f"""Hi {contact_name},

I'm Ela, an MSBA candidate at Brandeis graduating in {config['graduation']}. I'm very interested in the {title} role at {company} and would love to learn more about the team and the work you're doing in analytics.

Would you be open to a brief chat? I'd really appreciate any insights you could share.

Thank you!
Ela"""

    email_msg = f"""Subject: Brandeis MSBA Student - Interest in {title} at {company}

Dear {contact_name},

I hope this message finds you well. My name is Ela Kumuk, and I am currently pursuing my Master of Science in Business Analytics at Brandeis University, graduating in {config['graduation']}.

I recently came across the {title} position at {company} and was immediately drawn to the opportunity. My background in data analytics (Python, R, SQL, Tableau) combined with my undergraduate studies in Business and Psychology has prepared me to contribute meaningfully to your team.

I would greatly appreciate the opportunity to connect and learn more about {company}'s analytics team and any advice you might have for an aspiring analyst.

Thank you for your time and consideration.

Best regards,
Ela Kumuk
{config['email']}
Brandeis University, MSBA '26"""

    return linkedin_msg, email_msg

# --- CONFIG ---
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

# --- AI JOB ANALYSIS ---
def ai_analyze_job(job):
    """AI-powered deep analysis of a job posting."""
    company = job.get('company', '')
    title = job.get('title', '')
    location = job.get('location', '')

    prompt = f"""Analyze this job posting for a candidate applying from the perspective below.
Be specific and actionable. Write in a mix of Turkish and English (technical terms in English).

{ELA_PROFILE}

Job:
- Company: {company}
- Position: {title}
- Location: {location}

Provide analysis in this format:

## 🏢 ŞİRKET ANALİZİ
- Şirketin ne yaptığı, sektörü, büyüklüğü
- Kültürü ve değerleri
- Veri/analytics'e bakış açısı

## 🎯 POZİSYON UYUM ANALİZİ
- Bu pozisyon Ela'nın profiline ne kadar uyuyor (1-10 puan)
- Güçlü yanlar: Ela'nın bu iş için avantajları
- Zayıf yanlar: Eksik olabilecek beceriler
- H1B sponsorship ihtimali

## 📋 MUHTEMEL GÖREVLER
- Bu pozisyonda günlük yapılacak işler
- Kullanılacak araçlar ve teknolojiler

## 💡 BAŞVURU STRATEJİSİ
- Resume'de öne çıkarılması gerekenler
- Cover letter'da vurgulanması gerekenler
- LinkedIn'de yapılması gerekenler

## ⚠️ DİKKAT EDİLMESİ GEREKENLER
- Red flags (varsa)
- Rekabet seviyesi tahmini
"""
    return ai_generate(prompt, "AI analizi yapılamadı.")


# --- AI INTERVIEW PREP ---
def ai_interview_prep(job):
    """AI-powered interview preparation."""
    company = job.get('company', '')
    title = job.get('title', '')

    prompt = f"""Prepare comprehensive interview questions and answers for this candidate and job.
Write in a mix of Turkish and English. Be specific to the company and role.

{ELA_PROFILE}

Job:
- Company: {company}
- Position: {title}

Provide:

## 🎤 TEKNİK SORULAR (8 soru)
For each: Question, then a strong answer Ela should give (using her actual background)
Include: SQL queries, Python scenarios, statistics concepts, data visualization, A/B testing

## 💼 BEHAVIORAL SORULAR (6 soru - STAR format)
For each: Question, then a STAR-format answer Ela can adapt
Focus on: teamwork, problem-solving, handling ambiguity, leadership

## 🏢 ŞİRKETE ÖZEL SORULAR (4 soru)
Questions specific to {company}'s business, culture, recent news

## ❓ ELA'NIN SORMASI GEREKEN SORULAR (5 soru)
Smart questions that show genuine interest and preparation

## 💡 MÜLAKAT İPUÇLARI
- {company} mülakatlarında dikkat edilmesi gerekenler
- Dress code, format (virtual/in-person), typical process
- Common pitfalls to avoid
"""
    return ai_generate(prompt, "AI mülakat hazırlığı yapılamadı.")


# --- AI OUTREACH ---
def ai_cold_outreach(job, contact_name="[Name]", contact_title=""):
    """AI-powered personalized cold outreach messages."""
    company = job.get('company', '')
    title = job.get('title', '')

    prompt = f"""Write personalized cold outreach messages for networking about this job.
Sound natural, not robotic. Keep LinkedIn message under 300 chars. Keep email concise.

{ELA_PROFILE}

Job: {title} at {company}
Contact: {contact_name}, {contact_title}

Write:

1. **LinkedIn Connection Request** (max 300 characters - this is a HARD limit)
   - Personal, warm, specific reason for connecting

2. **LinkedIn Follow-up Message** (after they accept, ~100 words)
   - Reference the role, ask for a quick chat, mention Brandeis

3. **Cold Email** (~150 words)
   - Subject line + body
   - Professional but warm
   - Specific ask (15-min chat, advice, referral)

4. **Thank You Message** (after a call/chat, ~80 words)
   - Reference something specific from the conversation
   - Reiterate interest
"""
    return ai_generate(prompt, "AI outreach mesajları oluşturulamadı.")


# --- AI RESUME TAILORING ---
def tailor_resume_bullets(job):
    """AI-powered resume tailoring suggestions."""
    company = job.get('company', '')
    title = job.get('title', '')

    prompt = f"""Give specific resume tailoring advice for this job application.
Be very actionable — tell exactly what to change, add, or reorder.

{ELA_PROFILE}

Job: {title} at {company}

Provide in this format:

## RESUME'DE ÖNE ÇIKARILMASI GEREKENLER
- List 5 specific bullet points to highlight or move to the top

## EKLENECEK ANAHTAR KELİMELER
- List 8-10 keywords from this industry/role to weave into the resume

## SKILLS SIRALAMASINI DEĞİŞTİR
- What order should skills appear for this specific role

## ÖZEL BULLET POINT ÖNERİLERİ
- Write 3 new resume bullet points Ela could add, using her actual background
- Use action verbs, include metrics where possible (even estimates)
- Example format: "Analyzed X using Y, resulting in Z"

## ÇIKARILMASI GEREKENLER
- What's less relevant for this role and can be de-emphasized
"""

    ai_tips = ai_generate(prompt, None)
    if ai_tips:
        return {'ai_tips': ai_tips}

    # Fallback to basic logic
    title_lower = title.lower()
    emphasis = {'highlight': [], 'add_keywords': [], 'reorder_skills': []}

    if 'marketing' in title_lower:
        emphasis['highlight'] = ["Marketing Analytics coursework", "Consumer Psychology background", "A/B Testing", "Data Visualization"]
        emphasis['add_keywords'] = ["marketing mix", "customer segmentation", "campaign analysis", "ROI"]
    elif 'data' in title_lower:
        emphasis['highlight'] = ["Python & R programming", "Econometrics coursework", "SQL & database", "Statistical modeling"]
        emphasis['add_keywords'] = ["ETL", "data pipeline", "statistical modeling", "dashboards"]
    elif 'business' in title_lower:
        emphasis['highlight'] = ["Business Analytics coursework", "Double major Business & Psychology", "E-commerce experience", "Excel & Tableau"]
        emphasis['add_keywords'] = ["stakeholder communication", "KPIs", "business intelligence", "process improvement"]
    else:
        emphasis['highlight'] = ["MSBA at Brandeis", "Python, R, SQL", "Business & Psychology", "Tableau"]

    return emphasis

# --- ANALYTICS ---
def cmd_analytics():
    """Detailed analytics on job search progress."""
    jobs = load_jobs()
    if not jobs:
        print("No jobs tracked yet. Run: python3 job_hunter.py search")
        return

    print("\n" + "=" * 60)
    print("  JOBHUNTER ANALİZ RAPORU")
    print("=" * 60)

    # 1. Status breakdown
    statuses = {}
    for j in jobs:
        s = j.get('status', 'unknown')
        statuses[s] = statuses.get(s, 0) + 1

    total = len(jobs)
    print(f"\n📊 DURUM ÖZETİ ({total} toplam iş)")
    print("-" * 40)

    status_labels = {
        'new': 'Yeni (İncelenmemiş)',
        'preparing': 'Hazırlanıyor',
        'applied': 'Başvuru Yapıldı',
        'interview': 'Mülakat Aşaması',
        'offer': 'Teklif Alındı!',
        'rejected': 'Reddedildi',
        'saved': 'Kaydedildi',
        'skipped': 'Atlandı'
    }

    status_icons = {
        'new': '🆕', 'preparing': '📝', 'applied': '📨',
        'interview': '🎤', 'offer': '🎉', 'rejected': '❌',
        'saved': '💾', 'skipped': '⏭️'
    }

    for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
        icon = status_icons.get(status, '•')
        label = status_labels.get(status, status)
        pct = (count / total) * 100
        bar = '█' * int(pct / 2) + '░' * (50 - int(pct / 2))
        print(f"  {icon} {label:<25} {count:>4}  ({pct:5.1f}%)  {bar}")

    # 2. Pipeline funnel
    applied = statuses.get('applied', 0) + statuses.get('interview', 0) + statuses.get('offer', 0) + statuses.get('rejected', 0)
    interviews = statuses.get('interview', 0) + statuses.get('offer', 0)
    offers = statuses.get('offer', 0)
    rejected = statuses.get('rejected', 0)

    print(f"\n📈 BAŞVURU PİPELINE")
    print("-" * 40)
    print(f"  Toplam İş          → {total}")
    print(f"  Başvuru Yapılan     → {applied}")
    if applied > 0:
        print(f"  Mülakat Daveti      → {interviews}  ({interviews/applied*100:.0f}% response rate)")
        print(f"  Teklif              → {offers}  ({offers/applied*100:.0f}% offer rate)")
        print(f"  Red                 → {rejected}  ({rejected/applied*100:.0f}% rejection rate)")
        pending = applied - interviews - rejected
        if pending > 0:
            print(f"  Cevap Bekleyen      → {pending}")
    else:
        print("  ⚠️  Henüz başvuru yapılmamış!")

    # 3. Match score distribution
    scores = [int(j.get('match_score', 0)) for j in jobs]
    high = sum(1 for s in scores if s >= 60)
    mid = sum(1 for s in scores if 40 <= s < 60)
    low = sum(1 for s in scores if s < 40)

    print(f"\n🎯 MATCH SCORE DAĞILIMI")
    print("-" * 40)
    print(f"  Yüksek (60-100)    → {high:>3} iş  {'🟢' * min(high, 30)}")
    print(f"  Orta (40-59)       → {mid:>3} iş  {'🟡' * min(mid, 30)}")
    print(f"  Düşük (0-39)       → {low:>3} iş  {'🔴' * min(low, 30)}")
    avg_score = sum(scores) / len(scores) if scores else 0
    print(f"  Ortalama Score     → {avg_score:.1f}")

    # 4. Location analysis
    locations = {}
    for j in jobs:
        loc = j.get('location', 'Unknown').strip()
        # Simplify location
        if 'remote' in loc.lower():
            loc_key = 'Remote'
        elif 'MA' in loc or 'Boston' in loc or 'Cambridge' in loc or 'Waltham' in loc:
            loc_key = 'Massachusetts'
        elif 'NY' in loc or 'New York' in loc:
            loc_key = 'New York'
        elif 'CA' in loc or 'San Francisco' in loc or 'San Bruno' in loc:
            loc_key = 'California'
        elif 'TX' in loc:
            loc_key = 'Texas'
        elif 'IL' in loc or 'Chicago' in loc:
            loc_key = 'Illinois'
        elif 'Canada' in loc:
            loc_key = 'Canada'
        else:
            loc_key = 'Diğer ABD'
        locations[loc_key] = locations.get(loc_key, 0) + 1

    print(f"\n📍 LOKASYON DAĞILIMI")
    print("-" * 40)
    for loc, count in sorted(locations.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total) * 100
        print(f"  {loc:<25} {count:>3}  ({pct:.0f}%)")

    # 5. Company tier analysis
    config = load_config()
    target_companies = [c.lower() for c in config.get('target_companies', [])]
    target_count = 0
    for j in jobs:
        for tc in target_companies:
            if tc in j.get('company', '').lower():
                target_count += 1
                break

    print(f"\n🏢 ŞİRKET ANALİZİ")
    print("-" * 40)
    print(f"  Hedef listedeki şirketler  → {target_count}/{total}")
    print(f"  Diğer şirketler            → {total - target_count}/{total}")

    # 6. Top 10 recommendations (highest score, still new)
    new_jobs = [j for j in jobs if j.get('status') == 'new']
    top_new = sorted(new_jobs, key=lambda x: int(x.get('match_score', 0)), reverse=True)[:10]

    if top_new:
        print(f"\n⭐ ÖNCELİKLİ BAŞVURU ÖNERİLERİ (En yüksek score, henüz başvurulmamış)")
        print("-" * 80)
        print(f"  {'ID':<10} {'Şirket':<25} {'Pozisyon':<30} {'Score':<6}")
        print("  " + "-" * 75)
        for j in top_new:
            print(f"  {j['job_id']:<10} {j['company'][:24]:<25} {j['title'][:29]:<30} {j.get('match_score','?'):<6}")

    # 7. Weekly activity
    from collections import defaultdict
    weekly = defaultdict(int)
    for j in jobs:
        date_str = j.get('date_applied') or j.get('date_found', '')
        if date_str:
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
                week = d.strftime('%Y-W%U')
                weekly[week] += 1
            except ValueError:
                pass

    if weekly:
        print(f"\n📅 HAFTALIK AKTİVİTE")
        print("-" * 40)
        for week, count in sorted(weekly.items()):
            bar = '█' * count
            print(f"  {week}  {count:>3} iş  {bar}")

    # 8. Action items
    print(f"\n💡 YAPILMASI GEREKENLER")
    print("-" * 40)
    new_count = statuses.get('new', 0)
    prep_count = statuses.get('preparing', 0)
    if new_count > 0:
        print(f"  → {new_count} yeni iş incelenmeli")
    if prep_count > 0:
        print(f"  → {prep_count} iş başvuru için hazırlanıyor, tamamlayın")
    if applied == 0:
        print(f"  → Hiç başvuru yapılmamış! En yüksek score'lu işlere başvurun")
        print(f"    Komut: python3 job_hunter.py apply <job_id>")
    if high > 0:
        print(f"  → {high} yüksek eşleşmeli iş var, öncelik verin")
    print(f"\n{'=' * 60}\n")


# --- SMART FILTER ---
def cmd_smart_filter():
    """AI-powered smart filtering: skip irrelevant jobs, keep the best."""
    jobs = load_jobs()
    new_jobs = [j for j in jobs if j.get('status') == 'new']

    if not new_jobs:
        print("Filtrelenecek yeni iş yok.")
        return

    print(f"\n{'='*60}")
    print(f"  🧹 SMART FILTER — {len(new_jobs)} yeni iş analiz ediliyor")
    print(f"{'='*60}\n")

    skipped = 0
    kept = 0

    # Auto-skip rules (no AI needed — instant)
    skip_keywords_title = [
        'clearance', 'secret', 'ts/sci', 'security clearance',
        'principal', 'staff', 'senior', 'lead', 'director', 'manager',
        'phd required', 'phd degree required',
        'nurse', 'nursing', 'clinical', 'physician', 'medical director',
        'bilingual spanish', 'bilingual french', 'hebrew',
    ]
    skip_keywords_location = [
        'canada', 'united kingdom', 'uk', 'india', 'germany', 'australia',
        'singapore', 'japan', 'brazil', 'mexico', 'ireland',
    ]

    for job in new_jobs:
        title_lower = job.get('title', '').lower()
        loc_lower = job.get('location', '').lower()
        company = job.get('company', '')
        score = int(job.get('match_score', 0))
        skip_reason = None

        # Rule 1: Clearance/senior/irrelevant titles
        for kw in skip_keywords_title:
            if kw in title_lower:
                skip_reason = f"Title: '{kw}'"
                break

        # Rule 2: International locations (Ela needs US/OPT)
        if not skip_reason:
            for kw in skip_keywords_location:
                if kw in loc_lower and 'remote' not in loc_lower:
                    skip_reason = f"Location: '{job.get('location', '')}'"
                    break

        # Rule 3: Very low match score
        if not skip_reason and score < 25:
            skip_reason = f"Low score: {score}"

        # Rule 4: Company is just an arrow (duplicate/sub-listing)
        if not skip_reason and company.strip() in ['↳', '']:
            skip_reason = "Sub-listing (↳)"

        if skip_reason:
            update_job_status(job['job_id'], 'skipped', f"Auto-filtered: {skip_reason}")
            print(f"  ⏭️  {job['job_id']:<10} {company[:20]:<22} → Atlandı ({skip_reason})")
            skipped += 1
        else:
            kept += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  📊 SONUÇ:")
    print(f"     Atlandı:  {skipped} iş")
    print(f"     Kaldı:    {kept} iş")
    print(f"{'='*60}")

    # Show remaining top jobs
    remaining = load_jobs()
    active = [j for j in remaining if j.get('status') in ('new', 'preparing')]
    top = sorted(active, key=lambda x: int(x.get('match_score', 0)), reverse=True)[:15]

    if top:
        print(f"\n  ⭐ EN İYİ KALAN İŞLER:")
        print(f"  {'ID':<10} {'Şirket':<22} {'Pozisyon':<32} {'Skor':<6} {'Lokasyon'}")
        print(f"  {'-'*85}")
        for j in top:
            print(f"  {j['job_id']:<10} {j['company'][:21]:<22} {j['title'][:31]:<32} {j.get('match_score','?'):<6} {j.get('location','')[:20]}")

    print(f"\n  💡 Toplu başvuru için: python3 job_hunter.py batch")
    print(f"  💡 Tek başvuru için:  python3 job_hunter.py apply <job_id>\n")


# --- BATCH APPLY ---
def cmd_batch(count=10):
    """Generate AI application materials for top N jobs at once."""
    import time

    jobs = load_jobs()
    new_jobs = [j for j in jobs if j.get('status') == 'new']

    if not new_jobs:
        print("Başvurulacak yeni iş yok. Önce: python3 job_hunter.py search")
        return

    # Sort by score, take top N
    top_jobs = sorted(new_jobs, key=lambda x: int(x.get('match_score', 0)), reverse=True)[:count]

    print(f"\n{'='*60}")
    print(f"  🚀 TOPLU AI BAŞVURU — En iyi {len(top_jobs)} iş")
    print(f"{'='*60}\n")

    print(f"  Şu işler için başvuru paketi hazırlanacak:\n")
    for i, j in enumerate(top_jobs, 1):
        print(f"  {i:>2}. [{j['job_id']}] {j['company'][:20]} — {j['title'][:35]} (Skor: {j.get('match_score','?')})")
    print()

    success = 0
    failed = 0

    for i, job in enumerate(top_jobs, 1):
        company = job['company']
        title = job['title']
        job_id = job['job_id']

        print(f"\n{'─'*60}")
        print(f"  [{i}/{len(top_jobs)}] {title} @ {company}")
        print(f"{'─'*60}")

        safe_name = re.sub(r'[^\w\-]', '_', f"{company}_{title}")
        out_dir = OUTPUT_DIR / safe_name
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Cover Letter (AI)
            print("  📝 Cover letter...")
            cover = generate_cover_letter(job)
            with open(out_dir / "cover_letter.txt", 'w') as f:
                f.write(cover)
            time.sleep(2)  # Rate limit protection

            # Resume Tips (AI)
            print("  📋 Resume tips...")
            tips = tailor_resume_bullets(job)
            with open(out_dir / "resume_tips.txt", 'w') as f:
                f.write(f"Resume Tips: {title} at {company}\n{'='*60}\n\n")
                if 'ai_tips' in tips:
                    f.write(tips['ai_tips'])
                else:
                    for k, v in tips.items():
                        if isinstance(v, list) and v:
                            f.write(f"\n{k.upper()}:\n")
                            for item in v:
                                f.write(f"  - {item}\n")
            time.sleep(2)

            # Outreach (AI)
            print("  💬 Outreach mesajları...")
            outreach = ai_cold_outreach(job)
            with open(out_dir / "outreach_messages.txt", 'w') as f:
                f.write(outreach)
            time.sleep(2)

            # LinkedIn searches (no AI needed)
            searches = get_linkedin_search(job)
            with open(out_dir / "linkedin_contacts.txt", 'w') as f:
                f.write(f"LinkedIn Searches: {company}\n{'='*60}\n\n")
                for st, url in searches:
                    f.write(f"{st}:\n  {url}\n\n")

            update_job_status(job_id, "preparing")
            print(f"  ✅ Tamamlandı! → {out_dir}")
            success += 1

        except Exception as e:
            print(f"  ❌ Hata: {e}")
            failed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  🏁 TOPLU BAŞVURU TAMAMLANDI")
    print(f"{'='*60}")
    print(f"  ✅ Başarılı: {success}")
    if failed:
        print(f"  ❌ Başarısız: {failed}")
    print(f"  📁 Dosyalar: {OUTPUT_DIR}")
    print(f"\n  Sıradaki adımlar:")
    print(f"  1. applications/ klasöründeki cover letter'ları incele")
    print(f"  2. Her iş için başvuru linkini aç ve başvur")
    print(f"  3. Başvurduktan sonra: python3 job_hunter.py status <id> applied")
    print(f"  4. Takip için: python3 job_hunter.py remind\n")


# --- FOLLOW-UP REMINDERS ---
def cmd_remind():
    """Show follow-up reminders for applied jobs."""
    jobs = load_jobs()
    today = datetime.now()

    applied_jobs = [j for j in jobs if j.get('status') == 'applied' and j.get('date_applied')]
    preparing_jobs = [j for j in jobs if j.get('status') == 'preparing']
    interview_jobs = [j for j in jobs if j.get('status') == 'interview']

    print(f"\n{'='*60}")
    print(f"  ⏰ TAKİP HATIRLATMALARI")
    print(f"{'='*60}")

    if not applied_jobs and not preparing_jobs and not interview_jobs:
        print(f"\n  Henüz takip edilecek başvuru yok.")
        print(f"  Önce başvuru yap: python3 job_hunter.py batch")
        print()
        return

    # 1. Preparing too long (need to actually apply)
    if preparing_jobs:
        print(f"\n  📝 BAŞVURU BEKLİYOR ({len(preparing_jobs)} iş):")
        print(f"  {'─'*55}")
        for j in preparing_jobs:
            days = (today - datetime.strptime(j['date_found'], '%Y-%m-%d')).days
            urgency = "🔴 ACİL" if days > 7 else "🟡" if days > 3 else "🟢"
            print(f"  {urgency} {j['job_id']:<10} {j['company'][:20]:<22} {j['title'][:25]:<27} ({days} gün)")
            if j.get('url'):
                print(f"       🔗 {j['url']}")

    # 2. Applied — need follow-up?
    if applied_jobs:
        print(f"\n  📨 BAŞVURULAN İŞLER ({len(applied_jobs)}):")
        print(f"  {'─'*55}")
        for j in applied_jobs:
            try:
                applied_date = datetime.strptime(j['date_applied'], '%Y-%m-%d')
                days_since = (today - applied_date).days
            except ValueError:
                days_since = 0

            if days_since >= 14:
                status_icon = "🔴 Follow-up at! (2+ hafta)"
            elif days_since >= 7:
                status_icon = "🟡 Yakında follow-up at (1 hafta)"
            elif days_since >= 5:
                status_icon = "🟢 Bekleniyor (5 gün)"
            else:
                status_icon = "⏳ Yeni başvuru"

            print(f"  {status_icon}")
            print(f"       {j['job_id']:<10} {j['company'][:20]:<22} {j['title'][:25]} — {days_since} gün önce")

    # 3. Interviews
    if interview_jobs:
        print(f"\n  🎤 MÜLAKAT AŞAMASI ({len(interview_jobs)}):")
        print(f"  {'─'*55}")
        for j in interview_jobs:
            print(f"  ⭐ {j['job_id']:<10} {j['company'][:20]:<22} {j['title'][:25]}")
            print(f"       💡 Hazırlık: python3 job_hunter.py interview {j['job_id']}")

    # 4. Summary & next actions
    total_active = len(applied_jobs) + len(preparing_jobs) + len(interview_jobs)
    followup_needed = sum(1 for j in applied_jobs
                         if j.get('date_applied') and
                         (today - datetime.strptime(j['date_applied'], '%Y-%m-%d')).days >= 7)

    print(f"\n  {'='*55}")
    print(f"  📊 ÖZET:")
    print(f"     Aktif başvurular:     {total_active}")
    print(f"     Follow-up gerekli:    {followup_needed}")
    print(f"     Başvuru bekleyen:     {len(preparing_jobs)}")
    print(f"     Mülakat aşamasında:   {len(interview_jobs)}")
    print(f"  {'='*55}\n")


# --- MAIN CLI ---
def cmd_search():
    """Search for jobs and add to tracker."""
    init_tracker()
    print("\n=== JobHunter - Searching for Jobs ===\n")

    # Search GitHub repos
    print("Searching GitHub new-grad repos...")
    github_jobs = search_jobs_github()
    added = 0
    for job in github_jobs:
        if save_job(job):
            added += 1

    print(f"  Found {len(github_jobs)} relevant jobs, added {added} new ones.\n")

    # Show web search links
    searches, career_pages = search_jobs_web()
    print("=== Manual Search Links (open in browser) ===\n")
    for name, url in searches.items():
        print(f"  {name}:")
        print(f"    {url}\n")

    print("=== Company Career Pages ===\n")
    for company, url in career_pages.items():
        print(f"  {company}: {url}")

    print(f"\n=== Total jobs in tracker: {len(load_jobs())} ===")

def cmd_dashboard():
    """Show application dashboard."""
    jobs = load_jobs()
    if not jobs:
        print("No jobs tracked yet. Run: python3 job_hunter.py search")
        return

    # Stats
    statuses = {}
    for j in jobs:
        s = j.get('status', 'unknown')
        statuses[s] = statuses.get(s, 0) + 1

    print("\n=== JobHunter Dashboard ===\n")
    print(f"Total jobs tracked: {len(jobs)}")
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")

    # Top matches
    print("\n=== Top Matches (by score) ===\n")
    sorted_jobs = sorted(jobs, key=lambda x: int(x.get('match_score', 0)), reverse=True)
    print(f"{'ID':<10} {'Company':<25} {'Title':<35} {'Score':<6} {'Status':<10}")
    print("-" * 90)
    for j in sorted_jobs[:20]:
        print(f"{j['job_id']:<10} {j['company'][:24]:<25} {j['title'][:34]:<35} {j.get('match_score','?'):<6} {j['status']:<10}")

    # Pending applications
    new_jobs = [j for j in jobs if j.get('status') == 'new']
    if new_jobs:
        print(f"\nYou have {len(new_jobs)} new jobs to review!")
        print("Run: python3 job_hunter.py apply <job_id>")

def _find_job(job_id):
    """Find a job by ID."""
    jobs = load_jobs()
    for j in jobs:
        if j['job_id'] == job_id:
            return j
    return None

def cmd_apply(job_id):
    """Generate AI-powered application materials for a job."""
    job = _find_job(job_id)
    if not job:
        print(f"Job {job_id} not found. Run 'dashboard' to see available jobs.")
        return

    company = job['company']
    title = job['title']
    print(f"\n{'='*60}")
    print(f"  🚀 AI BAŞVURU PAKETİ: {title} @ {company}")
    print(f"{'='*60}\n")

    # Create output directory
    safe_name = re.sub(r'[^\w\-]', '_', f"{company}_{title}")
    out_dir = OUTPUT_DIR / safe_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. AI Cover Letter
    print("📝 AI Cover Letter oluşturuluyor...")
    cover_letter = generate_cover_letter(job)
    cl_file = out_dir / "cover_letter.txt"
    with open(cl_file, 'w') as f:
        f.write(cover_letter)
    print(f"   ✅ {cl_file}")

    # 2. AI Resume Tailoring
    print("📋 AI Resume önerileri hazırlanıyor...")
    emphasis = tailor_resume_bullets(job)
    suggestions_file = out_dir / "resume_tips.txt"
    with open(suggestions_file, 'w') as f:
        f.write(f"Resume Tailoring Tips for: {title} at {company}\n")
        f.write("=" * 60 + "\n\n")
        if 'ai_tips' in emphasis:
            f.write(emphasis['ai_tips'])
        else:
            f.write("HIGHLIGHT THESE:\n")
            for item in emphasis.get('highlight', []):
                f.write(f"  - {item}\n")
            f.write("\nADD THESE KEYWORDS:\n")
            for kw in emphasis.get('add_keywords', []):
                f.write(f"  - {kw}\n")
    print(f"   ✅ {suggestions_file}")

    # 3. AI Cold Outreach Messages
    print("💬 AI networking mesajları yazılıyor...")
    outreach = ai_cold_outreach(job)
    msg_file = out_dir / "outreach_messages.txt"
    with open(msg_file, 'w') as f:
        f.write(f"Outreach Messages for: {title} at {company}\n")
        f.write("=" * 60 + "\n\n")
        f.write(outreach)
    print(f"   ✅ {msg_file}")

    # 4. LinkedIn Searches
    print("🔍 LinkedIn arama linkleri hazırlanıyor...")
    searches = get_linkedin_search(job)
    linkedin_file = out_dir / "linkedin_contacts.txt"
    with open(linkedin_file, 'w') as f:
        f.write(f"LinkedIn Search Links for: {company}\n")
        f.write("=" * 60 + "\n\n")
        for search_title, url in searches:
            f.write(f"{search_title}:\n  {url}\n\n")
    print(f"   ✅ {linkedin_file}")

    # 5. AI Job Analysis
    print("🔬 AI iş analizi yapılıyor...")
    analysis = ai_analyze_job(job)
    analysis_file = out_dir / "job_analysis.txt"
    with open(analysis_file, 'w') as f:
        f.write(f"Job Analysis: {title} at {company}\n")
        f.write("=" * 60 + "\n\n")
        f.write(analysis)
    print(f"   ✅ {analysis_file}")

    # Update status
    update_job_status(job_id, "preparing")

    print(f"\n{'='*60}")
    print(f"  📁 Tüm dosyalar: {out_dir}")
    print(f"  📊 Durum: 'preparing' olarak güncellendi")
    if job.get('url'):
        print(f"  🔗 Başvuru linki: {job['url']}")
    print(f"{'='*60}")
    print(f"\n  💡 Mülakat hazırlığı için: python3 job_hunter.py interview {job_id}")


def cmd_interview(job_id):
    """AI-powered interview preparation."""
    job = _find_job(job_id)
    if not job:
        print(f"Job {job_id} not found.")
        return

    company = job['company']
    title = job['title']
    print(f"\n{'='*60}")
    print(f"  🎤 AI MÜLAKAT HAZIRLIK: {title} @ {company}")
    print(f"{'='*60}\n")

    print("AI mülakat soruları hazırlanıyor...\n")
    prep = ai_interview_prep(job)
    print(prep)

    # Save to file
    safe_name = re.sub(r'[^\w\-]', '_', f"{company}_{title}")
    out_dir = OUTPUT_DIR / safe_name
    out_dir.mkdir(parents=True, exist_ok=True)
    prep_file = out_dir / "interview_prep.txt"
    with open(prep_file, 'w') as f:
        f.write(f"Interview Prep: {title} at {company}\n")
        f.write("=" * 60 + "\n\n")
        f.write(prep)
    print(f"\n📁 Kaydedildi: {prep_file}")


def cmd_analyze(job_id):
    """AI-powered job analysis."""
    job = _find_job(job_id)
    if not job:
        print(f"Job {job_id} not found.")
        return

    company = job['company']
    title = job['title']
    print(f"\n{'='*60}")
    print(f"  🔬 AI İŞ ANALİZİ: {title} @ {company}")
    print(f"{'='*60}\n")

    print("AI analiz yapılıyor...\n")
    analysis = ai_analyze_job(job)
    print(analysis)


def cmd_ai(question):
    """Ask AI anything about job search."""
    prompt = f"""You are a career advisor for this candidate. Answer their question helpfully.
Write in Turkish (technical terms in English is OK).

{ELA_PROFILE}

Current job search status: 78 jobs tracked, mostly new/unreviewed, targeting Data Analyst and Business Analyst roles.

Question: {question}

Give specific, actionable advice. Don't be generic.
"""
    print(f"\n🤖 AI Kariyer Danışmanı\n")
    response = ai_generate(prompt, "AI yanıt veremedi.")
    print(response)

def cmd_linkedin(job_id):
    """Show LinkedIn search results for a job."""
    jobs = load_jobs()
    job = None
    for j in jobs:
        if j['job_id'] == job_id:
            job = j
            break

    if not job:
        print(f"Job {job_id} not found.")
        return

    print(f"\n=== LinkedIn Contacts for {job['company']} ===\n")
    searches = get_linkedin_search(job)
    for title, url in searches:
        print(f"  {title}:")
        print(f"    {url}\n")

    print("\n=== Cold Outreach Templates ===\n")
    linkedin_msg, email_msg = generate_cold_message(job)
    print("--- LinkedIn Message ---")
    print(linkedin_msg)
    print("\n--- Email Template ---")
    print(email_msg)

def cmd_add(company, title, url="", location=""):
    """Manually add a job to tracker."""
    init_tracker()
    jobs = load_jobs()
    job_id = f"MAN-{len(jobs)+1:04d}"
    match_score = calculate_match_score(title, company)

    job = {
        'job_id': job_id,
        'company': company,
        'title': title,
        'location': location,
        'url': url,
        'date_found': datetime.now().strftime('%Y-%m-%d'),
        'status': 'new',
        'date_applied': '',
        'contact_name': '',
        'contact_linkedin': '',
        'contact_email': '',
        'notes': '',
        'match_score': str(match_score),
        'h1b_sponsor': 'check'
    }

    if save_job(job):
        print(f"Added: {title} at {company} (ID: {job_id}, Score: {match_score})")
    else:
        print(f"Job already exists: {title} at {company}")

def cmd_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🎯 JobHunter - AI-Powered Job Search System          ║
╚══════════════════════════════════════════════════════════════╝

⚡ HIZLI BAŞLANGIÇ (vakit yoksa sadece bu 3 komutu çalıştır):
  1. smart-filter             Uygun olmayanları otomatik ele
  2. batch [N]                En iyi N iş için AI başvuru paketi (varsayılan: 10)
  3. remind                   Takip hatırlatmaları

📋 TEMEL KOMUTLAR:
  search                    Yeni iş ilanları ara (GitHub repos)
  dashboard                 Başvuru takip tablosu
  analytics                 Detaylı ilerleme analizi ve istatistikler

🤖 AI-POWERED KOMUTLAR (Gemini):
  apply <job_id>            Tek iş için AI başvuru paketi
  interview <job_id>        AI mülakat hazırlık soruları
  analyze <job_id>          AI iş analizi (uyum, strateji, red flags)
  ai "soru"                 AI kariyer danışmanına soru sor

🔗 NETWORKING:
  linkedin <job_id>         Hiring manager bulma + AI outreach mesajları

📝 YÖNETİM:
  add "Şirket" "Pozisyon" ["URL"] ["Lokasyon"]   Manuel iş ekle
  status <job_id> <durum>   Durum güncelle
  smart-filter              Uygun olmayanları otomatik filtrele
  remind                    Takip hatırlatmaları

💡 Tipik Workflow:
  python3 job_hunter.py search           # Yeni ilanları çek
  python3 job_hunter.py smart-filter     # Çöpü ele
  python3 job_hunter.py batch 10         # En iyi 10'a toplu başvuru paketi
  python3 job_hunter.py status GH-0038 applied   # Başvurduktan sonra işaretle
  python3 job_hunter.py remind           # Takip hatırlatmaları
""")

if __name__ == "__main__":
    # Init config
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)

    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "search":
        cmd_search()
    elif command == "analytics":
        cmd_analytics()
    elif command == "dashboard":
        cmd_dashboard()
    elif command in ("smart-filter", "filter"):
        cmd_smart_filter()
    elif command == "h1b":
        try:
            from h1b_checker import bulk_check_h1b
            bulk_check_h1b(str(JOBS_FILE))
        except ImportError:
            print("h1b_checker.py bulunamadı.")
    elif command == "batch":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        cmd_batch(count)
    elif command == "remind":
        cmd_remind()
    elif command == "apply":
        if len(sys.argv) < 3:
            print("Usage: python3 job_hunter.py apply <job_id>")
        else:
            cmd_apply(sys.argv[2])
    elif command == "interview":
        if len(sys.argv) < 3:
            print("Usage: python3 job_hunter.py interview <job_id>")
        else:
            cmd_interview(sys.argv[2])
    elif command == "analyze":
        if len(sys.argv) < 3:
            print("Usage: python3 job_hunter.py analyze <job_id>")
        else:
            cmd_analyze(sys.argv[2])
    elif command == "ai":
        if len(sys.argv) < 3:
            print('Usage: python3 job_hunter.py ai "your question here"')
        else:
            cmd_ai(" ".join(sys.argv[2:]))
    elif command == "linkedin":
        if len(sys.argv) < 3:
            print("Usage: python3 job_hunter.py linkedin <job_id>")
        else:
            cmd_linkedin(sys.argv[2])
    elif command == "add":
        if len(sys.argv) < 4:
            print('Usage: python3 job_hunter.py add "Company" "Title" ["URL"] ["Location"]')
        else:
            url = sys.argv[4] if len(sys.argv) > 4 else ""
            location = sys.argv[5] if len(sys.argv) > 5 else ""
            cmd_add(sys.argv[2], sys.argv[3], url, location)
    elif command == "status":
        if len(sys.argv) < 4:
            print("Usage: python3 job_hunter.py status <job_id> <new|preparing|applied|interview|rejected|offer>")
        else:
            if update_job_status(sys.argv[2], sys.argv[3]):
                print(f"Updated {sys.argv[2]} to '{sys.argv[3]}'")
            else:
                print(f"Job {sys.argv[2]} not found.")
    elif command == "help":
        cmd_help()
    else:
        print(f"Unknown command: {command}")
        cmd_help()
