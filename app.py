from flask import Flask, render_template, url_for
from pymongo import MongoClient
import urllib.parse
import plotly.graph_objects as go
import pandas as pd
import json
from bson.json_util import dumps
import plotly.utils
import certifi
import sys
import ssl

app = Flask(__name__)

MONGO_PASSWORD = "nidi@2022-2026"
ENCODED_PASSWORD = urllib.parse.quote_plus(MONGO_PASSWORD)
MONGO_URI = f"mongodb+srv://nidi_user0:{ENCODED_PASSWORD}@nidi.qkiysav.mongodb.net/?appName=NiDi"

try:
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000
    )
    db = client["NiDi_DB"]
    client.admin.command('ping')
except Exception as e:
    sys.exit(1)

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
                        x=x_data,
                        y=y_data,
                        marker=dict(
                            color='#1e3a66',
                            line=dict(color='#ffffff', width=1)
                        ),
                        opacity=0.8,
                        name='Bar'
                    ))
                    fig.add_trace(go.Scatter(
                        x=x_data,
                        y=y_data,
                        mode='lines+markers',
                        line=dict(color='#2a5aa8', width=3),
                        marker=dict(size=8, color='#1e3a66', line=dict(width=1, color='white')),
                        name='Trend'
                    ))

                    fig.update_layout(
                        title={'text': display_title, 'x': 0.5, 'font': {'color': '#1e3a66', 'size': 18, 'family': 'Segoe UI'}},
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        showlegend=False,
                        xaxis=dict(
                            gridcolor='#dbe1ec',
                            tickfont=dict(color='#4b5563'),
                            showline=True,
                            linecolor='#1e3a66'
                        ),
                        yaxis=dict(
                            gridcolor='#dbe1ec',
                            tickfont=dict(color='#4b5563'),
                            showline=True,
                            linecolor='#1e3a66'
                        ),
                        margin=dict(l=50, r=20, t=60, b=40),
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

@app.route("/login")
def login():
    return render_template("account.html")

@app.route("/admin")
def admin():
    return render_template("admin_login.html")

@app.route("/chat")
def chat():
    graphs = get_crime_stats()
    return render_template("botinterface.html", all_graphs=graphs)

@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")

@app.route("/forgot")
def forgot():
    return render_template("forgotpswd.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)