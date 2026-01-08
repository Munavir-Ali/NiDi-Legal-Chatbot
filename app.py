# app.py
from flask import Flask, render_template
from pymongo import MongoClient
import urllib.parse
import plotly.graph_objects as go
import pandas as pd
import json
from bson.json_util import dumps
import plotly.utils
import certifi
import sys

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
MONGO_PASSWORD = "nidi@2022-2026"
ENCODED_PASSWORD = urllib.parse.quote_plus(MONGO_PASSWORD)
MONGO_URI = f"mongodb+srv://nidi_user0:{ENCODED_PASSWORD}@nidi.qkiysav.mongodb.net/?appName=NiDi"

try:
    ca = certifi.where()
    client = MongoClient(MONGO_URI, tlsCAFile=ca, serverSelectionTimeoutMS=5000)
    db = client["NiDi_DB"]
    client.admin.command('ping')
except Exception as e:
    print(f"CRITICAL DATABASE ERROR: {e}")
    sys.exit(1)

@app.route('/')
def dashboard():
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

                # Clean title: Remove underscores and capitalize
                display_title = col_name.replace('_', ' ').upper()

                # 1. Check for 'Wide' format (Years like 2020, 2021 are column names)
                year_cols = [c for c in df.columns if c.isdigit() and len(c) == 4]

                if year_cols:
                    # Logic for Cyber/IPC: Pick the row that looks like a 'Total' or just the first row
                    row_idx = 0
                    if 'Crime_Heads' in df.columns:
                        total_rows = df[df['Crime_Heads'].str.contains('Total', na=False)].index
                        if not total_rows.empty:
                            row_idx = total_rows[0]

                    x_data = year_cols
                    y_data = [pd.to_numeric(df.loc[row_idx, yr], errors='coerce') for yr in year_cols]

                # 2. Check for 'Tall' format (Has a column specifically named 'Year')
                elif 'Year' in df.columns:
                    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
                    # Find the count column (Total, Cases, or the last column)
                    potential_y = ['Total', 'Cases', 'No. of cases']
                    count_col = next((c for c in potential_y if c in df.columns), df.columns[-1])

                    df = df.dropna(subset=['Year']).sort_values('Year')
                    x_data = df['Year']
                    y_data = pd.to_numeric(df[count_col], errors='coerce')

                # 3. Check for District-based format (POCSO)
                elif 'District' in df.columns:
                    df = df[~df['District'].str.contains('Total', na=False)]
                    x_data = df['District']
                    count_col = [c for c in df.columns if 'Total' in c][0]
                    y_data = pd.to_numeric(df[count_col], errors='coerce')

                # Build the Chart if we found data
                if len(x_data) > 0:
                    fig.add_trace(go.Bar(x=x_data, y=y_data, marker_color='#9290C3'))
                    fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='lines+markers', line=dict(color='#FFFFFF')))

                    fig.update_layout(
                        title={'text': display_title, 'x': 0.5, 'font': {'color': 'white'}},
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(gridcolor='#535C91', tickfont=dict(color='white')),
                        yaxis=dict(gridcolor='#535C91', tickfont=dict(color='white')),
                        margin=dict(l=40, r=40, t=60, b=40)
                    )
                    all_graphs_json.append(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))
        except Exception as e:
            print(f"Error loading {col_name}: {e}")

    return render_template('index.html', all_graphs=all_graphs_json)

if __name__ == '__main__':
    app.run(debug=True, port=5000)