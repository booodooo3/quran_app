import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import io
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import arabic_reshaper
from bidi.algorithm import get_display

# إعدادات الصفحة
st.set_page_config(
    page_title="المصحف المعلم",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# تنسيق CSS مخصص وآمن للجوال
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@400;700&display=swap');
    
    /* تطبيق الاتجاه العربي بشكل آمن لا يكسر تصميم Streamlit في الجوال */
    .block-container, [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
        font-family: 'Cairo', sans-serif;
    }
    
    p, div, span, h1, h2, h3, h4, h5, h6 {
        font-family: 'Cairo', sans-serif;
    }
    
    .stSelectbox, .stNumberInput {
        direction: rtl;
    }
    
    .quran-text {
        font-family: 'Amiri', serif;
        font-size: 36px;
        color: #0d47a1;
        text-align: center;
        background-color: #f5f7fa;
        padding: 25px;
        border-radius: 12px;
        margin: 20px 0;
        border: 1px solid #e3e6e8;
        line-height: 2.2;
    }
    
    .info-box {
        background-color: #e0f2f1;
        border-right: 6px solid #00695c;
        padding: 15px;
        border-radius: 8px;
        margin-top: 15px;
        font-size: 16px;
    }

    /* --- تلوين خانة الآية (العمود الثالث) وإيقاف الكيبورد --- */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child {
        background-color: #FFF9C4 !important; 
        border: 2px solid #FBC02D !important;
        border-radius: 8px !important;
    }
    
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) div[data-testid="stSelectbox"] input {
        caret-color: transparent !important;
        pointer-events: none !important;
        font-size: 16px !important;
    }
    
    /* --- تنسيق جدول العلامات في القائمة الجانبية --- */
    .signs-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
    }
    .signs-table td {
        border-bottom: 1px solid #ddd;
        padding: 12px 8px;
        font-size: 15px;
        line-height: 1.6;
    }
    .sign-symbol {
        color: #d32f2f !important;
        font-weight: bold;
        font-family: 'Amiri', serif;
        font-size: 26px;
        text-align: center;
        width: 40px;
    }
