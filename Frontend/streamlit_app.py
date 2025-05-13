import streamlit as st
import requests
import random
import pandas as pd
from datetime import datetime

# API Configuration
FLASK_API_URL = 'https://9fda3355-e9d0-407b-8251-e35d4b04d3e4-00-2qpufjr3z6si3.riker.replit.dev/get_data'
GEMINI_API_KEY = 'AIzaSyBdWBk-_PHYl15ZdAFspcaEKtwwMcrymvw'
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
WEATHER_API_KEY = 'bab07566b614de4ccb9d2cdf1da77c08'

# Cuaca Jakarta
def get_weather_forecast(city_name, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric&lang=id"
    try:
        response = requests.get(url, timeout=15)  # Extended timeout for weather API
        data = response.json()
        if response.status_code == 200:
            return {
                "kota": data["name"],
                "cuaca": data["weather"][0]["description"],
                "suhu": data["main"]["temp"],
                "terasa": data["main"]["feels_like"],
                "kelembaban": data["main"]["humidity"],
                "angin": f"{data['wind']['speed']} m/s {data['wind'].get('deg', 0)}°",
                "tekanan": f"{data['main']['pressure']} hPa",
                "dew_point": f"{round(data['main']['temp'] - ((100 - data['main']['humidity']) / 5), 1)} °C"
            }
        else:
            return {"error": f"Data tidak tersedia: {data.get('message', 'Unknown error')}"}
    except Exception as e:
        return {"error": str(e)}

# Gemini Analisis
def get_gemini_explanation(temp, humidity, ldr):
    try:
        context = (
            f"Sebagai ahli pertanian, berikan analisis singkat (5-7 kalimat) dalam Bahasa Indonesia "
            f"tentang kondisi rumah dengan:\n"
            f"- Suhu: {temp}°C\n"
            f"- Kelembaban: {humidity}%\n"
            f"- Intensitas Cahaya: {ldr}\n\n"
            f"Berikan rekomendasi tindakan jika diperlukan."
        )

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": context}]
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
            timeout=15  # Extended timeout for Gemini API request
        )
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

def format_timestamp(ts):
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M:%S')
        return str(ts)
    except:
        return "Waktu tidak valid"

# Streamlit UI
st.set_page_config(page_title="Monitoring Rumah ", layout="wide")
st.title('🌿 Monitoring Atap Cerdas Canopya')

# Cuaca Jakarta
st.markdown("---")
st.subheader("🌤 Prediksi Cuaca Jakarta Hari Ini")

cuaca = get_weather_forecast("Jakarta", WEATHER_API_KEY)
if "error" in cuaca:
    st.warning(cuaca["error"])
else:
    st.markdown(f"""
        *Kota:* {cuaca['kota']}  
        *Cuaca:* {cuaca['cuaca'].capitalize()}  
        *Suhu Udara:* {cuaca['suhu']} °C  
        *Terasa Seperti:* {cuaca['terasa']} °C  
        *Kelembaban:* {cuaca['kelembaban']} %  
        *Kecepatan Angin:* {cuaca['angin']}  
        *Tekanan Udara:* {cuaca['tekanan']}  
        *Titik Embun (Dew Point):* {cuaca['dew_point']}  
    """)

# CSS
st.markdown("""
    <style>
    .metric-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #e1f5fe;
        color: #333333;
        margin-bottom: 10px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
    }
    .warning-box {
        background-color: #e1f5fe;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        color: #333333;
    }
    </style>
""", unsafe_allow_html=True)

# Tombol
if st.button('🔄 Perbarui Data', type='primary'):
    with st.spinner('Memuat data terbaru...'):
        try:
            response = requests.get(FLASK_API_URL, timeout=15)  # Extended timeout for Flask request
            response.raise_for_status()
            api_data = response.json()

            if api_data.get('status') == 'success' and api_data.get('count', 0) > 0:
                data = api_data['data']
                latest = data[0]

                st.subheader('📊 Data Sensor Terkini')
                cols = st.columns(3)
                with cols[0]:
                    st.markdown(f'<div class="metric-box"><h3>🌡 Suhu</h3><h2>{latest["temperature"]} °C</h2></div>', unsafe_allow_html=True)
                with cols[1]:
                    st.markdown(f'<div class="metric-box"><h3>💧 Kelembaban</h3><h2>{latest["humidity"]}%</h2></div>', unsafe_allow_html=True)
                with cols[2]:
                    st.markdown(f'<div class="metric-box"><h3>☀ Intensitas Cahaya</h3><h2>{latest["ldr_value"]}</h2></div>', unsafe_allow_html=True)

                with st.expander("🔍 Analisis Kondisi", expanded=True):
                    analysis = get_gemini_explanation(
                        latest["temperature"],
                        latest["humidity"],
                        latest["ldr_value"]
                    )
                    st.write(analysis)

                    if latest["temperature"] > 30:
                        st.markdown('<div class="warning-box">⚠ <strong>Pemberitahuan: Tudung Akan Ditutup</strong><br>Suhu melebihi 30°C, tudung rumah kaca akan ditutup secara otomatis untuk melindungi tanaman dari suhu yang berlebihan.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="warning-box">🌞 <strong>Pemberitahuan: Tudung Akan Dibuka</strong><br>Suhu berada dalam rentang optimal untuk tanaman, tudung rumah kaca akan dibuka secara otomatis untuk pencahayaan yang lebih baik.</div>', unsafe_allow_html=True)

                st.subheader('📈 Grafik Historis')
                df = pd.DataFrame(data)
                try:
                    df['Waktu'] = pd.to_datetime(df['timestamp'], unit='s')
                except:
                    df['Waktu'] = pd.to_datetime(df['timestamp'])

                tab1, tab2, tab3 = st.tabs(["Suhu", "Kelembaban", "Cahaya"])
                with tab1:
                    st.line_chart(df, x='Waktu', y='temperature', height=300)
                with tab2:
                    st.line_chart(df, x='Waktu', y='humidity', height=300)
                with tab3:
                    st.line_chart(df, x='Waktu', y='ldr_value', height=300)

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

# Footer
st.markdown("---")
st.caption("Sistem Monitoring Rumah Kaca Cerdas Starlith Team © 2024 - Powered by Flask, Streamlit, dan Gemini AI")
st.caption("🧐Catatan: Streamlit bisa saja tidak terhubung ke server (backend Flask) karena Replit akan auto-sleep jika tidak diakses selama 5 menit. Jalankan ulang server Replit bila perlu.")
st.caption("Terimakasih 😁👍")
