import streamlit as st
import pandas as pd
import io
import xlsxwriter
import math

# Sayfa Ayarları
st.set_page_config(page_title="Hazırlık Sınıf Dağıtım", layout="wide")

st.title("🇬🇧 İngilizce Hazırlık Sınıf Atama Sistemi")

# --- SESSION STATE (HAFIZA) ---
if 'generated_lists' not in st.session_state:
    st.session_state['generated_lists'] = None
if 'generated_db' not in st.session_state:
    st.session_state['generated_db'] = None
if 'process_logs' not in st.session_state:
    st.session_state['process_logs'] = []

# --- TANIMLAR ---
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "PreFaculty"]
PASS_GRADES = ['A', 'B', 'C']
FAIL_GRADES = ['F', 'GHOST']

# --- 1. GENEL AYARLAR ---
st.sidebar.header("⚙️ Dönem Ayarları")
st.sidebar.info("İkinci Excel çıktısı için bu bilgileri giriniz.")
academic_year = st.sidebar.text_input("Akademik Yıl", value="2025-2026")
module_no = st.sidebar.selectbox("Kaçıncı Modül", options=[1, 2, 3, 4, 5], index=0)

if module_no == 1:
    st.sidebar.success("✅ 1. Modül seçildi: 'Modül Durumu' boş bırakılan öğrenciler, belirtilen seviyeye doğrudan yerleştirilecek.")

# --- 2. ŞABLON OLUŞTURMA FONKSİYONU ---
def create_template_with_help():
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # 1. Sayfa: Veri Şablonu
    example_data = {
        'Öğrenci No': [23001, 23002, 23003, 23004, 23005],
        'Ad': ['Ahmet', 'Ayşe', 'John', 'Fatma', 'Ali'],
        'Soyad': ['Yılmaz', 'Demir', 'Doe', 'Kaya', 'Can'],
        'Seviyesi': ['A1', 'A1', 'B1', 'A2', 'A2'],
        'Uyruk': ['ÖSYM', 'ÖSYM', 'YÖS', 'ÖSYM', 'ÖSYM'],
        'Modül Durumu': ['A', 'F', 'B', 'Placement', 'Ghost'] 
    }
    df_ex = pd.DataFrame(example_data)
    df_ex.to_excel(writer, index=False, sheet_name='Veri_Sablonu')
    
    # 2. Sayfa: NASIL KULLANILIR
    workbook = writer.book
    ws_help = workbook.add_worksheet('NASIL_KULLANILIR')
    
    # Formatlar
    fmt_title = workbook.add_format({'bold': True, 'font_size': 14, 'color': 'blue'})
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#f0f0f0', 'border': 1})
    fmt_text = workbook.add_format({'text_wrap': True, 'valign': 'top'})
    
    # Başlık
    ws_help.write('A1', 'SİSTEM KULLANIM KILAVUZU', fmt_title)
    
    headers = ['Sütun Adı', 'Açıklama ve Kurallar']
    ws_help.write('A3', headers[0], fmt_head)
    ws_help.write('B3', headers[1], fmt_head)
    
    instructions = [
        ['Öğrenci No', 'Öğrencinin okul numarasıdır. Mükerrer olmamalıdır.'],
        ['Ad / Soyad', 'Öğrencinin kimlik bilgileri.'],
        ['Seviyesi', 'Öğrencinin OKUDUĞU (Eski) seviye. Örn: A1, A2...'],
        ['Uyruk', '"ÖSYM" veya "YÖS" olarak belirtilmelidir.'],
        ['Modül Durumu', 'Not bilgisi:\n- A, B, C: Başarılı (Bir üst kura geçer).\n- F: Başarısız (Aynı kurda kalır).\n- Ghost: Devamsız (Aynı kurda kalır).\n- Placement: Yerleşti (Kurda başlar).\n- (Boş): Sadece 1. Modülde kullanılabilir.']
    ]
    
    row = 3
    for item in instructions:
        ws_help.write(row, 0, item[0], fmt_text)
        ws_help.write(row, 1, item[1], fmt_text)
        row += 1
        
    ws_help.set_column(0, 0, 20)
    ws_help.set_column(1, 1, 60)
    writer.close()
    return output.getvalue()

