from flask import Flask, render_template, redirect, request, session, url_for
import requests
import os
import urllib.parse
import pandas as pd
import json
from bson.json_util import dumps
import plotly.graph_objects as go
import plotly.utils
from dotenv import load_dotenv
from functools import lru_cache
from pymongo import MongoClient
from math import radians, cos, sin, asin, sqrt

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-fallback-key")

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

MONGO_PASSWORD = "nidi@2022-2026"
ENCODED_PASSWORD = urllib.parse.quote_plus(MONGO_PASSWORD)
MONGO_URI = f"mongodb+srv://nidi_user0:{ENCODED_PASSWORD}@nidi.qkiysav.mongodb.net/?appName=NiDi"

try:
    client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
    db = client["NiDi_DB"]
    client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")

def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return round(6371 * c, 2)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

def get_google_redirect_uri():
    uri = request.host_url.rstrip('/')
    if "ngrok-free.app" in uri:
        uri = uri.replace("http://", "https://")
    return f"{uri}/auth/google/callback"

@app.context_processor
def inject_user():
    user_data = session.get("user")
    if user_data:
        class UserProxy:
            def __init__(self, data):
                self.is_authenticated = True
                self.name = data.get("name")
                self.email = data.get("email")
                self.picture = data.get("picture")
        return dict(current_user=UserProxy(user_data))
    class AnonymousProxy:
        def __init__(self):
            self.is_authenticated = False
    return dict(current_user=AnonymousProxy())

@lru_cache(maxsize=1)
def get_crime_stats():
    collections = [
        "total_cases", "ipc_cases", "sll_cases", "crime_against_children",
        "crime_against_woman", "sc_st_atrocities", "cyber_cases",
        "missing_cases", "road_accidents", "cotpa_cases", "pocso_cases"
    ]
    all_graphs_json = []

    for col_name in collections:
        try:
            cursor = db[col_name].find({})
            df = pd.DataFrame(json.loads(dumps(cursor)))
            if not df.empty:
                fig = go.Figure()
                x_data, y_data = [], []
                display_title = col_name.replace('_', ' ').upper()
                year_cols = [c for c in df.columns if c.isdigit() and len(c) == 4]

                if year_cols:
                    row_idx = 0
                    if 'Crime_Heads' in df.columns:
                        total_rows = df[df['Crime_Heads'].str.contains('Total', na=False)].index
                        if not total_rows.empty:
                            row_idx = total_rows[0]
                    x_data = year_cols
                    y_data = [pd.to_numeric(df.loc[row_idx, yr], errors='coerce') for yr in year_cols]
                elif 'Year' in df.columns:
                    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
                    potential_y = ['Total', 'Cases', 'No. of cases']
                    count_col = next((c for c in potential_y if c in df.columns), df.columns[-1])
                    df = df.dropna(subset=['Year']).sort_values('Year')
                    x_data = df['Year']
                    y_data = pd.to_numeric(df[count_col], errors='coerce')
                elif 'District' in df.columns:
                    df = df[~df['District'].str.contains('Total', na=False)]
                    x_data = df['District']
                    count_col = [c for c in df.columns if 'Total' in c][0]
                    y_data = pd.to_numeric(df[count_col], errors='coerce')

                if len(x_data) > 0:
                    fig.add_trace(go.Bar(
                        x=x_data, y=y_data,
                        marker=dict(color='#1e3a66', line=dict(color='#ffffff', width=1)),
                        opacity=0.8
                    ))
                    fig.add_trace(go.Scatter(
                        x=x_data, y=y_data,
                        mode='markers+lines',
                        line=dict(color='#2a5aa8', width=3)
                    ))
                    fig.update_layout(
                        title={'text': display_title, 'x': 0.5},
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        showlegend=False,
                        margin=dict(l=50, r=50, t=60, b=40),
                        hovermode='x unified'
                    )
                    all_graphs_json.append(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))
        except:
            continue
    return all_graphs_json

@app.route("/")
def home():
    graphs = get_crime_stats()
    return render_template("index.html", all_graphs=graphs)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/signin")
def signup_view():
    if "user" in session:
        return redirect(url_for("home"))
    return render_template("signup.html")

@app.route("/login")
@app.route("/signup")
def login_redirect():
    return redirect(url_for("signup_view"))

@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("signup_view"))
    return render_template("botinterface.html")

@app.route("/auth/google")
def google_login():
    cfg = get_google_provider_cfg()
    redirect_uri = get_google_redirect_uri()
    return redirect(
        f"{cfg['authorization_endpoint']}?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}&scope=openid%20email%20profile")

@app.route("/auth/google/callback")
def google_callback():
    code = request.args.get("code")
    cfg = get_google_provider_cfg()
    redirect_uri = get_google_redirect_uri()
    token_res = requests.post(cfg["token_endpoint"], data={
        "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code"
    }).json()
    userinfo = requests.get(cfg["userinfo_endpoint"],
                            headers={"Authorization": f"Bearer {token_res['access_token']}"}).json()
    session["user"] = {"email": userinfo["email"], "name": userinfo["name"], "picture": userinfo["picture"]}
    return redirect(url_for("home"))

@app.route("/emergency-locator")
def emergency_locator():
    return render_template("locator.html")

@app.route("/get_nearby_stations")
def get_nearby_stations():
    try:
        lat_raw = request.args.get('lat')
        lon_raw = request.args.get('lon')
        if not lat_raw or not lon_raw:
            return {"error": "Missing coordinates"}, 400
        lat, lon = float(lat_raw), float(lon_raw)
        overpass_url = "http://overpass-api.de/api/interpreter"
        for radius in [2000, 5000, 10000]:
            overpass_query = f"""
            [out:json][timeout:15];
            (node["amenity"="police"](around:{radius},{lat},{lon});
             way["amenity"="police"](around:{radius},{lat},{lon}););
            out center;"""
            try:
                response = requests.get(overpass_url, params={'data': overpass_query}, timeout=15)
                data = response.json()
                elements = data.get('elements', [])
                if elements:
                    for el in elements:
                        s_lat = el.get('lat') or el.get('center', {}).get('lat')
                        s_lon = el.get('lon') or el.get('center', {}).get('lon')
                        el['distance'] = haversine(lat, lon, s_lat, s_lon)
                    elements.sort(key=lambda x: x['distance'])
                    data['elements'] = elements[:4]
                    return data
            except:
                continue
        return {"elements": []}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/rasa_proxy", methods=["POST"])
def rasa_proxy():
    rasa_url = "http://127.0.0.1:5005/webhooks/rest/webhook"
    try:
        response = requests.post(rasa_url, json=request.json, timeout=15)
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)