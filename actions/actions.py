import os
import re
import requests
import pandas as pd
from typing import Any, Text, Dict, List
from math import radians, cos, sin, asin, sqrt
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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
        else:
            final_match = matches[0]
            raw_text = final_match['text']
            act_label = final_match['label']

            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are NiDi, a helpful legal assistant. Explain legal provisions in very simple, easy-to-understand terms for common citizens. Keep it concise but helpful."},
                        {"role": "user", "content": f"Explain {act_label} Section/Article {display_section} simply based on this text: {raw_text}"}
                    ]
                )
                ai_explanation = completion.choices[0].message.content
                dispatcher.utter_message(text=f"⚖️ **{act_label} - {display_section}**\n\n{ai_explanation}")
            except Exception as e:
                dispatcher.utter_message(text=f"⚖️ **{act_label} - {display_section}**:\n\n{raw_text}")
                print(f"Groq API Error: {e}")

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

        lat, lon = float(location['lat']), float(location['lon'])
        overpass_url = "http://overpass-api.de/api/interpreter"

        final_stations = []
        for radius in [2000, 5000, 10000]:
            overpass_query = f"""
            [out:json];
            (
              node["amenity"="police"](around:{radius},{lat},{lon});
              way["amenity"="police"](around:{radius},{lat},{lon});
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

                if len(stations) >= 3 or radius == 10000:
                    stations.sort(key=lambda x: x['distance'])
                    final_stations = stations[:4]
                    break
            except:
                continue

        if not final_stations:
            dispatcher.utter_message(text="I couldn't find any police stations even within 10km.")
        else:
            dispatcher.utter_message(
                text=f"I found {len(final_stations)} stations near you:",
                json_message={"type": "station_list", "data": final_stations}
            )

        return []

class ActionPrepareComplaint(Action):
    def name(self) -> Text:
        return "action_prepare_complaint"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        incident = tracker.get_slot("incident_type") or "incident"
        details = tracker.get_slot("incident_details") or "No details provided"
        location = tracker.get_slot("incident_location") or "the specified area"

        to_field = f"Station House Officer,\nPolice Station, {location}"
        subject_field = f"Formal Complaint regarding {incident}"
        body_field = (
            f"I wish to report a {incident} that occurred at {location}. "
            f"Details: {details}. "
            f"I request you to kindly investigate this matter and take appropriate action."
        )

        dispatcher.utter_message(
            text=f"I have generated your draft for {incident}.",
            json_message={
                "type": "complaint_draft",
                "data": {
                    "to": to_field,
                    "subject": subject_field,
                    "body": body_field
                }
            }
        )
        return []

class ValidateComplaintForm(ValidationAction):
    def name(self) -> Text:
        return "validate_complaint_form"

    def validate_incident_details(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if len(slot_value) < 10:
            dispatcher.utter_message(text="Please provide a more detailed description so the draft is accurate.")
            return {"incident_details": None}
        return {"incident_details": slot_value}

if __name__ == "__main__":
    test_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": "Explain why fast inference is critical for reasoning models"
            }
        ]
    )
    print(test_completion.choices[0].message.content)