# --- ŞABLON İNDİRME ---
st.markdown("### 1. Adım: Veri Şablonu")
st.info("Sütun açıklamaları için Excel'deki 'NASIL_KULLANILIR' sekmesine bakabilirsiniz.")

template_file = create_template_with_help()

st.download_button(
    label="📥 Excel Şablonunu ve Kılavuzu İndir",
    data=template_file,
    file_name='Sinif_Atama_Sablonu_v3.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

st.divider()

# --- 3. DOSYA YÜKLEME ---
st.markdown("### 2. Adım: Listenizi Yükleyin")
uploaded_file = st.file_uploader("Excel dosyasını buraya yükleyin", type=['xlsx'], key="file_uploader")

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Temizlik
        df.columns = df.columns.str.strip()
        required_columns = ['Seviyesi', 'Öğrenci No', 'Ad', 'Soyad', 'Uyruk']
        if 'Modül Durumu' not in df.columns:
             st.error("❌ HATA: 'Modül Durumu' sütunu Excel'de bulunamadı.")
             st.stop()
             
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ HATA: Eksik sütunlar: {', '.join(missing_columns)}")
            st.stop()
            
        # Mükerrer Kontrolü
        duplicates = df[df.duplicated('Öğrenci No', keep=False)]
        if not duplicates.empty:
            st.error("⚠️ DİKKAT: Listede aynı numaraya sahip birden fazla kayıt bulundu!")
            st.dataframe(duplicates.sort_values('Öğrenci No'), use_container_width=True)
            st.warning("Lütfen Excel dosyanızı düzeltip tekrar yükleyin.")

        # Modül 1 Mantığı
        if module_no == 1:
            df['Modül Durumu'] = df['Modül Durumu'].fillna('Baslangic')
            df.loc[df['Modül Durumu'].astype(str).str.strip() == '', 'Modül Durumu'] = 'Baslangic'
        else:
            df['Modül Durumu'] = df['Modül Durumu'].fillna('Bilinmiyor')

        # Veri İşleme
        df['Seviyesi'] = df['Seviyesi'].astype(str).str.strip()
        level_map = {l.upper(): l for l in LEVEL_ORDER} 
        
        def normalize_level(val):
            val_upper = val.upper()
            if val_upper in level_map:
                return level_map[val_upper]
            return val_upper 
            
        df['Seviyesi'] = df['Seviyesi'].apply(normalize_level)
        df['Modül Durumu'] = df['Modül Durumu'].astype(str).str.strip()
        df['Uyruk'] = df['Uyruk'].astype(str).str.strip()
        df = df[df['Seviyesi'] != 'NAN']

        # Kur Atlama
        target_levels = []
        for index, row in df.iterrows():
            current_lvl = row['Seviyesi']
            grade = row['Modül Durumu'].upper()
            final_lvl = current_lvl 
            
            if grade in PASS_GRADES:
                if current_lvl in LEVEL_ORDER:
                    current_idx = LEVEL_ORDER.index(current_lvl)
                    if current_idx < len(LEVEL_ORDER) - 1:
                        final_lvl = LEVEL_ORDER[current_idx + 1]
                    else:
                        final_lvl = "Mezun/Fakülte" 
                else:
                    final_lvl = current_lvl 
            target_levels.append(final_lvl)

        df['Atanacak_Seviye'] = target_levels
        df_active = df[df['Atanacak_Seviye'] != "Mezun/Fakülte"].copy()
        
        # Sıralama
        active_levels = sorted(df_active['Atanacak_Seviye'].unique(), key=lambda x: LEVEL_ORDER.index(x) if x in LEVEL_ORDER else 999)
        
        st.success(f"✅ Dosya başarıyla işlendi ve kurallara göre dağıtıldı.")
        
        # --- İSTATİSTİK PANO (GÜNCELLENMİŞ) ---
        st.markdown("#### 📊 Öğrenci İstatistikleri (Atanacak Seviyeye Göre)")
        
        stats_data = []
        total_students_sum = 0
        
        for level in active_levels:
            subset = df_active[df_active['Atanacak_Seviye'] == level]
            total = len(subset)
            total_students_sum += total
            
            # 1. Ghost (Devamsız) Sayısı
            ghosts = len(subset[subset['Modül Durumu'].str.upper() == 'GHOST'])
            
            # 2. Placement / Yeni (Notu Placement veya Baslangic olanlar)
            placements = len(subset[subset['Modül Durumu'].str.upper().isin(['PLACEMENT', 'BASLANGIC'])])
            
            # 3. Geçen (Başarılı olup buraya gelenler - A, B, C)
            passed = len(subset[subset['Modül Durumu'].str.upper().isin(PASS_GRADES)])
            
            # 4. Kalan (Başarısız olup tekrar edenler - F)
            failed = len(subset[subset['Modül Durumu'].str.upper() == 'F'])
            
            # 5. Aktif (Sadece Geçen ve Kalan toplamı)
            active_std = passed + failed
            
            # Uyruk Dağılımı
            yos = len(subset[subset['Uyruk'].str.upper() == 'YÖS'])
            osym = len(subset[subset['Uyruk'].str.upper() == 'ÖSYM'])
            
            stats_data.append({
                'Seviye': level,
                'Toplam': total,
                'Aktif': active_std,
                'Geçen': passed,
                'Kalan': failed,
                'Placement / Yeni': placements,
                'Ghost': ghosts,
                'ÖSYM': osym,
                'YÖS': yos
            })
            
        # Tabloyu Göster
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
        st.caption(f"*Not: 'Aktif' sütunu, Geçen (alt kurdan gelen) ve Kalan (tekrar eden) öğrencilerin toplamıdır. Ghost ve Placement hariçtir.*")
        
        st.divider()

        # --- 4. PARAMETRE AYARLARI ---
        st.markdown("### 3. Adım: Sınıflandırma Ayarları")
        
        config = {} 
        
        with st.form("settings_form"):
            for level in active_levels:
                students_in_target = df_active[df_active['Atanacak_Seviye'] == level]
                count = len(students_in_target)
                
                st.markdown(f"**🎚️ {level} Seviyesi**")
                
                c1, c2, c3 = st.columns([1, 1, 3])
                
                with c1:
                    num_classes = st.number_input(
                        f"{level} Sınıf Sayısı", 
                        min_value=1, value=1, step=1, 
                        key=f"num_{level}"
                    )
                
                calculated_cap = math.ceil(count / num_classes)
                
                with c2:
                    is_manual = st.checkbox(f"Kapasiteleri elle gir", key=f"chk_{level}")
                    
                with c3:
                    level_caps = []
                    if not is_manual:
                        st.info(f"Otomatik Kapasite: ~{calculated_cap}")
                        for i in range(num_classes):
                            class_name = f"{level}.{i+1:02d}"
                            level_caps.append({'name': class_name, 'cap': calculated_cap})
                    else:
                        st.write("Sınıf Kapasiteleri:")
                        cols = st.columns(min(num_classes, 4))
                        for i in range(num_classes):
                            class_name = f"{level}.{i+1:02d}"
                            with cols[i % 4]:
                                cap = st.number_input(
                                    f"{class_name}", 
                                    min_value=1, value=calculated_cap, step=1, 
                                    key=f"cap_{level}_{i}"
                                )
                                level_caps.append({'name': class_name, 'cap': cap})
                    
                    config[level] = level_caps
                st.markdown("---")
            
            submitted = st.form_submit_button("🚀 Listeleri Oluştur", type="primary")

        # --- 5. HESAPLAMA ---
        if submitted:
            try:
                out_lists = io.BytesIO()
                wb_lists = xlsxwriter.Workbook(out_lists, {'in_memory': True})
                
                db_records = [] 
                current_logs = []
                
                for level in active_levels:
                    level_data = df_active[df_active['Atanacak_Seviye'] == level].copy()
                    classes_cfg = config[level]
                    
                    class_buckets = {c['name']: [] for c in classes_cfg}
                    class_names = [c['name'] for c in classes_cfg]
                    
                    groups = level_data.groupby(['Modül Durumu', 'Uyruk'])
                    current_class_idx = 0
                    
                    for _, group_df in groups:
                        shuffled_students = group_df.sample(frac=1, random_state=42).reset_index(drop=True)
                        for _, student in shuffled_students.iterrows():
                            target_class = class_names[current_class_idx]
                            class_buckets[target_class].append(student)
                            
                            if "." in target_class:
                                class_only_code = target_class.split(".")[-1]
                            else:
                                class_only_code = target_class

                            db_records.append({
                                'OgrNo': student['Öğrenci No'],
                                'Modul': module_no,
                                'Seviye': level,
                                'Sinif': str(class_only_code),
                                'Yil': academic_year
                            })
                            current_class_idx = (current_class_idx + 1) % len(class_names)
                    
                    for c_name in class_names:
                        students_in_class = class_buckets[c_name]
                        df_class = pd.DataFrame(students_in_class)
                        if df_class.empty:
                            df_class = pd.DataFrame(columns=df.columns)
                        else:
                            cols_to_show = ['Seviyesi', 'Öğrenci No', 'Ad', 'Soyad', 'Uyruk', 'Modül Durumu']
                            df_class = df_class[cols_to_show]
                        
                        ws = wb_lists.add_worksheet(c_name)
                        fmt_header = wb_lists.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
                        for col_num, value in enumerate(df_class.columns.values):
                            ws.write(0, col_num, value, fmt_header)
                        for r, row_data in enumerate(df_class.values):
                            for c, val in enumerate(row_data):
                                ws.write(r + 1, c, val)
                        ws.set_column(0, len(df_class.columns) - 1, 15)
                        current_logs.append(f"✅ {c_name} oluşturuldu ({len(df_class)} kişi).")

                wb_lists.close()
                
                df_db = pd.DataFrame(db_records)
                df_db = df_db[['OgrNo', 'Modul', 'Seviye', 'Sinif', 'Yil']]
                out_db = io.BytesIO()
                with pd.ExcelWriter(out_db, engine='xlsxwriter') as writer:
                    df_db.to_excel(writer, index=False, header=False, sheet_name='Database_Import')
                
                st.session_state['generated_lists'] = out_lists.getvalue()
                st.session_state['generated_db'] = out_db.getvalue()
                st.session_state['process_logs'] = current_logs
                
                st.success("Hesaplama tamamlandı! Dosyalar hazır.")

            except Exception as e:
                st.error(f"Beklenmeyen bir hata: {e}")

        # --- 6. SONUÇLAR ---
        if st.session_state['generated_lists'] is not None:
            st.divider()
            st.subheader("🎉 Sonuçlar")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="📥 1. Sınıf Listelerini İndir",
                    data=st.session_state['generated_lists'],
                    file_name='Hazirlik_Sinif_Listeleri.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            
            with col2:
                st.download_button(
                    label="📥 2. Veri Tabanı Listesini İndir",
                    data=st.session_state['generated_db'], 
                    file_name='Database_Import_List.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
            with st.expander("Son İşlem Raporu", expanded=False):
                for l in st.session_state['process_logs']:
                    st.text(l)

    except Exception as e:
        st.error(f"Hata: {e}")
