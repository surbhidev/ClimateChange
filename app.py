import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import math
from math import sin, pi

st.set_page_config(page_title="ClimateSight Globe", layout="wide")

# -----------------------
# Bigger default text via CSS
# -----------------------
st.markdown(
    """
    <style>
    body, p, div, span {
        font-size: 18px !important;
    }
    .big-value { font-size:22px; color:#37e67c; font-weight:700; background:#0b1f14; padding:4px 8px; border-radius:6px;}
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------
# Location lists
# -----------------------
COUNTRIES = {
    "USA": (38.0, -97.0), "Canada": (56.1, -106.3),
    "Brazil": (-14.2, -51.9), "Argentina": (-38.4, -63.6),
    "UK": (55.3, -3.4), "France": (46.2, 2.2), "Germany": (51.2, 10.4),
    "Italy": (41.9, 12.5), "Spain": (40.4, -3.7), "Portugal": (39.4, -8.2),
    "Norway": (60.4, 8.5), "Sweden": (60.1, 18.6), "Finland": (61.9, 25.7),
    "Poland": (51.9, 19.1), "Turkey": (39.0, 35.2), "Russia": (61.5, 105.3),
    "India": (20.6, 78.9), "Pakistan": (30.4, 69.3), "Nepal": (28.4, 84.1),
    "China": (35.8, 104.1), "Japan": (36.2, 138.2), "South Korea": (36.5, 127.9),
    "Indonesia": (-0.8, 113.9), "Australia": (-25.0, 133.8),
    "New Zealand": (-40.9, 174.9), "South Africa": (-30.6, 22.9),
    "Egypt": (26.8, 30.8), "Nigeria": (9.0, 8.7), "Kenya": (-0.02, 37.9),
    "Ethiopia": (9.1, 40.5), "Saudi Arabia": (23.9, 45.1),
    "UAE": (23.4, 53.8), "Qatar": (25.3, 51.2), "Iran": (32.4, 53.7),
    "Iraq": (33.2, 43.7), "Israel": (31.0, 34.8), "Mexico": (23.6, -102.6),
    "Colombia": (4.6, -74.1), "Peru": (-9.1, -75.0), "Chile": (-35.7, -71.5),
    "Venezuela": (6.4, -66.5), "Thailand": (15.8, 101.0),
    "Vietnam": (14.1, 108.3), "Malaysia": (4.2, 102.0),
    "Philippines": (12.8, 121.8), "Bangladesh": (23.7, 90.4),
    "Sri Lanka": (7.8, 80.6)
}

INDIA_STATES = {
    "Delhi": (28.644800, 77.216721),
    "Maharashtra (Mumbai)": (19.075983, 72.877655),
    "Karnataka (Bengaluru)": (12.971599, 77.594566),
    "Tamil Nadu (Chennai)": (13.082680, 80.270718),
    "Uttar Pradesh (Lucknow)": (26.846708, 80.946159),
    "West Bengal (Kolkata)": (22.572645, 88.363892),
    "Gujarat (Ahmedabad)": (23.022505, 72.571362),
    "Rajasthan (Jaipur)": (26.912434, 75.787270),
    "Punjab (Chandigarh)": (30.733315, 76.779417),
    "Haryana (Gurgaon)": (28.459497, 77.026638),
    "Kerala (Thiruvananthapuram)": (8.524139, 76.936638),
    "Odisha (Bhubaneswar)": (20.296059, 85.824539),
    "Bihar (Patna)": (25.594095, 85.137566),
    "Assam (Guwahati)": (26.144518, 91.736237),
    "Madhya Pradesh (Bhopal)": (23.259933, 77.412615),
    "Jharkhand (Ranchi)": (23.344100, 85.309563),
    "Chhattisgarh (Raipur)": (21.251384, 81.629641),
    "Telangana (Hyderabad)": (17.385044, 78.486671)
}

# -----------------------
# Caches
# -----------------------
if "temp" not in st.session_state: st.session_state["temp"] = {}
if "wind" not in st.session_state: st.session_state["wind"] = {}
if "forecast" not in st.session_state: st.session_state["forecast"] = {}
if "air" not in st.session_state: st.session_state["air"] = {}

# -----------------------
# Utility functions
# -----------------------
def speed_to_color(speed, vmax=15.0):
    if speed is None:
        return "rgb(180,180,180)"
    s = max(0.0, min(float(speed), vmax))
    frac = s / vmax
    if frac <= 0.33:
        t = frac / 0.33
        r, g, b = 0, int(255 * t), int(200 + t * 55)
    elif frac <= 0.66:
        t = (frac - 0.33) / 0.33
        r, g, b = int(255 * t), 255, int(255 * (1 - t))
    else:
        t = (frac - 0.66) / 0.34
        r, g, b = 255, int(255 * (1 - t)), 0
    return f"rgb({r},{g},{b})"


def destination_point(lat, lon, bearing_deg, distance_km):
    R = 6371.0
    br = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    d = distance_km / R
    lat2 = math.asin(math.sin(lat1) * math.cos(d) +
                     math.cos(lat1) * math.sin(d) * math.cos(br))
    lon2 = lon1 + math.atan2(math.sin(br) * math.sin(d) * math.cos(lat1),
                             math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def deg_to_compass(deg):
    if deg is None:
        return "—"
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int((deg + 11.25) / 22.5) % 16]

# -----------------------
# Open-Meteo API Helpers
# -----------------------
def get_temp(lat, lon):
    key = f"T:{lat:.3f}:{lon:.3f}"
    if key in st.session_state["temp"]:
        return st.session_state["temp"][key]
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "hourly": "temperature_2m", "timezone": "auto"},
            timeout=8).json()
        val = resp.get("hourly", {}).get("temperature_2m", [None])[0]
        st.session_state["temp"][key] = val
        return val
    except:
        st.session_state["temp"][key] = None
        return None


def get_wind(lat, lon):
    key = f"W:{lat:.3f}:{lon:.3f}"
    if key in st.session_state["wind"]:
        return st.session_state["wind"][key]
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "hourly": "windspeed_10m,winddirection_10m",
                    "timezone": "auto"},
            timeout=8).json()
        ws = resp["hourly"]["windspeed_10m"][0]
        wd = resp["hourly"]["winddirection_10m"][0]
        st.session_state["wind"][key] = (ws, wd)
        return ws, wd
    except:
        st.session_state["wind"][key] = (None, None)
        return None, None


def get_forecast(lat, lon):
    key = f"F:{lat:.3f}:{lon:.3f}"
    if key in st.session_state["forecast"]:
        return st.session_state["forecast"][key]
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "hourly":
                    "temperature_2m,relativehumidity_2m,windspeed_10m,winddirection_10m",
                "daily":
                    "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto"
            },
            timeout=10).json()
        st.session_state["forecast"][key] = resp
        return resp
    except:
        st.session_state["forecast"][key] = {}
        return {}


def get_air(lat, lon):
    key = f"A:{lat:.3f}:{lon:.3f}"
    if key in st.session_state["air"]:
        return st.session_state["air"][key]
    try:
        resp = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={"latitude": lat, "longitude": lon,
                    "hourly": "pm10,pm2_5,us_aqi"},
            timeout=10).json()
        st.session_state["air"][key] = resp
        return resp
    except:
        st.session_state["air"][key] = {}
        return {}

# -----------------------
# 48-hour plot
# -----------------------
def plot_temp48(forecast):
    try:
        df = pd.DataFrame({
            "time": forecast["hourly"]["time"][:48],
            "temp": forecast["hourly"]["temperature_2m"][:48]
        })
        df["time"] = pd.to_datetime(df["time"])
        now = pd.Timestamp.now()

        fig = go.Figure(go.Scatter(
            x=df["time"], y=df["temp"], mode="lines+markers",
            line=dict(width=3), marker=dict(size=6)
        ))

        if df["time"].min() <= now <= df["time"].max():
            xloc = now
        else:
            xloc = df["time"].min()

        fig.add_vline(x=xloc, line_width=3, line_dash="dash",
                      line_color="#ff4d4d", opacity=0.9)

        fig.update_layout(height=360, margin=dict(l=20, r=20, t=20, b=20))
        return fig
    except:
        return go.Figure()

# -----------------------
# UI selection
# -----------------------
st.title("🌍 ClimateSight Globe")

mode = st.sidebar.radio("Mode", ["World", "India (states)"])
if mode == "World":
    selected = st.sidebar.selectbox("Select Country", list(COUNTRIES.keys()))
    sel_lat, sel_lon = COUNTRIES[selected]
else:
    selected = st.sidebar.selectbox("Select State", list(INDIA_STATES.keys()))
    sel_lat, sel_lon = INDIA_STATES[selected]

# -----------------------
# Build data points
# -----------------------
locations = COUNTRIES if mode == "World" else INDIA_STATES
points = []
for name, (lat, lon) in locations.items():
    temp = get_temp(lat, lon)
    ws, wd = get_wind(lat, lon)
    points.append({
        "name": name, "lat": lat, "lon": lon,
        "temp": temp, "ws": ws, "wd": wd,
        "color": speed_to_color(ws)
    })

wind_points = [p for p in points if p["wd"] is not None]

# -----------------------
# Base globe figure
# -----------------------
fig = go.Figure()

fig.add_trace(go.Scattergeo(
    lat=[p["lat"] for p in points],
    lon=[p["lon"] for p in points],
    text=[f"{p['name']} — {p['temp']}°C" for p in points],
    mode="markers+text",
    marker=dict(size=9, color="crimson"),
    textfont=dict(size=18, color="white"),
    textposition="top center"
))

# placeholders for wind arrow pieces
for p in wind_points:
    fig.add_trace(go.Scattergeo(lat=[None], lon=[None], mode="lines", line=dict(width=4, color=p["color"])))
    fig.add_trace(go.Scattergeo(lat=[None], lon=[None], mode="lines", line=dict(width=4, color=p["color"])))
    fig.add_trace(go.Scattergeo(lat=[None], lon=[None], mode="lines", line=dict(width=4, color=p["color"])))

# -----------------------
# Animation frames
# -----------------------
N = 20
OSC = 12
MAIN = 500
HEAD = 150

frames = []
for i in range(N):
    phase = 2*pi*(i/N)
    fdata = [fig.data[0]]
    for idx, p in enumerate(wind_points):
        base = float(p["wd"])
        bearing = base + OSC * math.sin(phase + idx*0.3)

        lat2, lon2 = destination_point(p["lat"], p["lon"], bearing, MAIN)
        left_lat, left_lon = destination_point(lat2, lon2, bearing+150, HEAD)
        right_lat, right_lon = destination_point(lat2, lon2, bearing-150, HEAD)

        fdata.append(go.Scattergeo(lat=[p["lat"], lat2], lon=[p["lon"], lon2],
                                   mode="lines", line=dict(width=4, color=p["color"])))
        fdata.append(go.Scattergeo(lat=[lat2, left_lat], lon=[lon2, left_lon],
                                   mode="lines", line=dict(width=4, color=p["color"])))
        fdata.append(go.Scattergeo(lat=[lat2, right_lat], lon=[lon2, right_lon],
                                   mode="lines", line=dict(width=4, color=p["color"])))

    frames.append(go.Frame(name=f"f{i}", data=fdata))

fig.frames = frames

# -----------------------
# Layout with blue ocean
# -----------------------
fig.update_layout(
    geo=dict(
        showcountries=True,
        showland=True,
        showocean=True,
        landcolor="rgba(211, 211, 211, 1)",
        oceancolor="rgba(179, 229, 252, 0.8)",
        coastlinecolor="rgba(100,100,100,0.6)",
        showcoastlines=True,
        projection_type="orthographic",
        projection_rotation=dict(lat=sel_lat, lon=sel_lon)
    ),
    margin=dict(l=0, r=0, t=10, b=0),
    showlegend=False,
    height=720,
    updatemenus=[{
        "type": "buttons",
        "showactive": False,
        "x": 0.06, "y": 0.06,
        "buttons": [
            {"label": "Play", "method": "animate",
             "args": [None, {"frame": {"duration": 80, "redraw": True}, "fromcurrent": True}]},
            {"label": "Pause", "method": "animate",
             "args": [[None], {"frame": {"duration": 0, "redraw": False}}]}
        ]
    }]
)

# -----------------------
# Show Globe
# -----------------------
st.plotly_chart(fig, use_container_width=True)

# -----------------------
# Wind-Speed Legend (Sidebar)
# -----------------------
with st.sidebar:
    st.markdown("## 🌬 Wind Speed Legend")
    st.write("Arrow colors represent wind intensity (m/s).")

    legend_html = """
    <div style="padding:10px; background-color:#111; border-radius:8px;">
        <div style="display:flex; align-items:center; margin-bottom:6px;">
            <div style="width:22px; height:10px; background:rgb(0,0,200); margin-right:8px;"></div>
            <span style="color:white;">0 – 1 m/s (Calm)</span>
        </div>
        <div style="display:flex; align-items:center; margin-bottom:6px;">
            <div style="width:22px; height:10px; background:rgb(0,120,230); margin-right:8px;"></div>
            <span style="color:white;">1 – 3 m/s (Light Breeze)</span>
        </div>
        <div style="display:flex; align-items:center; margin-bottom:6px;">
            <div style="width:22px; height:10px; background:rgb(60,255,120); margin-right:8px;"></div>
            <span style="color:white;">3 – 6 m/s (Moderate Breeze)</span>
        </div>
        <div style="display:flex; align-items:center; margin-bottom:6px;">
            <div style="width:22px; height:10px; background:rgb(255,255,0); margin-right:8px;"></div>
            <span style="color:white;">6 – 10 m/s (Strong Breeze)</span>
        </div>
        <div style="display:flex; align-items:center; margin-bottom:6px;">
            <div style="width:22px; height:10px; background:rgb(255,170,0); margin-right:8px;"></div>
            <span style="color:white;">10 – 12 m/s (High Wind)</span>
        </div>
        <div style="display:flex; align-items:center;">
            <div style="width:22px; height:10px; background:rgb(255,80,0); margin-right:8px;"></div>
            <span style="color:white;">12 – 15 m/s (Very Strong Wind)</span>
        </div>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)



