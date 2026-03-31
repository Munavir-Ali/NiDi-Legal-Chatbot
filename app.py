cd 

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
    collections = ["total_cases", "ipc_cases", "sll_cases", "crime_against_children", "crime_against_woman", "sc_st_atrocities", "cyber_cases", "missing_cases", "road_accidents", "cotpa_cases", "pocso_cases"]
    all_graphs_json = []
    for col_name in collections:
        try:
            cursor = db[col_name].find({})
            df = pd.DataFrame(json.loads(dumps(cursor)))
            if not df.empty:
                fig = go.Figure()
                display_title = col_name.replace('_', ' ').upper()
                year_cols = [c for c in df.columns if c.isdigit() and len(c) == 4]
                if year_cols:
                    row_idx = 0
                    if 'Crime_Heads' in df.columns:
                        total_rows = df[df['Crime_Heads'].str.contains('Total', na=False)].index
                        if not total_rows.empty: row_idx = total_rows[0]
                    x_data = year_cols
                    y_data = [pd.to_numeric(df.loc[row_idx, yr], errors='coerce') for yr in year_cols]
                elif 'Year' in df.columns:
                    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
                    count_col = next((c for c in ['Total', 'Cases', 'No. of cases'] if c in df.columns), df.columns[-1])
                    df = df.dropna(subset=['Year']).sort_values('Year')
                    x_data, y_data = df['Year'], pd.to_numeric(df[count_col], errors='coerce')
                elif 'District' in df.columns:
                    df = df[~df['District'].str.contains('Total', na=False)]
                    x_data = df['District']
                    count_col = [c for c in df.columns if 'Total' in c][0]
                    y_data = pd.to_numeric(df[count_col], errors='coerce')
                if len(x_data) > 0:
                    fig.add_trace(go.Bar(x=x_data, y=y_data, marker=dict(color='#1e3a66', line=dict(color='#ffffff', width=1)), opacity=0.8))
                    fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='markers+lines', line=dict(color='#2a5aa8', width=3)))
                    fig.update_layout(title={'text': display_title, 'x': 0.5}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(l=50, r=50, t=60, b=40), hovermode='x unified')
                    all_graphs_json.append(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))
        except: continue
    return all_graphs_json

@app.route("/")
def home():
    return render_template("index.html", all_graphs=get_crime_stats())

@app.route("/about")
def about(): return render_template("about.html")

@app.route("/signin")
def signup_view():
    if "user" in session: return redirect(url_for("home"))
    return render_template("signup.html")

@app.route("/chat")
def chat():
    if "user" not in session: return redirect(url_for("signup_view"))
    return render_template("botinterface.html")

@app.route("/auth/google")
def google_login():
    cfg = get_google_provider_cfg()
    return redirect(f"{cfg['authorization_endpoint']}?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={get_google_redirect_uri()}&scope=openid%20email%20profile")

@app.route("/auth/google/callback")
def google_callback():
    code = request.args.get("code")
    cfg = get_google_provider_cfg()
    token_res = requests.post(cfg["token_endpoint"], data={"code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "redirect_uri": get_google_redirect_uri(), "grant_type": "authorization_code"}).json()
    userinfo = requests.get(cfg["userinfo_endpoint"], headers={"Authorization": f"Bearer {token_res['access_token']}"}).json()
    session["user"] = {"email": userinfo["email"], "name": userinfo["name"], "picture": userinfo["picture"]}
    return redirect(url_for("home"))

@app.route("/get_nearby_stations")
def get_nearby_stations():
    try:
        lat, lon = float(request.args.get('lat')), float(request.args.get('lon'))
        overpass_url = "http://overpass-api.de/api/interpreter"
        for radius in [2000, 5000, 10000]:
            query = f'[out:json][timeout:15];(node["amenity"="police"](around:{radius},{lat},{lon});way["amenity"="police"](around:{radius},{lat},{lon}););out center;'
            response = requests.get(overpass_url, params={'data': query}, timeout=15).json()
            elements = response.get('elements', [])
            if elements:
                for el in elements:
                    s_lat, s_lon = el.get('lat') or el.get('center', {}).get('lat'), el.get('lon') or el.get('center', {}).get('lon')
                    el['distance'] = haversine(lat, lon, s_lat, s_lon)
                elements.sort(key=lambda x: x['distance'])
                return {"elements": elements[:4]}
        return {"elements": []}
    except Exception as e: return {"error": str(e)}, 500

@app.route("/generate_complaint", methods=["POST"])
def generate_complaint():
    data = request.json
    incident, details, location = data.get('incident', 'General'), data.get('details', 'N/A'), data.get('location', 'N/A')
    recipient, subject = "helpline@police.gov.in", f"Legal Complaint: {incident}"
    body = f"To,\nThe SHO,\n{location}\n\nSubject: Formal complaint regarding {incident}.\n\nRespected Sir/Madam,\n\nI report an incident at {location}. Details: {details}.\n\nSincerely,\n{session.get('user', {}).get('name', 'Citizen')}"
    mailto_link = f"mailto:{recipient}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    return jsonify({"mailto_link": mailto_link, "preview": body})


@app.route("/rasa_proxy", methods=["POST"])
def rasa_proxy():
    user_data = request.json
    user_text = user_data.get("message", "").strip()

    # Capture metadata if it exists
    metadata = user_data.get("metadata", {})

    try:
        detected_lang = detect(user_text)
        target_langs = ['hi', 'ml']
        is_legal_query = any(keyword in user_text.upper() for keyword in ["IPC", "BNS", "SECTION", "ARTICLE", "⚖️"])
        is_short = len(user_text.split()) < 3
        should_translate = detected_lang in target_langs and (not is_short or is_legal_query)

        if should_translate:
            user_data['message'] = GoogleTranslator(source=detected_lang, target='en').translate(user_text)

        # Ensure user_data (which now contains metadata from the frontend) is sent
        rasa_response = requests.post("http://127.0.0.1:5005/webhooks/rest/webhook", json=user_data, timeout=60).json()

        if should_translate:
            back_translator = GoogleTranslator(source='en', target=detected_lang)
            for res in rasa_response:
                if 'text' in res:
                    res['text'] = back_translator.translate(res['text'])

        return jsonify(rasa_response)
    except:
        rasa_response = requests.post("http://127.0.0.1:5005/webhooks/rest/webhook", json=user_data, timeout=60).json()
        return jsonify(rasa_response)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/locator")
def locator():
    if "user" not in session:
        return redirect(url_for("signup_view"))
    return render_template("locator.html")

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)