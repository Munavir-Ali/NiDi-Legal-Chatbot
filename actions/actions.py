from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import pandas as pd
import os
import re


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

        if not matches:
            dispatcher.utter_message(text=f"No details found for {legal_section_raw}.")
        elif len(matches) == 1:
            dispatcher.utter_message(
                text=f"⚖️ **{matches[0]['label']} - {legal_section_raw.upper()}**:\n\n{matches[0]['text']}")
        else:
            options = ", ".join([m['label'] for m in matches])
            dispatcher.utter_message(
                text=f"I found Section {clean_query} in multiple acts: {options}. Which one did you mean?")
            dispatcher.utter_message(text=f"Displaying **{matches[0]['label']}** result:\n\n{matches[0]['text']}")

        return []


# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []
