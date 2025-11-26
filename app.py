import streamlit as st
import pandas as pd
import io
import xlsxwriter

# Sayfa Ayarları
st.set_page_config(page_title="Hazırlık Sınıf Dağıtım", layout="wide")

st.title("🇬🇧 İngilizce Hazırlık Sınıf Atama Sistemi")

# --- TANIMLAR ---
# Kur sıralaması (Terfi mantığı için gereklidir)
LEVEL_ORDER = ["A1", "A2", "B1", "B2"]
PASS_GRADES = ['A', 'B', 'C'] # Bir üst kura geçiren notlar
FAIL_GRADES = ['F', 'GHOST']   # Tekrar ettiren notlar
# Placement: Olduğu seviyede başlatır.

# --- 1. ŞABLON İNDİRME ---
st.markdown("### 1. Adım: Veri Şablonu")
st.info("Ayarların açılması için önce aşağıdaki şablona uygun listenizi yüklemeniz gerekmektedir.")

# Örnek veri
example_data = {
    'Öğrenci No': [23001, 23002, 23003, 23004, 23005],
    'Ad': ['Ahmet', 'Ayşe', 'John', 'Fatma', 'Mehmet'],
    'Soyad': ['Yılmaz', 'Demir', 'Doe', 'Kaya', 'Çelik'],
    'Seviyesi': ['A1', 'A1', 'B1', 'B1', 'A2'],
    'Uyruk': ['ÖSYM', 'ÖSYM', 'YÖS', 'ÖSYM', 'ÖSYM'],
    'Modül Durumu': ['A', 'F', 'B', 'Ghost', 'Placement'] 
}
df_example = pd.DataFrame(example_data)

