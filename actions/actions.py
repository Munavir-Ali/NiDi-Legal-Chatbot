import os
import re
import requests
import pandas as pd
from typing import Any, Text, Dict, List
from math import radians, cos, sin, asin, sqrt
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction
from rasa_sdk.events import SlotSet
from groq import Groq
# import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# L1 CONFIGURATION (GROQ - PRIMARY)
# ==========================================
client = Groq(api_key=os.environ.get("L1_API_KEY"))

# ==========================================
# L2 CONFIGURATION (GOOGLE - COMMENTED OUT)
# ==========================================
# genai.configure(api_key=os.environ.get("L2_API_KEY"))

NIDI_INSTRUCTION = """
You are NiDi, a specialized Legal and Service Assistant for Indian Citizens. 
Your expertise is EXCLUSIVELY limited to:
1. Explaining Indian Laws (IPC and BNS).
2. Drafting legal complaints and documents.
3. Providing information about nearby police stations or legal services.

STRICT PROTOCOL:
- If a user asks a non-legal or non-service question (e.g., "Who is the President?", "Tell me a joke"), you MUST politely decline. 
- Response for off-topic queries: "I am NiDi, your specialized Legal Assistant. I can only assist with legal matters, complaints, and police-related services. Please ask a legal question."
- Always maintain a formal, professional tone.
- Do NOT include any disclaimers or "Note:" footers INSIDE drafted documents.
"""

# model = genai.GenerativeModel(
#     model_name="gemini-2.0-flash",
#     system_instruction=NIDI_INSTRUCTION
# )


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
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": NIDI_INSTRUCTION},
                        {"role": "user", "content": tracker.latest_message.get('text')}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                dispatcher.utter_message(text=chat_completion.choices[0].message.content)
            except Exception as e:
                print(f"GROQ ERROR: {e}")
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
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": NIDI_INSTRUCTION},
                    {"role": "user", "content": tracker.latest_message.get('text')}
                ],
                model="llama-3.3-70b-versatile",
            )
            dispatcher.utter_message(text=chat_completion.choices[0].message.content)
        else:
            final_match = matches[0]
            raw_text = final_match['text']
            act_label = final_match['label']

            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": NIDI_INSTRUCTION},
                        {"role": "user", "content": f"Explain {act_label} Section/Article {display_section} simply based on this text: {raw_text}"}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                ai_explanation = chat_completion.choices[0].message.content
                dispatcher.utter_message(text=f"⚖️ **{act_label} - {display_section}**\n\n{ai_explanation}")
            except Exception as e:
                dispatcher.utter_message(text=f"⚖️ **{act_label} - {display_section}**:\n\n{raw_text}")
                print(f"GROQ API Error: {e}")

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

        user_input = tracker.latest_message.get('text')

        chat_history = ""
        for event in tracker.events:
            if event.get("event") == "user":
                chat_history += f"User: {event.get('text')}\n"
            elif event.get("event") == "bot" and event.get("text"):
                chat_history += f"NiDi: {event.get('text')}\n"

        prompt = f"""
        You are NiDi, a specialized Indian Legal Assistant.

        HISTORY:
        {chat_history}

        NEW MESSAGE: "{user_input}"

        INSTRUCTIONS:
        1. Acknowledge what the user said with empathy.
        2. Identify if the following are present: Incident Type, Location, Key Details.
        3. If any detail is missing, ask for it naturally.
        4. If you have enough info, summarize it and ask: "CONFIRMED: I have the details. Shall I draft the formal complaint for you?"
        5. If the user says 'Yes', 'Draft it', or 'Sure', reply ONLY with: "DRAFTING_NOW"
        """

        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": NIDI_INSTRUCTION},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
            )
            reply = chat_completion.choices[0].message.content.strip()

            if "DRAFTING_NOW" in reply:
                draft_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": NIDI_INSTRUCTION},
                        {"role": "user", "content": f"Draft a professional police complaint for the SHO. Summary: {chat_history}. Use a formal Indian legal format."}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                draft_text = draft_completion.choices[0].message.content

                dispatcher.utter_message(
                    text="Your professional legal draft is ready.",
                    json_message={
                        "type": "complaint_draft",
                        "data": {
                            "to": "Station House Officer",
                            "subject": "Formal Complaint regarding incident",
                            "body": draft_text
                        }
                    }
                )
                return [SlotSet("incident_type", None), SlotSet("incident_details", None),
                        SlotSet("incident_location", None)]
            else:
                dispatcher.utter_message(text=reply)
        except Exception as e:
            print(f"GROQ ERROR: {e}")
            dispatcher.utter_message(text="I'm here to help. Please tell me more about the incident.")

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
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello NiDi"}],
            model="llama-3.3-70b-versatile",
        )
        print("Groq Connection Successful:", chat_completion.choices[0].message.content)
    except Exception as e:
        print("Groq Connection Failed:", e)