</style>
""", unsafe_allow_html=True)

# ثوابت البيانات
REVELATION_ORDER_LIST = [
    96, 68, 73, 74, 1, 111, 81, 87, 92, 89,
    93, 94, 103, 100, 108, 102, 107, 109, 105, 113,
    114, 112, 53, 80, 97, 91, 85, 95, 106, 101,
    75, 104, 77, 50, 90, 86, 54, 38, 7, 72,
    36, 25, 35, 19, 20, 56, 26, 27, 28, 17,
    10, 11, 12, 15, 6, 37, 31, 34, 39, 40,
    41, 42, 43, 44, 45, 46, 51, 88, 18, 16,
    71, 14, 21, 23, 32, 52, 67, 69, 70, 78,
    79, 82, 84, 30, 29, 83, 2, 8, 3, 33,
    60, 4, 99, 57, 47, 13, 55, 76, 65, 98,
    59, 24, 22, 63, 58, 49, 66, 64, 61, 62,
    48, 5, 9, 110
]

SURAH_REVELATION_ORDER = {surah: i + 1 for i, surah in enumerate(REVELATION_ORDER_LIST)}

RECITERS = {
    "ar.minshawi": "الشيخ محمد صديق المنشاوي",
    "ar.husary": "الشيخ محمود خليل الحصري",
    "ar.parhizgar": "القارئ شهريار برهيزقار"
}

# --- دالة تلوين العلامات القرآنية بالأحمر ---
def colorize_marks(text):
    marks = [
        "ۖ", "ۗ", "ۘ", "ۙ", "ۚ", "ۛ", 
        "ۢ", "ۡ", "ۤ", "ٓ", "ۜ", "۟", "۠", 
        "۩", "۞" 
    ]
    for mark in marks:
        text = text.replace(mark, f"<span style='color:#d32f2f; font-weight:bold;'>{mark}</span>")
    return text

# دوال مساعدة
@st.cache_data
def get_surahs():
    try:
        response = requests.get("https://api.alquran.cloud/v1/surah")
        if response.status_code == 200:
            return response.json()["data"]
        return []
    except:
        return []

@st.cache_data
def get_surah_with_audio_array(surah_num, reciter_id):
    try:
        text_res = requests.get(f"https://api.alquran.cloud/v1/surah/{surah_num}/quran-uthmani").json()
        audio_res = requests.get(f"https://api.alquran.cloud/v1/surah/{surah_num}/{reciter_id}").json()
        
        if text_res['code'] == 200 and audio_res['code'] == 200:
            combined = []
            text_ayahs = text_res['data']['ayahs']
            audio_ayahs = audio_res['data']['ayahs']
            for i in range(len(text_ayahs)):
                combined.append({
                    "text": text_ayahs[i]["text"],
                    "audio": audio_ayahs[i]["audio"],
                    "numberInSurah": text_ayahs[i]["numberInSurah"]
                })
            return combined
        return []
    except:
        return []

def get_ayah_data(surah_num, ayah_num, reciter_id):
    """جلب الآية بدون التفسير الميسر"""
    try:
        url_text = f"https://api.alquran.cloud/v1/ayah/{surah_num}:{ayah_num}/quran-uthmani"
        url_audio = f"https://api.alquran.cloud/v1/ayah/{surah_num}:{ayah_num}/{reciter_id}"
        
        text_res = requests.get(url_text).json()
        audio_res = requests.get(url_audio).json()
        
        if text_res["code"] == 200 and audio_res["code"] == 200:
            text_data = text_res["data"]["text"]
            if surah_num != 1 and ayah_num == 1:
                basmalah = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"
                if text_data.startswith(basmalah):
                     text_data = text_data[len(basmalah):].strip()
            
            return {
                "text": text_data,
                "audio": audio_res["data"]["audio"],
                "sajda": text_res["data"].get("sajda", False)
            }
        return None
    except Exception:
        return None

def ensure_font_exists():
    font_path = "Amiri-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(response.content)
        except Exception as e:
            pass
    return font_path

def to_arabic_numerals(n):
    digits = {'0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤', '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'}
    return "".join([digits[d] for d in str(n)])

@st.cache_data
def get_full_surah_text(surah_num):
    try:
        response = requests.get(f"https://api.alquran.cloud/v1/surah/{surah_num}/quran-uthmani")
        if response.status_code == 200:
            data = response.json()["data"]
            ayahs = []
            if surah_num != 1 and len(data["ayahs"]) > 0:
                first_ayah_text = data["ayahs"][0]['text']
                basmalah = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"
                if first_ayah_text.startswith(basmalah):
                    data["ayahs"][0]['text'] = first_ayah_text[len(basmalah):].strip()

            for ayah in data["ayahs"]:
                num = to_arabic_numerals(ayah['numberInSurah'])
                ayahs.append(f"{ayah['text']} ﴿{num}﴾")
            full_text = " ".join(ayahs)
            return data["name"], full_text
        return None, None
    except:
        return None, None

def create_pdf(surah_name, surah_text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    font_path = ensure_font_exists()
    try:
        pdfmetrics.registerFont(TTFont('Amiri', font_path))
    except:
        pass
    
    c.setFont('Amiri', 24)
    reshaped_title = arabic_reshaper.reshape(f"سورة {surah_name}")
    bidi_title = get_display(reshaped_title)
    c.drawCentredString(width / 2, height - 3 * cm, bidi_title)
    
    c.setFont('Amiri', 16)
    y_position = height - 5 * cm
    margin = 2 * cm
    line_height = 0.8 * cm
    max_width = width - 2 * margin
    
    words = surah_text.split()
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        reshaped_line = arabic_reshaper.reshape(line_str)
        bidi_line = get_display(reshaped_line)
        text_width = c.stringWidth(bidi_line, 'Amiri', 16)
        
        if text_width > max_width:
            current_line.pop()
            line_str = " ".join(current_line)
            reshaped_line = arabic_reshaper.reshape(line_str)
            bidi_line = get_display(reshaped_line)
            c.drawRightString(width - margin, y_position, bidi_line)
            y_position -= line_height
            current_line = [word]
            if y_position < margin:
                c.showPage()
                c.setFont('Amiri', 16)
                y_position = height - margin
    
    if current_line:
        line_str = " ".join(current_line)
        reshaped_line = arabic_reshaper.reshape(line_str)
        bidi_line = get_display(reshaped_line)
        c.drawRightString(width - margin, y_position, bidi_line)
        
    c.save()
    buffer.seek(0)
    return buffer

# التطبيق الرئيسي
def main():
    st.markdown("<h1 style='text-align: center;'>🕌 المصحف المعلم</h1>", unsafe_allow_html=True)

    with st.sidebar:
        st.header("📖 علامات الوقف ومصطلحات الضبط")
        st.markdown("""
        <table class="signs-table">
            <tr><td class="sign-symbol">مـ</td><td>تُفِيدُ لُزُومَ الْوَقْفِ</td></tr>
            <tr><td class="sign-symbol">لا</td><td>تُفِيدُ النَّهْيَ عَنِ الْوَقْفِ</td></tr>
            <tr><td class="sign-symbol">صلے</td><td>تُفِيدُ بِأَنَّ الْوَصْلَ أَوْلَى مَعَ جَوَازِ الْوَقْفِ</td></tr>
            <tr><td class="sign-symbol">قلے</td><td>تُفِيدُ بِأَنَّ الْوَقْفَ أَوْلَى</td></tr>
            <tr><td class="sign-symbol">ج</td><td>تُفِيدُ جَوَازَ الْوَقْفِ</td></tr>
            <tr><td class="sign-symbol">∴</td><td>تُفِيدُ جَوَازَ الْوَقْفِ بِأَحَدِ الْمَوْضِعَيْنِ وَلَيْسَ فِي كِلَيْهِمَا</td></tr>
            <tr><td class="sign-symbol">°</td><td>لِلدَّلَالَةِ عَلَى زِيَادَةِ الْحَرْفِ وَعَدَمِ النُّطْقِ بِهِ</td></tr>
            <tr><td class="sign-symbol">0</td><td>لِلدَّلَالَةِ عَلَى زِيَادَةِ الْحَرْفِ حِينَ الْوَصْلِ</td></tr>
            <tr><td class="sign-symbol">حـ</td><td>لِلدَّلَالَةِ عَلَى سُكُونِ الْحَرْفِ (رأس خاء بدون نقطة)</td></tr>
            <tr><td class="sign-symbol">م</td><td>لِلدَّلَالَةِ عَلَى وُجُودِ الْإِقْلَابِ</td></tr>
            <tr><td class="sign-symbol">ــٌـ</td><td>لِلدَّلَالَةِ عَلَى إِظْهَارِ التَّنْوِينِ</td></tr>
            <tr><td class="sign-symbol">ــًـ</td><td>لِلدَّلَالَةِ عَلَى الْإِدْغَامِ وَالْإِخْفَاءِ</td></tr>
            <tr><td class="sign-symbol">ــّـ</td><td>لِلدَّلَالَةِ عَلَى وُجُوبِ النُّطْقِ بِالْحَرْفِ الْمَتْرُوكِ</td></tr>
            <tr><td class="sign-symbol">س</td><td>لِلدَّلَالَةِ عَلَى وُجُوبِ النُّطْقِ بِالسِّينِ بَدَلَ الصَّادِ</td></tr>
            <tr><td class="sign-symbol">~</td><td>لِلدَّلَالَةِ عَلَى لُزُومِ الْمَدِّ الزَّائِدِ</td></tr>
            <tr><td class="sign-symbol">۩</td><td>لِلدَّلَالَةِ عَلَى مَوْضِعِ السُّجُودِ...</td></tr>
            <tr><td class="sign-symbol">۞</td><td>لِلدَّلَالَةِ عَلَى بِدَايَةِ الْأَجْزَاءِ وَالْأَحْزَابِ وَأَنْصَافِهَا وَأَرْبَاعِهَا</td></tr>
            <tr><td class="sign-symbol">۝</td><td>لِلدَّلَالَةِ عَلَى نِهَايَةِ الْآيَةِ وَرَقْمِهَا</td></tr>
        </table>
        """, unsafe_allow_html=True)

    surahs = get_surahs()
    if not surahs:
        st.error("فشل تحميل قائمة السور. يرجى التحقق من الاتصال بالإنترنت.")
        return

    current_surah_num = st.session_state.get('current_surah_num', 1)
    current_surah = next((s for s in surahs if s["number"] == current_surah_num), surahs[0])
    
    revelation_order = SURAH_REVELATION_ORDER.get(current_surah["number"], "غير متوفر")
    place = "مكية" if current_surah["revelationType"] == "Meccan" else "مدنية"
    
    with st.expander("ℹ️ معلومات السورة"):
        st.markdown(f"""
        <div class="info-box" style="margin-top: 0;">
            <div class="surah-info-item"><b>اسم السورة:</b> {current_surah["name"]} ({current_surah["englishName"]})</div>
            <div class="surah-info-item"><b>مكان النزول:</b> {place}</div>
            <div class="surah-info-item"><b>عدد الآيات:</b> {current_surah["numberOfAyahs"]}</div>
            <div class="surah-info-item"><b>ترتيب النزول الأصلي:</b> {revelation_order}</div>
        </div>
        """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        reciter_key = st.selectbox("🎙️ القارئ:", options=list(RECITERS.keys()), format_func=lambda x: RECITERS[x])
    
    with col2:
        surah_options = {s["number"]: f"{s['number']}. {s['name']} ({s['numberOfAyahs']} آية)" for s in surahs}
        selected_surah_num = st.selectbox(
            "اختر السورة:",
            options=list(surah_options.keys()),
            format_func=lambda x: surah_options[x],
            index=current_surah_num - 1
        )
        
        if selected_surah_num != st.session_state.get('current_surah_num', 1):
            st.session_state.current_surah_num = selected_surah_num
            st.session_state.current_ayah_num = 1
            st.rerun()

    with col3:
        current_surah_data = next((s for s in surahs if s["number"] == selected_surah_num), None)
        ayah_count = current_surah_data["numberOfAyahs"] if current_surah_data else 7
        
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.button("السابق (-)", key="prev_ayah", use_container_width=True):
                if st.session_state.get('current_ayah_num', 1) > 1:
                    st.session_state.current_ayah_num -= 1
                    st.rerun()
        with nav_col2:
            if st.button("التالي (+)", key="next_ayah", use_container_width=True):
                if st.session_state.get('current_ayah_num', 1) < ayah_count:
                    st.session_state.current_ayah_num += 1
                    st.rerun()

        selected_ayah_num = st.selectbox(
            "رقم الآية:",
            options=range(1, ayah_count + 1),
            index=st.session_state.get('current_ayah_num', 1) - 1,
            format_func=lambda x: f"الآية {x}"
        )
        
        if selected_ayah_num != st.session_state.get('current_ayah_num', 1):
            st.session_state.current_ayah_num = selected_ayah_num
            st.rerun()

    ayah_data = get_ayah_data(selected_surah_num, selected_ayah_num, reciter_key)
    
    if ayah_data:
        # تلوين العلامات قبل العرض
        colored_text = colorize_marks(ayah_data["text"])
        
        st.markdown(f'<div class="quran-text">{colored_text}</div>', unsafe_allow_html=True)
        
        st.markdown("### 🎧 تلاوة الآية")
        st.audio(ayah_data["audio"], format="audio/mp3")
        
        sajda_text = "لا يوجد سجدة"
        if ayah_data.get("sajda"):
            if isinstance(ayah_data["sajda"], dict):
                sajda_text = "✅ <span style='color:red;'>يوجد سجدة تلاوة (واجبة)</span>" if ayah_data["sajda"].get("obligatory") else "✅ <span style='color:red;'>يوجد سجدة تلاوة (مستحبة)</span>"
            else:
                sajda_text = "✅ <span style='color:red;'>يوجد سجدة تلاوة</span>"
        
        st.markdown(f"""
        <div class="info-box">
            <b>📌 التنبيهات:</b><br>
            <ul>
                <li><b>السجود:</b> {sajda_text}</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # ==========================================
    # قسم التتبع الصوتي الذكي (Audio-Text Sync)
    # ==========================================
    st.markdown("### 📼 السورة كاملة (مع التتبع الصوتي الذكي 🟡)")
    st.info("اضغط على زر التشغيل لبدء التلاوة، وسيتم تظليل الآية المقروءة باللون الأصفر. يمكنك الضغط على أي آية للانتقال إليها مباشرة.")
    
    revelation_sorted_surahs = []
    for surah_num in REVELATION_ORDER_LIST:
        s = next((surah for surah in surahs if surah["number"] == surah_num), None)
        if s:
            revelation_sorted_surahs.append(s)
            
    try:
        current_rev_index = next(i for i, s in enumerate(revelation_sorted_surahs) if s["number"] == selected_surah_num)
    except StopIteration:
        current_rev_index = 0

    selected_full_surah = st.selectbox(
        "القرآن بترتيب النزول:",
        options=revelation_sorted_surahs,
        format_func=lambda s: f"{SURAH_REVELATION_ORDER[s['number']]}. {s['name']} (رقم {s['number']})",
        index=current_rev_index
    )
    
    if selected_full_surah:
        with st.spinner("جاري تهيئة المشغل الذكي..."):
            ayahs_audio_data = get_surah_with_audio_array(selected_full_surah["number"], reciter_key)
            
            if ayahs_audio_data:
                js_ayahs = []
                basmalah = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"
                for i, a in enumerate(ayahs_audio_data):
                    text = a["text"]
                    if selected_full_surah["number"] != 1 and i == 0 and text.startswith(basmalah):
                        text = text[len(basmalah):].strip()
                        
                    # تلوين العلامات داخل المشغل الذكي
                    colored_text_js = colorize_marks(text)
                    js_ayahs.append({"text": colored_text_js, "audio": a["audio"], "num": a["numberInSurah"]})
                
                js_data_string = json.dumps(js_ayahs)
                
                smart_player_html = f"""
                <!DOCTYPE html>
                <html dir="rtl" lang="ar">
                <head>
                    <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@400;700&display=swap" rel="stylesheet">
                    <style>
                        body {{ 
                            font-family: 'Amiri', serif; 
                            background: #f5f7fa; 
                            padding: 20px; 
                            margin: 0;
                            border-radius: 10px; 
                        }}
                        .ayah {{ 
                            font-size: 34px; 
                            line-height: 2.4; 
                            color: #0d47a1; 
                            transition: background-color 0.3s; 
                            cursor: pointer; 
                            padding: 3px 8px; 
                            border-radius: 8px; 
                        }}
                        .ayah:hover {{ background-color: #e0e0e0; }}
                        .active {{ 
                            background-color: #FFF9C4 !important; 
                            border-bottom: 2px solid #FBC02D; 
                            color: #000;
                        }}
                        .controls {{ 
                            text-align: center; 
                            margin-bottom: 20px; 
                            position: sticky; 
                            top: 0; 
                            background: rgba(245, 247, 250, 0.95); 
                            padding: 15px; 
                            z-index: 100; 
                            border-bottom: 2px solid #ddd;
                            border-radius: 10px;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                        }}
                        button {{ 
                            font-family: 'Cairo', sans-serif; 
                            font-size: 16px; 
                            font-weight: bold;
                            padding: 10px 20px; 
                            margin: 5px; 
                            cursor: pointer; 
                            border: none; 
                            border-radius: 5px; 
                            background: #00695c; 
                            color: white; 
                            transition: 0.2s;
                        }}
                        button:hover {{ background: #004d40; transform: scale(1.05); }}
                        #status {{ display: block; margin-top: 10px; font-family: 'Cairo', sans-serif; font-size: 15px; color: #d32f2f; font-weight: bold; }}
                    </style>
                </head>
                <body>
                    <div class="controls">
                        <button id="playBtn" onclick="togglePlay()">▶ تشغيل السورة</button>
                        <button onclick="nextAyah()">⏭ الآية التالية</button>
                        <button onclick="prevAyah()">⏮ الآية السابقة</button>
                        <span id="status">جاهز للتشغيل</span>
                    </div>
                    
                    <div id="quran-container" style="text-align: justify; text-justify: inter-word;"></div>

                    <script>
                        const ayahs = {js_data_string};
                        let currentIndex = 0;
                        let audio = new Audio();
                        let isPlaying = false;

                        const container = document.getElementById('quran-container');
                        const playBtn = document.getElementById('playBtn');
                        const statusText = document.getElementById('status');

                        function toArabicNumerals(num) {{
                            const digits = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
                            return num.toString().replace(/[0-9]/g, w => digits[+w]);
                        }}

                        function renderText() {{
                            let html = '';
                            ayahs.forEach((a, i) => {{
                                html += `<span class="ayah ${{i === currentIndex ? 'active' : ''}}" id="ayah-${{i}}" onclick="playSpecific(${{i}})">${{a.text}} ﴿${{toArabicNumerals(a.num)}}﴾</span> `;
                            }});
                            container.innerHTML = html;
                            
                            const activeEl = document.getElementById(`ayah-${{currentIndex}}`);
                            if(activeEl) {{
                                activeEl.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                            }}
                        }}

                        function loadAudio() {{
                            audio.src = ayahs[currentIndex].audio;
                            audio.load();
                            renderText();
                            statusText.innerText = "🔊 جاري تلاوة الآية: " + ayahs[currentIndex].num;
                        }}

                        function togglePlay() {{
                            if (isPlaying) {{
                                audio.pause();
                                isPlaying = false;
                                playBtn.innerText = "▶ إكمال التلاوة";
                                statusText.innerText = "⏸ متوقف مؤقتاً عند الآية: " + ayahs[currentIndex].num;
                            }} else {{
                                if(!audio.src || audio.src === "") loadAudio();
                                audio.play();
                                isPlaying = true;
                                playBtn.innerText = "⏸ إيقاف مؤقت";
                            }}
                        }}

                        function playSpecific(index) {{
                            currentIndex = index;
                            loadAudio();
                            audio.play();
                            isPlaying = true;
                            playBtn.innerText = "⏸ إيقاف مؤقت";
                        }}

                        function nextAyah() {{
                            if (currentIndex < ayahs.length - 1) {{
                                currentIndex++;
                                loadAudio();
                                if(isPlaying) audio.play();
                            }}
                        }}

                        function prevAyah() {{
                            if (currentIndex > 0) {{
                                currentIndex--;
                                loadAudio();
                                if(isPlaying) audio.play();
                            }}
                        }}

                        audio.onended = function() {{
                            if (currentIndex < ayahs.length - 1) {{
                                currentIndex++;
                                loadAudio();
                                audio.play();
                            }} else {{
                                isPlaying = false;
                                playBtn.innerText = "▶ إعادة التشغيل";
                                statusText.innerText = "✅ انتهت السورة";
                                currentIndex = 0;
                                renderText(); 
                            }}
                        }};
                        
                        audio.onwaiting = function() {{ statusText.innerText = "⏳ جاري التحميل..."; }};
                        audio.onerror = function() {{ statusText.innerText = "❌ خطأ في تحميل الصوت. تأكد من الإنترنت."; }};

                        renderText();
                    </script>
                </body>
                </html>
                """
                
                components.html(smart_player_html, height=750, scrolling=True)

    st.markdown("---")
    st.markdown("### 📄 تحميل السورة (PDF)")
    
    pdf_key = f"pdf_v3_{selected_surah_num}"
    
    if pdf_key not in st.session_state:
        st.info("اضغط على الزر أدناه لتجهيز ملف PDF (نسخة طباعة: أبيض وأسود، بدون زخارف).")
        if st.button("📥 تجهيز ملف PDF"):
            with st.spinner("جاري إعداد الملف..."):
                s_name_pdf, s_text_pdf = get_full_surah_text(selected_surah_num)
                if s_name_pdf and s_text_pdf:
                    pdf_data = create_pdf(s_name_pdf, s_text_pdf)
                    st.session_state[pdf_key] = pdf_data
                    st.rerun()
    else:
        st.success("ملف PDF جاهز للتحميل!")
        col_dl_1, col_dl_2 = st.columns([1, 1])
        with col_dl_1:
            st.download_button(
                label="⬇️ تحميل ملف PDF",
                data=st.session_state[pdf_key],
                file_name=f"Surah_{selected_surah_num}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col_dl_2:
            if st.button("🔄 إعادة التجهيز", use_container_width=True):
                del st.session_state[pdf_key]
                st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; margin-top: 20px;'>
            © 2026 Developed by boood0003<br>
            <a href="https://analyzer-a.com" target="_blank" style="color: #0d47a1; text-decoration: none;">https://analyzer-a.com</a>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()