import streamlit as st
import requests
import os
import io
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

# تنسيق CSS مخصص لدعم اللغة العربية والاتجاه من اليمين لليسار
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stSelectbox, .stNumberInput {
        direction: rtl;
    }
    
    .quran-text {
        font-family: 'Amiri', serif;
        font-size: 32px;
        color: #0d47a1;
        text-align: center;
        background-color: #f5f7fa;
        padding: 25px;
        border-radius: 12px;
        margin: 20px 0;
        border: 1px solid #e3e6e8;
        line-height: 2.0;
    }
    
    .info-box {
        background-color: #e0f2f1;
        border-right: 6px solid #00695c;
        padding: 15px;
        border-radius: 8px;
        margin-top: 15px;
        font-size: 16px;
    }
    
    .tafsir-box {
        background-color: #fff9c4;
        border-right: 6px solid #fbc02d;
        padding: 20px;
        border-radius: 8px;
        margin-top: 15px;
        font-size: 18px;
        line-height: 1.8;
    }
    
    /* تعديل اتجاه القائمة الجانبية والعناصر */
    .css-16idsys p {
        text-align: right;
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

FULL_SURAH_URLS = {
    "ar.minshawi": "https://server10.mp3quran.net/minsh/",
    "ar.husary": "https://server13.mp3quran.net/husr/",
    "ar.parhizgar": "https://tanzil.net/res/audio/parhizgar/"
}

RECITERS = {
    "ar.minshawi": "الشيخ محمد صديق المنشاوي",
    "ar.husary": "الشيخ محمود خليل الحصري",
    "ar.parhizgar": "القارئ شهريار برهيزقار"
}

# دوال مساعدة
@st.cache_data
def get_surahs():
    try:
        response = requests.get("http://api.alquran.cloud/v1/surah")
        if response.status_code == 200:
            return response.json()["data"]
        return []
    except:
        return []

def get_ayah_data(surah_num, ayah_num, reciter_id):
    try:
        urls = [
            f"http://api.alquran.cloud/v1/ayah/{surah_num}:{ayah_num}/{reciter_id}",
            f"http://api.alquran.cloud/v1/ayah/{surah_num}:{ayah_num}/ar.muyassar"
        ]
        
        # لا يمكن استخدام Promise.all هنا، نقوم بطلبات متتالية أو متوازية بسيطة
        ayah_res = requests.get(urls[0]).json()
        tafsir_res = requests.get(urls[1]).json()
        
        if ayah_res["code"] == 200 and tafsir_res["code"] == 200:
            data = ayah_res["data"]
            # معالجة البسملة في العرض: حذفها من النص للآية الأولى (ما عدا الفاتحة)
            if surah_num != 1 and ayah_num == 1:
                basmalah = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"
                if data["text"].startswith(basmalah):
                     data["text"] = data["text"][len(basmalah):].strip()
            
            return data, tafsir_res["data"]
        return None, None
    except Exception:
        # حل مشكلة سورة الفاتحة الآية 1 (البسملة) في حال فشل الاتصال
        if surah_num == 1 and ayah_num == 1:
            fallback_ayah = {
                "number": 1,
                "text": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
                "audio": f"https://cdn.islamic.network/quran/audio/128/{reciter_id}/1.mp3",
                "numberInSurah": 1,
                "juz": 1,
                "manzil": 1,
                "page": 1,
                "ruku": 1,
                "hizbQuarter": 1,
                "sajda": False
            }
            fallback_tafsir = {
                "text": "سورة الفاتحة سميت هذه السورة بالفاتحة؛ لأنه يفتتح بها القرآن العظيم، وتسمى المثاني؛ لأنها تقرأ في كل ركعة، ولها أسماء أخر. أبتدئ قراءة القرآن باسم الله مستعينا به، (اللهِ) علم على الرب -تبارك وتعالى- المعبود بحق دون سواه، وهو أخص أسماء الله تعالى، ولا يسمى به غيره سبحانه. (الرَّحْمَنِ) ذي الرحمة العامة الذي وسعت رحمته جميع الخلق، (الرَّحِيمِ) بالمؤمنين، وهما اسمان من أسماء الله تعالى، يتضمنان إثبات صفة الرحمة لله تعالى كما يليق بجلاله."
            }
            return fallback_ayah, fallback_tafsir
            
        return None, None

def analyze_marks(text):
    marks = []
    if "ۖ" in text: marks.append("<b>ۖ (صلى):</b> الوصل أولى (الاستمرارية أفضل مع جواز الوقف)")
    if "ۗ" in text: marks.append("<b>ۗ (قلى):</b> الوقف أولى (الوقف أفضل مع جواز الوصل)")
    if "ۘ" in text: marks.append("<b>ۘ (مـ):</b> وقف لازم (يجب الوقف)")
    if "ۙ" in text: marks.append("<b>ۙ (لا):</b> لا تقف (يجب الوصل)")
    if "ۚ" in text: marks.append("<b>ۚ (ج):</b> وقف جائز (يستوي الوقف والوصل)")
    if "ۛ" in text: marks.append("<b>ۛ (∴):</b> وقف تعانق (قف على أحد الموضعين ولا تقف على الآخر)")
    return marks

def ensure_font_exists():
    font_path = "Amiri-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(response.content)
            else:
                st.error("فشل تحميل ملف الخط.")
        except Exception as e:
            st.error(f"حدث خطأ أثناء تحميل الخط: {e}")
    return font_path

def to_arabic_numerals(n):
    digits = {'0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤', '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'}
    return "".join([digits[d] for d in str(n)])

@st.cache_data
def get_full_surah_text(surah_num):
    try:
        response = requests.get(f"http://api.alquran.cloud/v1/surah/{surah_num}/quran-simple")
        if response.status_code == 200:
            data = response.json()["data"]
            ayahs = []
            
            # معالجة البسملة: حذفها من بداية الآية الأولى لكل السور ما عدا الفاتحة (رقم 1)
            if surah_num != 1 and len(data["ayahs"]) > 0:
                first_ayah_text = data["ayahs"][0]['text']
                basmalah = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
                if first_ayah_text.startswith(basmalah):
                    # حذف البسملة وتنظيف المسافات الزائدة
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
    
    # Title
    c.setFont('Amiri', 24)
    reshaped_title = arabic_reshaper.reshape(f"سورة {surah_name}")
    bidi_title = get_display(reshaped_title)
    c.drawCentredString(width / 2, height - 3 * cm, bidi_title)
    
    # Text Configuration
    c.setFont('Amiri', 16)
    y_position = height - 5 * cm
    margin = 2 * cm
    line_height = 0.8 * cm
    max_width = width - 2 * margin
    
    # Processing Text
    words = surah_text.split()
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        
        # Check width
        reshaped_line = arabic_reshaper.reshape(line_str)
        bidi_line = get_display(reshaped_line)
        text_width = c.stringWidth(bidi_line, 'Amiri', 16)
        
        if text_width > max_width:
            # Line too long, remove last word and print
            current_line.pop()
            
            # Print current line
            line_str = " ".join(current_line)
            reshaped_line = arabic_reshaper.reshape(line_str)
            bidi_line = get_display(reshaped_line)
            c.drawRightString(width - margin, y_position, bidi_line)
            
            y_position -= line_height
            current_line = [word]
            
            # New Page Check
            if y_position < margin:
                c.showPage()
                c.setFont('Amiri', 16)
                y_position = height - margin
    
    # Print last line
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

    # تحميل البيانات
    surahs = get_surahs()
    if not surahs:
        st.error("فشل تحميل قائمة السور. يرجى التحقق من الاتصال بالإنترنت.")
        return

    # معلومات السورة (في الأعلى بدلاً من القائمة الجانبية)
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

    # لوحة التحكم الرئيسية
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        reciter_key = st.selectbox("🎙️ القارئ:", options=list(RECITERS.keys()), format_func=lambda x: RECITERS[x])
    
    with col2:
        # إنشاء قائمة السور للعرض
        surah_options = {s["number"]: f"{s['number']}. {s['name']} ({s['numberOfAyahs']} آية)" for s in surahs}
        selected_surah_num = st.selectbox(
            "اختر السورة:",
            options=list(surah_options.keys()),
            format_func=lambda x: surah_options[x],
            index=current_surah_num - 1
        )
        
        # تحديث السورة الحالية في الجلسة
        if selected_surah_num != st.session_state.get('current_surah_num', 1):
            st.session_state.current_surah_num = selected_surah_num
            st.session_state.current_ayah_num = 1 # إعادة تعيين الآية للأولى
            st.rerun()

    with col3:
        # اختيار الآية
        current_surah_data = next((s for s in surahs if s["number"] == selected_surah_num), None)
        ayah_count = current_surah_data["numberOfAyahs"] if current_surah_data else 7
        
        # أزرار التنقل بين الآيات
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

    # زر العرض (في ستريم ليت التحديث فوري، لكن يمكن وضع زر للتأكيد أو جلب البيانات)
    # سنجلب البيانات مباشرة عند التغيير لسرعة الاستجابة
    
    ayah_data, tafsir_data = get_ayah_data(selected_surah_num, selected_ayah_num, reciter_key)
    
    if ayah_data and tafsir_data:
        # عرض النص القرآني
        st.markdown(f'<div class="quran-text">{ayah_data["text"]}</div>', unsafe_allow_html=True)
        
        # مشغل الصوت للآية
        st.markdown("### 🎧 تلاوة الآية")
        st.audio(ayah_data["audio"], format="audio/mp3")
        
        # صندوق المعلومات (علامات الوقف والسجود)
        sajda_text = "لا يوجد سجدة"
        if ayah_data.get("sajda"):
            if isinstance(ayah_data["sajda"], dict):
                sajda_text = "✅ يوجد سجدة تلاوة (واجبة)" if ayah_data["sajda"].get("obligatory") else "✅ يوجد سجدة تلاوة (مستحبة)"
            else:
                sajda_text = "✅ يوجد سجدة تلاوة"

        marks = analyze_marks(ayah_data["text"])
        marks_html = "".join([f"<li>{m}</li>" for m in marks]) if marks else "<li>لا توجد علامات وقف خاصة في هذه الآية.</li>"
        
        st.markdown(f"""
        <div class="info-box">
            <b>📌 علامات القراءة (الوقف، السجود، الاستمرارية):</b><br>
            <ul>
                <li><b>السجود:</b> {sajda_text}</li>
            </ul>
            <b>علامات الوقف في الآية:</b>
            <ul>{marks_html}</ul>
        </div>
        """, unsafe_allow_html=True)
        
        # التفسير
        st.markdown("### 📚 التفسير الميسر")
        st.markdown(f'<div class="tafsir-box">{tafsir_data["text"]}</div>', unsafe_allow_html=True)
        


    st.markdown("---")
    
    # قسم السورة الكاملة
    st.markdown("### 📼 السورة كاملة")
    
    # تحضير قائمة السور حسب ترتيب النزول
    revelation_sorted_surahs = []
    for surah_num in REVELATION_ORDER_LIST:
        s = next((surah for surah in surahs if surah["number"] == surah_num), None)
        if s:
            revelation_sorted_surahs.append(s)
            
    # اختيار السورة الكاملة (افتراضياً نفس السورة المختارة بالأعلى)
    # نحتاج للبحث عن index السورة الحالية في القائمة المرتبة حسب النزول
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
        full_url_base = FULL_SURAH_URLS[reciter_key]
        formatted_surah_num = str(selected_full_surah["number"]).zfill(3)
        full_audio_url = f"{full_url_base}{formatted_surah_num}.mp3"
        
        st.audio(full_audio_url, format="audio/mp3")

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
