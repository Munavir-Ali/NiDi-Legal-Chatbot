# app.py

from flask import Flask, render_template
from pymongo import MongoClient
import urllib.parse
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
from bson.json_util import dumps
import plotly.utils

# ==================================
# === DATABASE CONFIGURATION ===
# ==================================
MONGO_PASSWORD = "nidi@2022-2026"
ENCODED_PASSWORD = urllib.parse.quote_plus(MONGO_PASSWORD)
MONGO_URI = f"mongodb+srv://nidi_user0:{ENCODED_PASSWORD}@nidi.qkiysav.mongodb.net/?appName=NiDi"
DATABASE_NAME = "NiDi_DB"

# Initialize Flask App
app = Flask(__name__)

client = MongoClient(MONGO_URI, tlsInsecure=True)
db = client[DATABASE_NAME]


@app.route('/')
def dashboard():
    """
    Renders the main dashboard page with the combined Bar and Line chart for Total Cases.
    """
    # 1. Fetch Data from MongoDB
    total_cases_cursor = db['total_cases'].find({})
    total_cases_list = json.loads(dumps(total_cases_cursor))
    df = pd.DataFrame(total_cases_list)

    if df.empty:
        return "No data found in MongoDB for visualization.", 500

    # 2. Prepare Data and Columns
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
    df['Total'] = pd.to_numeric(df['Total'], errors='coerce')
    df = df.dropna(subset=['Year', 'Total'])
    df = df.sort_values(by='Year')

    # 3. Create Combined Plotly Visualization (Bar + Smoothed Line)
    fig = go.Figure()

    # Add the Bar trace (blue bars)
    fig.add_trace(go.Bar(
        x=df['Year'],
        y=df['Total'],
        name='Cases',
        marker_color='#63B3ED'  # Light blue color
    ))

    # Add the Line trace (black trend line with orange markers)
    fig.add_trace(go.Scatter(
        x=df['Year'],
        y=df['Total'],
        name='Trend',
        mode='lines+markers',
        # Added smoothing (spline) for the curve to match the source image
        line=dict(color='black', width=2, shape='spline'),
        marker=dict(color='orange', size=8, line=dict(width=1, color='black'))
    ))

    # Update Layout for Titles and Axes
    fig.update_layout(
        title={
            'text': 'Total Crime Cases Registered',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'},

        # Y-axis title adjustment
        yaxis_title='No. of cases registered',

        # Annotation for the secondary title ("Total crimes (IPC + SLL)")
        annotations=[
            dict(
                x=0.01,
                y=1.05,
                xref='paper', yref='paper',
                text='Total crimes (IPC + SLL)',
                showarrow=False,
                font=dict(size=14, color='black')
            )
        ],
        xaxis_title='Year',
        hovermode="x unified",
        template='plotly_white'
    )

    # 4. Render Template
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template('index.html', graphJSON=graph_json)


if __name__ == '__main__':
    app.run(debug=True)