# -----------------------
# Details Section (fixed)
# -----------------------
st.subheader(f"📍 Details — {selected}")

forecast = get_forecast(sel_lat, sel_lon)
air = get_air(sel_lat, sel_lon)
wspd, wdir = get_wind(sel_lat, sel_lon)

# Prepare safe defaults for summary (extract values BEFORE creating the summary)
cur_temp = None
cur_hum = None
pm25 = None
pm10 = None
aqi = None

# Extract current temp & humidity from forecast safely
try:
    cur_temp = forecast.get("hourly", {}).get("temperature_2m", [None])[0]
except Exception:
    cur_temp = None

try:
    cur_hum = forecast.get("hourly", {}).get("relativehumidity_2m", [None])[0]
except Exception:
    cur_hum = None

# Extract AQI values safely
try:
    pm25 = air.get("hourly", {}).get("pm2_5", [None])[0]
    pm10 = air.get("hourly", {}).get("pm10", [None])[0]
    aqi = air.get("hourly", {}).get("us_aqi", [None])[0]
except Exception:
    pm25 = pm10 = aqi = None

left, right = st.columns([2, 1])

# ------------------------------------------------------
# NEW FEATURE — AI-STYLE WEATHER SUMMARY (2–3 SENTENCES)
# ------------------------------------------------------
def summarize_weather(temp, hum, wind, aqi):
    sentences = []

    # Temperature interpretation
    if temp is not None:
        try:
            tval = float(temp)
        except:
            tval = None
        if tval is not None:
            if tval < 10:
                sentences.append(f"The temperature is quite cold at around {tval}°C, so conditions may feel chilly.")
            elif tval < 20:
                sentences.append(f"The temperature is mild at about {tval}°C, comfortable for most outdoor activities.")
            elif tval < 30:
                sentences.append(f"The temperature is warm at roughly {tval}°C.")
            else:
                sentences.append(f"It's quite hot right now at around {tval}°C, which may feel uncomfortable outdoors.")

    # Humidity interpretation
    if hum is not None:
        try:
            hval = float(hum)
        except:
            hval = None
        if hval is not None:
            if hval > 70:
                sentences.append("Humidity is high, which can make the weather feel heavier and more uncomfortable.")
            elif hval > 40:
                sentences.append("Humidity levels are moderate and generally comfortable.")
            else:
                sentences.append("Humidity is low, so the air may feel dry.")

    # Wind interpretation
    if wind is not None:
        try:
            wval = float(wind)
        except:
            wval = None
        if wval is not None:
            if wval < 3:
                sentences.append("Winds are very light, keeping conditions calm.")
            elif wval < 7:
                sentences.append("There's a gentle to moderate breeze.")
            else:
                sentences.append("Winds are strong, which may affect outdoor comfort.")

    # AQI interpretation
    if aqi is not None:
        try:
            aval = float(aqi)
        except:
            aval = None
        if aval is not None:
            if aval <= 50:
                sentences.append("Air quality is excellent, making outdoor activities completely safe.")
            elif aval <= 100:
                sentences.append("Air quality is acceptable for most people.")
            else:
                sentences.append("Air quality is poor, so sensitive groups should limit outdoor exposure.")

    return " ".join(sentences[:3])  # only 2–3 sentences

st.markdown("### Climate sight")
summary = summarize_weather(cur_temp, cur_hum, wspd, aqi)
st.markdown(f"<p style='font-size:19px; color:#e5e5e5;'>{summary}</p>", unsafe_allow_html=True)

# -----------------------
# Left column: Current Weather + chart
# -----------------------
with left:
    st.markdown("### 🌦 Current Weather")
    if cur_temp is not None:
        st.markdown(f"**Temperature:** <span class='big-value'>{cur_temp} °C</span>", unsafe_allow_html=True)
    else:
        st.write("Temperature unavailable")

    if cur_hum is not None:
        st.markdown(f"**Humidity:** <span class='big-value'>{cur_hum}%</span>", unsafe_allow_html=True)
    else:
        st.write("Humidity unavailable")

    st.markdown("### 🌬 Wind")
    if wdir is not None:
        st.markdown(
            f"Direction: <span class='big-value'>{int(wdir)}° ({deg_to_compass(wdir)})</span>",
            unsafe_allow_html=True
        )
    if wspd is not None:
        st.markdown(
            f"Speed: <span class='big-value'>{wspd} m/s</span>",
            unsafe_allow_html=True
        )

    st.markdown("### 📍 Coordinates")
    st.markdown(f"Latitude: <span class='big-value'>{sel_lat}</span>", unsafe_allow_html=True)
    st.markdown(f"Longitude: <span class='big-value'>{sel_lon}</span>", unsafe_allow_html=True)

    st.markdown("### 📈 48hr Temperature")
    st.plotly_chart(plot_temp48(forecast), use_container_width=True)

