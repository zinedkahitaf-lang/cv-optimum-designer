import sys
import os

# === AGGRESSIVE ISOLATION BYPASS (V3) ===
# This kills the conflict with the old 'fpdf' library by completely 
# purging sys.modules and force-prioritizing the local folder.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Purge any existing fpdf/PIL references BEFORE imports
for m in list(sys.modules.keys()):
    if 'fpdf' in m.lower() or 'pil' in m.lower():
        del sys.modules[m]

import streamlit as st
import openai
import json
import io
import base64
from PIL import Image
from fpdf import FPDF

# Sayfa Ayarları
st.set_page_config(
    page_title="Profesyonel CV Sihirbazı",
    page_icon="🎨",
    layout="wide"
)

# === CUSTOM CSS - PREMIUM DESIGN ===
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Inter:wght@300;400;600&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Outfit', sans-serif; font-weight: 700; color: #1e293b; }
    
    .stApp {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    }
    
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* Global Glassmorphism */
    div.stChatMessage {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        margin-bottom: 1rem;
    }
    
    /* Sidebar Styling */
    .css-1d391kg {
        background-color: #0f172a;
    }
    
    .stButton button {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: scale(1.02);
        box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4);
    }
    
    /* Profile Circle */
    .profile-frame {
        width: 150px;
        height: 150px;
        border-radius: 50%;
        overflow: hidden;
        border: 4px solid #6366f1;
        margin: 0 auto 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# === INITIAL SESSION STATE ===
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_data" not in st.session_state:
    st.session_state.user_data = {
        "name": "",
        "summary": "",
        "experience": [],
        "education": [],
        "skills": [],
        "contact": {},
        "photo": None
    }
if "job_description" not in st.session_state:
    st.session_state.job_description = ""

# --- API KEY MANAGEMENT ---
# Priority: 1. Streamlit Secrets (Cloud), 2. Sidebar Input (Local)
api_key = st.secrets.get("OPENAI_API_KEY")

if not api_key:
    with st.sidebar:
        st.markdown("### 🔑 API Anahtarı")
        api_key = st.text_input("OpenAI API Key:", type="password", placeholder="sk-...")
        if api_key:
            st.success("Anahtar girildi!")
        else:
            st.warning("Devam etmek için API anahtarı giriniz.")
            st.stop()

openai.api_key = api_key

# === SIDEBAR: PHOTO & JOB ===
with st.sidebar:
    st.markdown("# 🛠️ Kontrol Paneli")
    
    # Photo Upload
    st.markdown("### 📸 Profil Resmi")
    uploaded_photo = st.file_uploader("Bir fotoğraf seçin...", type=["jpg", "png", "jpeg"])
    if uploaded_photo:
        # Robust loading to avoid UnidentifiedImageError
        img_bytes = uploaded_photo.read()
        img = Image.open(io.BytesIO(img_bytes))
        uploaded_photo.seek(0) # Reset just in case
        st.image(img, use_container_width=True, caption="Seçilen Resim")
        # Save to session state
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        st.session_state.user_data["photo"] = base64.b64encode(buffered.getvalue()).decode()

    st.markdown("---")
    
    # Job Description
    st.markdown("### 💼 İş İlanı Analizi")
    job_desc = st.text_area("Hedef iş ilanını buraya yapıştırın:", height=200)
    if job_desc != st.session_state.job_description:
        st.session_state.job_description = job_desc
        st.success("İş ilanı kaydedildi. İnceleme başlıyor...")

    st.markdown("---")
    st.info("👨‍💻 **Geliştirici Notu**\n\nBu uygulama İş Güvenliği Uzmanı **Fatih AKDENİZ** tarafından geliştirilmiştir.")

# === ANA ARAYÜZ ===
st.title("🛡️ Profesyonel CV Tasarım Sihirbazı")
st.markdown("### Hoş geldin! CV oluşturma sürecinde senin yardımcınım. Seninle konuşarak o muhteşem CV'yi hazırlayacağız.")

# Chat history display
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Kendini bana anlat..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI Response Logic
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Sistem Talimatları
        system_msg = f"""
        Sen bir İK uzmanı ve aday yardımcısısın. 
        Görevin: Kullanıcının paylaştığı İŞ İLANINI analiz etmek ve bu ilana %100 uyumlu, adayları mülakata çağırttıracak premium bir CV hazırlamak.
        
        MEVCUT İŞ İLANI: {st.session_state.job_description if st.session_state.job_description else 'Henüz paylaşılmadı.'}
        
        🔴 ANAYASAN - TÜM KURALLARIN ÖNÜNDEDİR:
        1. KİŞİSEL BİLGİ KORUMASI: İsim, Soyisim, Telefon, E-posta, LinkedIn, Adres, Okul isimleri ve Şirket isimlerini ASLA UYDURMA. Bunlar kritiktir, eksikse sadece sor.
        2. HR KREATİFLİĞİ: Özet (Summary) ve İş Deneyimi (Experience) açıklamalarında DEHANLA PARLA. Kullanıcının verdiği basit cümleleri, İK terminolojisiyle (Örn: "End-to-end management", "Strategic optimization", "Stakeholder engagement") ZENGİNLEŞTİR.
        3. İŞ İLANI ANALİZİ: İlandaki anahtar kelimeleri tespit et ve mülakatta bu noktalara (Örn: belirli bir sertifika veya yazılım tecrübesi) odaklan.
        4. TEK MESAJDA SOR: Aşağıdaki her alanı madde madde ve detaylıca tek bir mesajda iste:
           - Tam İsim ve İletişim Bilgileri (E-posta, Tel, Konum)
           - İş Deneyimi (Şirket, Pozisyon, Tarihler, Başarılar - Sen bunları en etkileyici hale getireceksin)
           - Eğitim (Okul, Bölüm, Mezuniyet Tarihi)
           - Yetenekler (Soft & Hard Skills)
           - DİLLER (Hangi dilleri, hangi seviyede biliyorsun?)
        5. DOĞRUDAN KONUYA GİR: "Merhaba dostum, jilet gibi bir CV için şu detayları masaya yatıralım" diyerek listeyi sun.
        
        HEDEF: Kullanıcı bu mesajı okuduğunda, senin tecrübesine değer katacağını hissetmeli.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_msg},
                    *st.session_state.messages
                ],
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"AI Hatası: {str(e)}")

# === PDF GENERATION LOGIC (FPDF2) ===
def generate_premium_pdf(cv_data, photo_b64):
    try:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        
        # Register Fonts (Turkish Support)
        pdf.add_font("Arial", "", "fonts/arial.ttf")
        pdf.add_font("Arial", "B", "fonts/arialbd.ttf")
        pdf.add_font("Arial", "I", "fonts/ariali.ttf")
        
        # Colors
        color_navy = (15, 23, 42)    # #0f172a
        color_accent = (99, 102, 241) # #6366f1
        color_text = (30, 41, 59)     # #1e293b
        color_light = (100, 116, 139) # #64748b
        color_white = (255, 255, 255)
        # --- SIDEBAR BACKGROUND ---
        pdf.set_fill_color(*color_navy)
        pdf.rect(0, 0, 70, 297, "F")
        
        # --- PHOTO ---
        if photo_b64:
            try:
                img_data = base64.b64decode(photo_b64)
                img_stream = io.BytesIO(img_data)
                img = Image.open(img_stream)
                pdf.image(img, x=17.5, y=10, w=35)
            except: pass
        
        # --- SIDEBAR CONTENT (X=10) ---
        pdf.set_text_color(*color_white)
        
        # Contact Section
        y_pos = 55
        pdf.set_font("Arial", "B", 11)
        pdf.set_xy(10, y_pos)
        pdf.cell(50, 7, "İLETİŞİM", ln=True)
        pdf.set_draw_color(*color_accent)
        pdf.line(10, pdf.get_y(), 60, pdf.get_y())
        
        pdf.set_font("Arial", "", 8.5)
        pdf.ln(3)
        pdf.set_x(10)
        # Handle multi-line contact info with spacing
        contact_info = [
            f"📧 {cv_data.get('contact', {}).get('email', '')}",
            f"📞 {cv_data.get('contact', {}).get('phone', '')}",
            f"📍 {cv_data.get('contact', {}).get('location', '')}"
        ]
        for line in contact_info:
            pdf.set_x(10)
            pdf.cell(50, 5, line, ln=True)
        
        # Skills Section
        pdf.ln(6)
        y_pos = pdf.get_y()
        pdf.set_font("Arial", "B", 11)
        pdf.set_x(10)
        pdf.cell(50, 7, "YETENEKLER", ln=True)
        pdf.line(10, pdf.get_y(), 60, pdf.get_y())
        
        pdf.set_font("Arial", "", 8.5)
        pdf.ln(3)
        for s in cv_data.get('skills', []):
            pdf.set_x(10)
            pdf.multi_cell(50, 5, f"• {s}")
            pdf.ln(1)
        
        # Languages Section
        pdf.ln(6)
        y_pos = pdf.get_y()
        pdf.set_font("Arial", "B", 11)
        pdf.set_x(10)
        pdf.cell(50, 7, "DİLLER", ln=True)
        pdf.line(10, pdf.get_y(), 60, pdf.get_y())
        
        pdf.set_font("Arial", "", 8.5)
        pdf.ln(3)
        pdf.set_x(10)
        pdf.multi_cell(50, 5, ", ".join(cv_data.get('languages', [])))

        # --- MAIN CONTENT (X=80) ---
        pdf.set_text_color(*color_navy)
        
        # Name (X=80, Y=15)
        pdf.set_font("Arial", "B", 22)
        pdf.set_xy(80, 15)
        pdf.cell(120, 10, cv_data.get('full_name', ''), ln=True)
        
        # Title
        pdf.set_text_color(*color_accent)
        pdf.set_font("Arial", "B", 13)
        pdf.set_x(80)
        pdf.cell(120, 7, cv_data.get('role_title', ''), ln=True)
        
        # Summary
        pdf.ln(5)
        pdf.set_text_color(*color_navy)
        pdf.set_font("Arial", "B", 10.5)
        pdf.set_x(80)
        pdf.cell(120, 6, "ÖZET", ln=True)
        pdf.set_draw_color(*color_accent)
        pdf.line(80, pdf.get_y(), 200, pdf.get_y())
        
        pdf.ln(2)
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(*color_text)
        pdf.set_x(80)
        pdf.multi_cell(120, 4.2, cv_data.get('summary', ''))
        
        # Experience
        pdf.ln(5)
        pdf.set_text_color(*color_navy)
        pdf.set_font("Arial", "B", 10.5)
        pdf.set_x(80)
        pdf.cell(120, 6, "DENEYİM", ln=True)
        pdf.line(80, pdf.get_y(), 200, pdf.get_y())
        
        pdf.ln(4)
        for exp in cv_data.get('experience', []):
            # Company & Date
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(*color_navy)
            pdf.set_x(80)
            
            # Draw company and date on same line
            current_y = pdf.get_y()
            pdf.cell(90, 7, exp.get('company', ''))
            pdf.set_font("Arial", "", 8.5)
            pdf.set_text_color(*color_light)
            pdf.set_xy(170, current_y)
            pdf.cell(30, 7, exp.get('date', ''), align="R", ln=True)
            
            # Role
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(*color_accent)
            pdf.set_x(80)
            pdf.cell(120, 5, exp.get('role', ''), ln=True)
            
            # Description
            pdf.set_font("Arial", "", 8.5)
            pdf.set_text_color(*color_text)
            pdf.set_x(82)
            pdf.multi_cell(118, 4.2, exp.get('description', ''))
            pdf.ln(2)

        # Education
        pdf.ln(3)
        pdf.set_text_color(*color_navy)
        pdf.set_font("Arial", "B", 10.5)
        pdf.set_x(80)
        pdf.cell(120, 6, "EĞİTİM", ln=True)
        pdf.line(80, pdf.get_y(), 200, pdf.get_y())
        
        pdf.ln(3)
        for edu in cv_data.get('education', []):
            pdf.set_font("Arial", "B", 10)
            pdf.set_x(80)
            current_y = pdf.get_y()
            pdf.cell(90, 7, edu.get('school', ''))
            pdf.set_font("Arial", "", 8.5)
            pdf.set_text_color(*color_light)
            pdf.set_xy(170, current_y)
            pdf.cell(30, 7, edu.get('date', ''), align="R", ln=True)
            
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(*color_text)
            pdf.set_x(80)
            pdf.cell(120, 5, edu.get('degree', ''), ln=True)
            pdf.ln(1)

        return bytes(pdf.output())
    except Exception as e:
        st.error(f"PDF Oluşturma Hatası (fpdf2): {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

# === FINAL GENERATION LOGIC ===
def generate_premium_html(cv_data, photo_b64):
    # Pre-build segments to avoid nested f-strings (Python 3.11 compatibility)
    
    # Skills tags
    skills_html = "".join([f'<span class="skill-tag" style="background: rgba(255,255,255,0.1); color: white;">{s}</span>' for s in cv_data.get('skills', [])])
    
    # Experience items
    exp_html = ""
    for exp in cv_data.get('experience', []):
        exp_html += f"""
        <div class="experience-item">
            <div class="exp-header">
                <span class="company-name">{exp.get('company', '')}</span>
                <span class="job-date">{exp.get('date', '')}</span>
            </div>
            <div class="job-title">{exp.get('role', '')}</div>
            <p style="font-size: 13px; color: var(--text-light); line-height: 1.5;">{exp.get('description', '')}</p>
        </div>
        """
    
    # Education items
    edu_html = ""
    for edu in cv_data.get('education', []):
        edu_html += f"""
        <div class="experience-item">
            <div class="exp-header">
                <span class="company-name">{edu.get('school', '')}</span>
                <span class="job-date">{edu.get('date', '')}</span>
            </div>
            <div class="job-title">{edu.get('degree', '')}</div>
        </div>
        """
    
    # Base template
    html_template = f"""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{cv_data.get('full_name', 'Profesyonel CV')}</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #0f172a;
            --accent: #6366f1;
            --text-dark: #1e293b;
            --text-light: #64748b;
            --white: #ffffff;
        }}

        @media print {{
            @page {{ size: A4; margin: 0; }}
            body {{ -webkit-print-color-adjust: exact; }}
            .no-print {{ display: none; }}
        }}

        body {{
            margin: 0;
            background-color: #f1f5f9;
            font-family: 'Inter', sans-serif;
            color: var(--text-dark);
        }}

        .cv-container {{
            width: 210mm;
            min-height: 297mm;
            margin: 20px auto;
            background: var(--white);
            display: grid;
            grid-template-columns: 280px 1fr;
            box-shadow: 0 0 50px rgba(0,0,0,0.1);
        }}

        .sidebar {{
            background-color: var(--primary);
            color: var(--white);
            padding: 40px 30px;
        }}

        .photo-container {{
            width: 160px;
            height: 160px;
            border-radius: 50%;
            border: 4px solid var(--accent);
            margin: 0 auto 30px;
            overflow: hidden;
            background: #1e293b;
        }}

        .photo-container img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .main-content {{
            padding: 50px 40px;
            background: var(--white);
        }}

        .section-title {{
            font-family: 'Montserrat', sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: var(--primary);
            border-bottom: 2px solid var(--accent);
            padding-bottom: 8px;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .sidebar .section-title {{
            color: var(--white);
            border-bottom-color: rgba(255,255,255,0.2);
            font-size: 14px;
        }}

        .experience-item {{
            margin-bottom: 25px;
        }}

        .exp-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 5px;
        }}

        .company-name {{
            font-weight: 700;
            font-size: 16px;
            color: var(--primary);
        }}

        .job-date {{
            font-size: 13px;
            color: var(--text-light);
        }}

        .job-title {{
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 8px;
            font-size: 14px;
        }}

        .summary-text {{
            font-style: italic;
            line-height: 1.6;
            color: var(--text-light);
            margin-bottom: 30px;
        }}

        .skill-tag {{
            display: inline-block;
            background: rgba(99, 102, 241, 0.1);
            color: var(--accent);
            padding: 5px 12px;
            border-radius: 20px;
            margin: 0 5px 10px 0;
            font-size: 12px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="cv-container">
        <aside class="sidebar">
            <div class="photo-container">
                {f'<img src="data:image/png;base64,{photo_b64}" />' if photo_b64 else ''}
            </div>
            
            <div class="section-title">İletişim</div>
            <p style="font-size: 13px; margin-bottom: 15px;">
                📧 {cv_data.get('contact', {}).get('email', '')}<br>
                📞 {cv_data.get('contact', {}).get('phone', '')}<br>
                📍 {cv_data.get('contact', {}).get('location', '')}
            </p>

            <div class="section-title">Yetenekler</div>
            <div>
                {skills_html}
            </div>

            <div class="section-title" style="margin-top: 30px;">Diller</div>
            <p style="font-size: 13px;">
                {', '.join(cv_data.get('languages', []))}
            </p>
        </aside>

        <main class="main-content">
            <h1 style="font-family: 'Montserrat'; font-size: 40px; margin: 0; color: var(--primary);">{cv_data.get('full_name', '')}</h1>
            <h2 style="font-size: 20px; font-weight: 400; color: var(--accent); margin: 5px 0 30px 0;">{cv_data.get('role_title', '')}</h2>

            <div class="section-title">Özet</div>
            <p class="summary-text">{cv_data.get('summary', '')}</p>

            <div class="section-title">Deneyim</div>
            {exp_html}

            <div class="section-title">Eğitim</div>
            {edu_html}
        </main>
    </div>
</body>
</html>
    """
    return html_template

# === GENERATE CV BUTTON ===
if st.button("✨ CV'mi Hemen Oluştur (Draft)"):
    st.info("Veriler analiz ediliyor ve Ultra-Premium tasarımına giydiriliyor... (Bu işlem bir saniye sürecek)")
    
    synth_prompt = f"""
    Aşağıdaki sohbet geçmişinden yararlanarak kullanıcı için profesyonel bir CV objesi oluştur (JSON formatında). 
    İş ilanına ({st.session_state.job_description}) göre metinleri optimize et (ATS-Friendly).
    
    🔴 KESİN TALİMATLAR - STRATEJİK İK DOKUNUŞU: 
    1. KİŞİSEL VERİ GÜVENLİĞİ: İsim, Soyisim, Telefon, E-posta, LinkedIn, Adres, Okul isimleri ve Şirket isimlerini ASLA UYDURMA. Konuşmada yoksa "[BİLGİ EKSİK]" yaz.
    2. PROFESYONEL PARLATMA & TEK SAYFA OPTİMİZASYONU: 
       - 'summary' ve deneyim açıklamalarında senin becerin konuşsun. 
       - Kullanıcının verdiği başarıları İK diliyle ZENGİNLEŞTİR.
       - KRİTİK: CV'nin tek bir A4 sayfasına sığması gerekiyor. Bu yüzden metinleri mümkün olduğunca vurucu, sonuç odaklı ama GEREKSİZ UZATMADAN yaz. Kelime kalabalığı yapma, her cümle bir değer katsın.
    3. JSON Formatı (Kesin):
    {{
      "full_name": "...",
      "role_title": "İlanla uyumlu iddialı bir başlık",
      "contact": {{"email": "...", "phone": "...", "location": "...", "linkedin": "..."}},
      "summary": "Senin tarafandan profesyonelce yazılmış, etkileyici ve ilan uyumlu özet",
      "experience": [{{ "company": "...", "role": "...", "date": "...", "description": "Senin tarafandan zenginleştirilmiş profesyonel açıklama" }}],
      "education": [{{ "school": "...", "degree": "...", "date": "..." }}],
      "skills": ["...", "..."],
      "languages": ["...", "..."]
    }}
    
    SOHBET GEÇMİŞİ VE MÜLAKAT VERİLERİ:
    {json.dumps(st.session_state.messages, ensure_ascii=False)}
    """
    
    try:
        final_gen = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": synth_prompt}],
            response_format={ "type": "json_object" }
        )
        cv_json = json.loads(final_gen.choices[0].message.content)
        st.session_state.user_data.update(cv_json)
        
        # HTML Generate
        final_html = generate_premium_html(cv_json, st.session_state.user_data["photo"])
        
        # PDF Generate
        final_pdf = generate_premium_pdf(cv_json, st.session_state.user_data["photo"])
        
        st.success("Analiz tamamlandı!")
        
        # Preview & Download
        st.markdown("### 📄 CV Önizleme")
        st.components.v1.html(final_html, height=800, scrolling=True)
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button(
                label="📥 Premium CV'yi İndir (HTML)",
                data=final_html,
                file_name=f"{cv_json['full_name']}_CV_Premium.html",
                mime="text/html"
            )
        
        with col_down2:
            if final_pdf:
                st.download_button(
                    label="📕 Premium CV'yi İndir (PDF)",
                    data=final_pdf,
                    file_name=f"{cv_json['full_name']}_CV_Premium.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("PDF oluşturulurken bir hata oluştu.")
        
    except Exception as e:
        st.error(f"Sentez Hatası: {str(e)}")
