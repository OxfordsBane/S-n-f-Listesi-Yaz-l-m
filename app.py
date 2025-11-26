import streamlit as st
import pandas as pd
import io
import xlsxwriter
import random

# Sayfa Ayarları
st.set_page_config(page_title="Hazırlık Sınıf Dağıtım Otomasyonu", layout="wide")

st.title("🇬🇧 İngilizce Hazırlık Sınıf Atama Sistemi")
st.markdown("""
Bu sistem, yüklenen öğrenci listesini belirtilen kriterlere (Modül Durumu, Uyruk) göre
eşit ve adil bir şekilde sınıflara dağıtır.
""")

# --- 1. ŞABLON İNDİRME BÖLÜMÜ ---
st.subheader("1. Veri Hazırlığı")
st.info("Lütfen aşağıdaki şablona uygun bir Excel dosyası hazırlayın. Sütun isimleri birebir aynı olmalıdır.")

# Örnek veri oluşturma
example_data = {
    'Öğrenci No': [23001, 23002, 23003, 23004],
    'Ad': ['Ahmet', 'Ayşe', 'John', 'Fatma'],
    'Soyad': ['Yılmaz', 'Demir', 'Doe', 'Kaya'],
    'Seviyesi': ['A1', 'A1', 'A2', 'B1'],
    'Uyruk': ['ÖSYM', 'ÖSYM', 'YÖS', 'ÖSYM'],
    'Modül Durumu': ['A', 'F', 'Placement', 'B'] 
}
df_example = pd.DataFrame(example_data)

