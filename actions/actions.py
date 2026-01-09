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

        legal_section_raw = tracker.get_slot('legal_section')

        if not legal_section_raw:
            dispatcher.utter_message(text="I couldn't identify the section. Which one are you looking for?")
            return []

        clean_query = re.sub(r'(?i)article|section|of|indian|constitution|ipc|crpc|bns|bsa|the', '',
                             legal_section_raw).strip().lower()

        data_path = os.path.join(os.getcwd(), "legal_data")
        files = ['bsa_sections.xlsx', 'bns_sections.xlsx', 'ipc_sections.xlsx', 'crpc_sections.xlsx', 'Final_IC.xlsx']

        found_text = None
        matched_file = ""

        for file in files:
            path = os.path.join(data_path, file)
            if not os.path.exists(path):
                continue

            try:
                if file.endswith('.csv'):
                    df = pd.read_csv(path)
                    df['article_id'] = df['article_id'].astype(str).str.strip().str.lower()
                    result = df[df['article_id'] == clean_query]
                    if not result.empty:
                        found_text = result.iloc[0]['article_desc']
                        matched_file = "Constitution"
                        break
                else:
                    df = pd.read_excel(path)
                    search_col = 'Section' if 'Section' in df.columns else 'Section _name'

                    df[search_col] = df[search_col].astype(str).str.strip().str.lower()
                    result = df[df[search_col] == clean_query]

                    if not result.empty:
                        found_text = result.iloc[0]['Description']
                        matched_file = file.split('_')[0].upper()
                        break
            except Exception as e:
                print(f"Error reading {file}: {e}")

        if found_text:
            dispatcher.utter_message(text=f"⚖️ **{matched_file} - {legal_section_raw.title()}**:\n\n{found_text}")
        else:
            dispatcher.utter_message(
                text=f"I found '{legal_section_raw}' in my list, but couldn't find its details in the {matched_file if matched_file else 'datasets'}. Try asking for just the number, e.g., 'What is Article 1?'")

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
