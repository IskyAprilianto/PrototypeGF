import streamlit as st
import requests
import random
import pandas as pd
from datetime import datetime

# Konfigurasi API
# Ganti URL ini dengan URL publik yang didapatkan dari Replit
FLASK_API_URL = 'https://9fda3355-e9d0-407b-8251-e35d4b04d3e4-00-2qpufjr3z6si3.riker.replit.dev:3000/get_data'

GEMINI_API_KEY = 'AIzaSyBdWBk-_PHYl15ZdAFspcaEKtwwMcrymvw'  # Pastikan API key valid
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'


def get_gemini_explanation(temp, humidity, ldr):
    """Dapatkan penjelasan dari Gemini API dengan konteks lengkap"""
    try:
        # Buat prompt yang lebih kaya dengan semua parameter sensor
        context = (
            f"Sebagai ahli pertanian, berikan analisis singkat (5-7 kalimat) dalam Bahasa Indonesia "
            f"tentang kondisi rumah kaca dengan:\n"
            f"- Suhu: {temp}°C\n"
            f"- Kelembaban: {humidity}%\n"
            f"- Intensitas Cahaya: {ldr}\n\n"
            f"Berikan rekomendasi tindakan jika diperlukan."
        )
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{
                    "text": context
                }]
            }],
            "safetySettings": {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            },
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 200
            }
        }
        
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        
        # Ekstrak respon dengan penanganan error yang lebih baik
        result = response.json()
        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']
        return "Tidak dapat memproses respon Gemini"
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error koneksi ke Gemini API: {str(e)}")
        return f"Penjelasan tidak tersedia: Error jaringan"
    except Exception as e:
        st.error(f"Error pemrosesan Gemini: {str(e)}")
        return f"Penjelasan tidak tersedia: Error sistem"


# Fungsi untuk memformat timestamp
def format_timestamp(ts):
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M:%S')
        return str(ts)
    except:
        return "Waktu tidak valid"


# Antarmuka Streamlit
st.set_page_config(page_title="Monitoring Rumah Kaca", layout="wide")
st.title('🌿 Monitoring Rumah Kaca Cerdas')

# Menambahkan CSS untuk penataan tampilan
st.markdown("""
    <style>
    .metric-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #e1f5fe;  /* Warna latar belakang yang lebih terang */
        color: #333333;  /* Warna teks lebih gelap */
        margin-bottom: 10px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);  /* Menambahkan bayangan untuk efek depth */
    }
    .warning-box {
        background-color: #e1f5fe;  /* Warna latar belakang yang serupa dengan kotak data */
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        color: #333333;  /* Menjaga konsistensi warna teks */
    }
    </style>
    """, unsafe_allow_html=True)

if st.button('🔄 Perbarui Data', type='primary'):
    with st.spinner('Memuat data terbaru...'):
        try:
            # Ambil data dari Flask API
            response = requests.get(FLASK_API_URL, timeout=10)
            response.raise_for_status()
            api_data = response.json()
            
            if api_data.get('status') == 'success' and api_data.get('count', 0) > 0:
                data = api_data['data']
                latest = data[0]
                
                # Tampilan data terbaru
                st.subheader('📊 Data Sensor Terkini')
                cols = st.columns(3)
                with cols[0]:
                    st.markdown('<div class="metric-box">'
                               '<h3>🌡️ Suhu</h3>'
                               f'<h2>{latest["temperature"]} °C</h2>'
                               '</div>', unsafe_allow_html=True)
                with cols[1]:
                    st.markdown('<div class="metric-box">'
                               '<h3>💧 Kelembaban</h3>'
                               f'<h2>{latest["humidity"]}%</h2>'
                               '</div>', unsafe_allow_html=True)
                with cols[2]:
                    st.markdown('<div class="metric-box">'
                               '<h3>☀️ Intensitas Cahaya</h3>'
                               f'<h2>{latest["ldr_value"]}</h2>'
                               '</div>', unsafe_allow_html=True)
                
                # Analisis Gemini
                with st.expander("🔍 Analisis Kondisi", expanded=True):
                    analysis = get_gemini_explanation(
                        latest["temperature"],
                        latest["humidity"],
                        latest["ldr_value"]
                    )
                    st.write(analysis)
                    
                    # Pemberitahuan otomatis berdasarkan suhu
                    if latest["temperature"] > 30:
                        st.markdown('<div class="warning-box">'
                                   '⚠️ <strong>Pemberitahuan: Tudung Akan Ditutup</strong><br>'
                                   'Suhu melebihi 30°C, tudung rumah kaca akan ditutup secara otomatis '
                                   'untuk melindungi tanaman dari suhu yang berlebihan.'
                                   '</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="warning-box">'
                                   '🌞 <strong>Pemberitahuan: Tudung Akan Dibuka</strong><br>'
                                   'Suhu berada dalam rentang optimal untuk tanaman, tudung rumah kaca akan dibuka '
                                   'secara otomatis untuk pencahayaan yang lebih baik.'
                                   '</div>', unsafe_allow_html=True)
                
                # Visualisasi data
                st.subheader('📈 Grafik Historis')
                df = pd.DataFrame(data)
                
                # Konversi timestamp
                try:
                    df['Waktu'] = pd.to_datetime(df['timestamp'], unit='s')
                except:
                    df['Waktu'] = pd.to_datetime(df['timestamp'])
                
                # Tabs untuk grafik
                tab1, tab2, tab3 = st.tabs(["Suhu", "Kelembaban", "Cahaya"])
                
                with tab1:
                    st.line_chart(df, x='Waktu', y='temperature', height=300)
                with tab2:
                    st.line_chart(df, x='Waktu', y='humidity', height=300)
                with tab3:
                    st.line_chart(df, x='Waktu', y='ldr_value', height=300)
                
                # Tabel data
                st.subheader('📋 Data Historis')
                df_display = df.copy()
                df_display['Waktu'] = df_display['Waktu'].apply(format_timestamp)
                st.dataframe(
                    df_display[['Waktu', 'temperature', 'humidity', 'ldr_value']],
                    column_config={
                        "Waktu": "Waktu",
                        "temperature": st.column_config.NumberColumn("Suhu (°C)", format="%.1f"),
                        "humidity": st.column_config.NumberColumn("Kelembaban (%)", format="%.1f"),
                        "ldr_value": st.column_config.NumberColumn("Intensitas Cahaya")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
            else:
                st.warning("Tidak ada data yang tersedia di server")
                
        except requests.exceptions.RequestException as e:
            st.error(f"Gagal terhubung ke server: {str(e)}")
        except Exception as e:
            st.error(f"Terjadi kesalahan sistem: {str(e)}")
else:
    st.info("Klik tombol 'Perbarui Data' untuk memuat informasi terbaru dari sensor")

# Catatan kaki
st.markdown("---")
st.caption("Sistem Monitoring Rumah Kaca Cerdas Starlith Team © 2024 - Powered by Flask, Streamlit, dan Gemini AI")
st.caption("Catatan : Streamlit bisa saja tidak terhubung ke sever (backend flask) dikarenakan running server pada replit(webhosting yang free) sering off sendiri, untuk menor atau reviewers tidak bisa mengakses dikarenakan server mati dapat menjalankan secara lokal atau bisa chat salah satu anggota kelompok agar segera menghidupkan kembali server pada Replit")