# Şablonu Excel'e çevirme fonksiyonu
def to_excel_template(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Veri_Sablonu')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

template_file = to_excel_template(df_example)

st.download_button(
    label="📥 Boş Excel Şablonunu İndir",
    data=template_file,
    file_name='Sinif_Atama_Sablonu.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# --- 2. DOSYA YÜKLEME ---
st.subheader("2. Öğrenci Listesini Yükle")
uploaded_file = st.file_uploader("Excel dosyasını buraya sürükleyin", type=['xlsx'])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Sütun kontrolü
        required_columns = ['Seviyesi', 'Öğrenci No', 'Ad', 'Soyad', 'Uyruk', 'Modül Durumu']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"Hata: Excel dosyasında şu sütunlar eksik: {', '.join(missing_columns)}")
            st.stop()
            
        st.success(f"Toplam {len(df)} öğrenci kaydı başarıyla yüklendi.")
        
        # Seviyeleri tespit et
        levels = sorted(df['Seviyesi'].unique())
        st.write(f"Tespit edilen seviyeler: {', '.join(levels)}")
        
        # --- 3. PARAMETRE AYARLARI ---
        st.subheader("3. Sınıf ve Kapasite Ayarları")
        
        config = {} # Ayarları tutacak sözlük
        
        # Her seviye için ayar kutusu oluştur
        for level in levels:
            student_count_in_level = len(df[df['Seviyesi'] == level])
            with st.expander(f"🎚️ {level} Seviyesi Ayarları (Toplam Öğrenci: {student_count_in_level})", expanded=True):
                
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    num_classes = st.number_input(
                        f"{level} için Sınıf Sayısı", 
                        min_value=1, value=1, step=1, 
                        key=f"num_{level}"
                    )
                
                with col2:
                    st.write("Sınıf Kapasiteleri:")
                    cols = st.columns(min(num_classes, 5)) # Yan yana en fazla 5 kutu
                    
                    level_caps = []
                    for i in range(num_classes):
                        # Sınıf ismi oluştur (Örn: A1.01)
                        class_name = f"{level}.{i+1:02d}"
                        
                        # Dinamik sütun yönetimi
                        with cols[i % 5]:
                            cap = st.number_input(
                                f"{class_name} Kap.", 
                                min_value=1, value=20, step=1, 
                                key=f"cap_{level}_{i}"
                            )
                            level_caps.append({'name': class_name, 'cap': cap})
                    
                    config[level] = level_caps
                    
                    # Kapasite Kontrolü ve Uyarı
                    total_cap = sum([c['cap'] for c in level_caps])
                    if total_cap < student_count_in_level:
                        st.warning(f"⚠️ DİKKAT: {level} seviyesinde toplam öğrenci ({student_count_in_level}), toplam kapasiteden ({total_cap}) fazla! Fazla öğrenciler yine de eşit dağıtılacak.")
                    else:
                        st.caption(f"Yeterli kapasite. (Öğrenci: {student_count_in_level} / Kapasite: {total_cap})")

        # --- 4. DAĞITIM MOTORU ---
        if st.button("🚀 Sınıfları Oluştur ve Dağıt", type="primary"):
            
            output_buffer = io.BytesIO()
            workbook = xlsxwriter.Workbook(output_buffer, {'in_memory': True})
            
            # Raporlama için loglar
            logs = []
            
            for level in levels:
                level_data = df[df['Seviyesi'] == level].copy()
                classes_cfg = config[level]
                
                # Sınıf havuzlarını oluştur
                # classes yapısı: { 'A1.01': [], 'A1.02': [] }
                class_buckets = {c['name']: [] for c in classes_cfg}
                class_names = [c['name'] for c in classes_cfg]
                
                # GRUPLANDIRMA VE DAĞITIM STRATEJİSİ
                # Adil dağıtım için veriyi 'Modül Durumu' ve 'Uyruk'a göre grupluyoruz.
                # Örn: (A, YÖS), (A, ÖSYM), (F, ÖSYM), (Ghost, YÖS)...
                # Bu grupların her birini kendi içinde karıştırıp sınıflara sırayla (Round Robin) dağıtacağız.
                
                groups = level_data.groupby(['Modül Durumu', 'Uyruk'])
                
                # Dağıtım sırası için pointer
                current_class_idx = 0
                
                for _, group_df in groups:
                    # Grup içindeki öğrencileri karıştır (Rastgelelik için)
                    shuffled_students = group_df.sample(frac=1, random_state=42).reset_index(drop=True)
                    
                    for _, student in shuffled_students.iterrows():
                        target_class = class_names[current_class_idx]
                        
                        # Öğrenciyi sözlük formatında listeye ekle
                        class_buckets[target_class].append(student)
                        
                        # Bir sonraki sınıfa geç (Döngüsel)
                        current_class_idx = (current_class_idx + 1) % len(class_names)
                
                # --- EXCEL SAYFALARINI OLUŞTURMA ---
                for c_name in class_names:
                    students_in_class = class_buckets[c_name]
                    df_class = pd.DataFrame(students_in_class)
                    
                    # Eğer sınıf boşsa boş dataframe oluştur
                    if df_class.empty:
                        df_class = pd.DataFrame(columns=df.columns)
                    else:
                        # Orijinal sütun sırasını koru
                        df_class = df_class[df.columns]
                    
                    # Excel'e yaz
                    worksheet = workbook.add_worksheet(c_name)
                    
                    # Başlıkları yaz
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
                    for col_num, value in enumerate(df_class.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                        
                    # Verileri yaz
                    for row_num, row_data in enumerate(df_class.values):
                        for col_num, value in enumerate(row_data):
                            worksheet.write(row_num + 1, col_num, value)
                            
                    # Sütun genişliklerini ayarla (Otomatik gibi)
                    worksheet.set_column(0, len(df_class.columns) - 1, 15)
                    
                    # Log tut
                    logs.append(f"{c_name} oluşturuldu. Mevcut: {len(df_class)}")

            workbook.close()
            
            # --- SONUÇ GÖSTERİMİ ---
            st.success("✅ Dağıtım tamamlandı!")
            
            # Raporu göster
            with st.expander("Dağıtım Detayları"):
                for log in logs:
                    st.text(log)
            
            # İndirme Butonu
            st.download_button(
                label="📥 Oluşturulan Sınıf Listelerini İndir (Excel)",
                data=output_buffer.getvalue(),
                file_name='Hazirlik_Sinif_Listeleri.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
    except Exception as e:
        st.error(f"Bir hata oluştu: {e}")
        st.error("Lütfen yüklediğiniz Excel dosyasının formatını kontrol edin.")