# -----------------------
# Right column: Air Quality
# -----------------------
with right:
    st.markdown("### 🌫 Air Quality")
    if pm25 is not None or pm10 is not None or aqi is not None:
        try:
            if pm25 is not None:
                st.markdown(f"PM2.5: <span class='big-value'>{pm25}</span>", unsafe_allow_html=True)
            if pm10 is not None:
                st.markdown(f"PM10: <span class='big-value'>{pm10}</span>", unsafe_allow_html=True)
            if aqi is not None:
                st.markdown(f"US AQI: <span class='big-value'>{aqi}</span>", unsafe_allow_html=True)
        except Exception:
            st.write("Air quality unavailable")
    else:
        st.write("Air quality unavailable")

# -----------------------
# 7-day Summary (unchanged)
# -----------------------
st.markdown("### 📅 7-day Summary")
try:
    daily = forecast["daily"]
    st.markdown(f"Max Today: <span class='big-value'>{daily['temperature_2m_max'][0]} °C</span>",
                unsafe_allow_html=True)
    st.markdown(f"Min Today: <span class='big-value'>{daily['temperature_2m_min'][0]} °C</span>",
                unsafe_allow_html=True)
    st.markdown(f"Rain Today: <span class='big-value'>{daily['precipitation_sum'][0]} mm</span>",
                unsafe_allow_html=True)
except Exception:
    st.write("Forecast unavailable")
