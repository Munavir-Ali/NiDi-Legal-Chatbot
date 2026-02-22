from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import pandas as pd
import os
import re
import requests
from math import radians, cos, sin, asin, sqrt


def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km


class ActionGetLegalDescription(Action):
    def name(self) -> Text:
        return "action_get_legal_description"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_msg = tracker.latest_message.get('text', '').upper()
        legal_section_raw = tracker.get_slot('legal_section')

        if not legal_section_raw:
            dispatcher.utter_message(text="I couldn't identify the section. Which one are you looking for?")
            return []

        clean_query = re.sub(r'(?i)article|section|of|indian|constitution|ipc|crpc|bns|bsa|the|ic', '',
                             legal_section_raw).strip().lower()

        data_path = os.path.join(os.getcwd(), "legal_data")

        all_files = {
            'BNS': 'bns_sections.xlsx',
            'BSA': 'bsa_sections.xlsx',
            'IPC': 'ipc_sections.xlsx',
            'CRPC': 'crpc_sections.xlsx',
            'IC': 'Final_IC.xlsx'
        }

        target_files = []
        if 'IPC' in user_msg:
            target_files = [('IPC', all_files['IPC'])]
        elif 'BNS' in user_msg:
            target_files = [('BNS', all_files['BNS'])]
        elif 'BSA' in user_msg:
            target_files = [('BSA', all_files['BSA'])]
        elif 'CRPC' in user_msg:
            target_files = [('CRPC', all_files['CRPC'])]
        elif any(x in user_msg for x in ['IC', 'CONSTITUTION', 'ARTICLE']):
            target_files = [('CONSTITUTION', all_files['IC'])]
        else:
            target_files = [
                ('BNS', 'bns_sections.xlsx'),
                ('BSA', 'bsa_sections.xlsx'),
                ('CONSTITUTION', 'Final_IC.xlsx'),
                ('IPC', 'ipc_sections.xlsx'),
                ('CRPC', 'crpc_sections.xlsx')
            ]

        matches = []
        for label, file_name in target_files:
            path = os.path.join(data_path, file_name)
            if not os.path.exists(path):
                continue

            try:
                df = pd.read_excel(path)

                if "Final_IC" in file_name:
                    id_col, desc_col = 'article_id', 'article_desc'
                elif "ipc_sections" in file_name:
                    id_col, desc_col = 'Section', 'Description'
                else:
                    id_col = 'Section' if 'Section' in df.columns else 'Section _name'
                    desc_col = 'Description'

                df[id_col] = df[id_col].astype(str).str.strip().str.lower()

                if "ipc_sections" in file_name:
                    df[id_col] = df[id_col].str.replace('ipc_', '', regex=False)
                elif "Final_IC" in file_name:
                    df[id_col] = df[id_col].str.replace('article ', '', regex=False).str.replace(
                        ' of indian constitution', '', regex=False)

                result = df[df[id_col] == clean_query]

                if not result.empty:
                    matches.append({
                        "label": label,
                        "text": result.iloc[0][desc_col]
                    })
            except Exception as e:
                print(f"Error processing {file_name}: {e}")

        display_section = re.sub(r'(?i)ipc|bns|bsa|crpc|article|section', '', legal_section_raw).strip().upper()

        if not matches:
            dispatcher.utter_message(text=f"No details found for {legal_section_raw}.")
        elif len(matches) == 1:
            dispatcher.utter_message(
                text=f"⚖️ **{matches[0]['label']} - {display_section}**:\n\n{matches[0]['text']}")
        else:
            options = ", ".join([m['label'] for m in matches])
            dispatcher.utter_message(
                text=f"I found Section {clean_query} in multiple acts: {options}. Which one did you mean?")
            dispatcher.utter_message(text=f"Displaying **{matches[0]['label']}** result:\n\n{matches[0]['text']}")

        return []


class ActionFindNearbyPolice(Action):
    def name(self) -> Text:
        return "action_find_nearby_police"

    def run(self, dispatcher, tracker, domain):
        metadata = tracker.get_slot("session_metadata") or {}
        location = metadata.get("location")

        if not location:
            events = tracker.current_state().get("events", [])
            for e in reversed(events):
                if e.get("event") == "user":
                    metadata = e.get("metadata", {})
                    location = metadata.get("location")
                    break

        if not location:
            dispatcher.utter_message(text="I need your location permission to find the nearest station.")
            return []

        lat, lon = location['lat'], location['lon']
        overpass_url = "http://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json];
        (
          node["amenity"="police"](around:5000,{lat},{lon});
          way["amenity"="police"](around:5000,{lat},{lon});
        );
        out center;
        """

        try:
            response = requests.get(overpass_url, params={'data': overpass_query}, timeout=10)
            elements = response.json().get('elements', [])
            stations = []

            for el in elements:
                s_lat = el.get('lat') or el.get('center', {}).get('lat')
                s_lon = el.get('lon') or el.get('center', {}).get('lon')
                tags = el.get('tags', {})
                dist = haversine(lat, lon, s_lat, s_lon)

                stations.append({
                    "name": tags.get("name", "Police Station"),
                    "address": f"{tags.get('addr:street', '')} {tags.get('addr:suburb', '')}".strip() or "Address not listed",
                    "phone": tags.get("contact:phone") or tags.get("phone") or "Contact not available",
                    "lat": s_lat, "lon": s_lon, "distance": round(dist, 2)
                })

            stations.sort(key=lambda x: x['distance'])

            if not stations:
                dispatcher.utter_message(text="I couldn't find any police stations within 5km.")
            else:
                dispatcher.utter_message(
                    text="Here are the nearest police stations to you:",
                    json_message={"type": "station_list", "data": stations[:3]}
                )
        except:
            dispatcher.utter_message(text="Service error while searching for stations.")

        return []