def to_excel_template(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Veri_Sablonu')
    writer.close()
    return output.getvalue()

template_file = to_excel_template(df_example)

st.download_button(
    label="📥 Boş Excel Şablonunu İndir",
    data=template_file,
    file_name='Sinif_Atama_Sablonu.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

st.divider()

# --- 2. DOSYA YÜKLEME ---
st.markdown("### 2. Adım: Listenizi Yükleyin")
uploaded_file = st.file_uploader("Excel dosyasını buraya yükleyin (Sürükle-Bırak)", type=['xlsx'])

if uploaded_file is not None:
    try:
        # Excel'i oku
        df = pd.read_excel(uploaded_file)
        
        # Temizlik
        df.columns = df.columns.str.strip()
        required_columns = ['Seviyesi', 'Öğrenci No', 'Ad', 'Soyad', 'Uyruk', 'Modül Durumu']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"❌ HATA: Eksik sütunlar: {', '.join(missing_columns)}")
            st.stop()
            
        # Veri Standartlaştırma
        df['Seviyesi'] = df['Seviyesi'].astype(str).str.strip().str.upper()
        df['Modül Durumu'] = df['Modül Durumu'].astype(str).str.strip() # Harf duyarlılığı için upper yapmıyoruz, aşağıda kontrol edeceğiz.
        df['Uyruk'] = df['Uyruk'].astype(str).str.strip()
        df = df[df['Seviyesi'] != 'NAN']

        # --- KUR ATLAMA MANTIĞI (LEVEL UP LOGIC) ---
        # Öğrencinin 'Seviyesi' ve 'Modül Durumu'na bakarak 'Hedef_Seviye'yi belirle
        
        target_levels = []
        
        for index, row in df.iterrows():
            current_lvl = row['Seviyesi']
            grade = row['Modül Durumu']
            
            # Not kontrolü (Büyük/küçük harf duyarsız yapalım)
            grade_upper = grade.upper()
            
            final_lvl = current_lvl # Varsayılan: Değişmez
            
            if grade_upper in PASS_GRADES:
                # Başarılı ise bir üst kura geç
                if current_lvl in LEVEL_ORDER:
                    current_idx = LEVEL_ORDER.index(current_lvl)
                    if current_idx < len(LEVEL_ORDER) - 1:
                        final_lvl = LEVEL_ORDER[current_idx + 1]
                    else:
                        final_lvl = current_lvl + " (Mezun?)" # Liste dışı durum
                else:
                    final_lvl = current_lvl # Tanımsız seviye ise kalır
            
            # F, GHOST veya PLACEMENT ise seviye değişmez (Current Level kalır)
            # Not: Placement genelde başlayacağı kura yerleştirildiği için değişmez kabul ettik.
            
            target_levels.append(final_lvl)

        # Yeni hesaplanan seviyeyi dataframe'e ekle
        df['Atanacak_Seviye'] = target_levels

        # Artık ayarları 'Seviyesi'ne göre değil, hesaplanan 'Atanacak_Seviye'ye göre yapacağız
        active_levels = sorted(df['Atanacak_Seviye'].unique())
        
        st.success(f"✅ Dosya işlendi. Kur atlama kuralları uygulandı.")
        st.info(f"Oluşacak Sınıf Seviyeleri: {', '.join(active_levels)}")
        
        st.divider()

        # --- 3. PARAMETRE AYARLARI ---
        st.markdown("### 3. Adım: Sınıf Kontenjan Ayarları")
        
        config = {} 
        
        with st.form("settings_form"):
            for level in active_levels:
                # O seviyeye atanacak öğrencileri filtrele (Eski seviyesine göre değil!)
                students_in_target = df[df['Atanacak_Seviye'] == level]
                count = len(students_in_target)
                
                st.markdown(f"**🎚️ {level} Sınıfları** (Atanacak Öğrenci: {count})")
                
                c1, c2 = st.columns([1, 4])
                with c1:
                    num_classes = st.number_input(
                        f"{level} Sınıf Adedi", 
                        min_value=1, value=1, step=1, 
                        key=f"num_{level}"
                    )
                
                with c2:
                    st.write(f"{level} Kapasiteleri:")
                    cols = st.columns(min(num_classes, 6))
                    
                    level_caps = []
                    for i in range(num_classes):
                        class_name = f"{level}.{i+1:02d}"
                        with cols[i % 6]:
                            cap = st.number_input(
                                f"{class_name}", 
                                min_value=1, value=20, step=1, 
                                key=f"cap_{level}_{i}"
                            )
                            level_caps.append({'name': class_name, 'cap': cap})
                    
                    config[level] = level_caps
                st.markdown("---")
            
            submitted = st.form_submit_button("💾 Listeleri Oluştur", type="primary")

        # --- 4. DAĞITIM MOTORU ---
        if submitted:
            output_buffer = io.BytesIO()
            workbook = xlsxwriter.Workbook(output_buffer, {'in_memory': True})
            logs = []
            
            for level in active_levels:
                # O seviyeye GİDECEK öğrencileri al
                level_data = df[df['Atanacak_Seviye'] == level].copy()
                classes_cfg = config[level]
                
                # Kapasite Kontrolü
                total_cap = sum([c['cap'] for c in classes_cfg])
                if total_cap < len(level_data):
                    st.warning(f"⚠️ {level} seviyesinde {len(level_data)} öğrenci var ama kapasite {total_cap}. Fazlalıklar dağıtılıyor.")

                class_buckets = {c['name']: [] for c in classes_cfg}
                class_names = [c['name'] for c in classes_cfg]
                
                # Gruplandır ve Dağıt
                groups = level_data.groupby(['Modül Durumu', 'Uyruk'])
                current_class_idx = 0
                
                for _, group_df in groups:
                    shuffled_students = group_df.sample(frac=1, random_state=42).reset_index(drop=True)
                    for _, student in shuffled_students.iterrows():
                        target_class = class_names[current_class_idx]
                        class_buckets[target_class].append(student)
                        current_class_idx = (current_class_idx + 1) % len(class_names)
                
                # Excel'e Yazma
                for c_name in class_names:
                    students_in_class = class_buckets[c_name]
                    df_class = pd.DataFrame(students_in_class)
                    
                    if df_class.empty:
                        df_class = pd.DataFrame(columns=df.columns)
                    else:
                        # Çıktıda 'Atanacak_Seviye' sütununu göstermeye gerek yok, veya isteğe bağlı.
                        # Orijinal sütunları koruyalım + Atanan sınıfı ekleyebiliriz ama ayrı sayfa istedin.
                        cols_to_show = ['Seviyesi', 'Öğrenci No', 'Ad', 'Soyad', 'Uyruk', 'Modül Durumu']
                        df_class = df_class[cols_to_show]
                    
                    worksheet = workbook.add_worksheet(c_name)
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
                    
                    for col_num, value in enumerate(df_class.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                        
                    for row_num, row_data in enumerate(df_class.values):
                        for col_num, value in enumerate(row_data):
                            worksheet.write(row_num + 1, col_num, value) # type: ignore
                            
                    worksheet.set_column(0, len(df_class.columns) - 1, 15)
                    logs.append(f"✅ {c_name} sınıfı oluşturuldu. Mevcut: {len(df_class)}")

            workbook.close()
            
            st.success("Tüm dağıtım işlemleri tamamlandı!")
            with st.expander("Detaylı Rapor"):
                for log in logs:
                    st.text(log)
            
            st.download_button(
                label="📥 HAZIR LİSTELERİ İNDİR (Excel)",
                data=output_buffer.getvalue(),
                file_name='Hazirlik_Sinif_Listeleri.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
    except Exception as e:
        st.error(f"Beklenmeyen bir hata oluştu: {e}")
