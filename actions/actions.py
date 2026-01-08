from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import pandas as pd
import os


class ActionGetLegalDescription(Action):
    def name(self) -> Text:
        return "action_get_legal_description"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Get the section name from the bot's memory
        legal_section = tracker.get_slot('legal_section')

        if not legal_section:
            dispatcher.utter_message(text="I couldn't identify the section. Which one are you looking for?")
            return []

        # Path to your project data
        data_path = r'D:\Project_NiDi\Project_Data_Folder'
        files = ['bsa_sections.xlsx', 'bns_sections.xlsx', 'ipc_sections.xlsx', 'crpc_sections.xlsx', 'Final_IC.csv']

        found_text = None

        # Search through all files
        for file in files:
            path = os.path.join(data_path, file)
            if not os.path.exists(path):
                continue

            try:
                if file.endswith('.csv'):
                    df = pd.read_csv(path)
                    # Clean the data: remove extra spaces from the ID column
                    df['article_id'] = df['article_id'].astype(str).str.strip()

                    # Improved search: Exact match after stripping spaces
                    result = df[df['article_id'].str.lower() == legal_section.lower().strip()]

                    if not result.empty:
                        found_text = result.iloc[0]['article_desc']
                        break
                else:
                    df = pd.read_excel(path)
                    search_col = 'Section' if 'Section' in df.columns else 'Section _name'

                    # Clean and search for Excel files
                    df[search_col] = df[search_col].astype(str).str.strip()
                    result = df[df[search_col].str.lower() == legal_section.lower().strip()]

                    if not result.empty:
                        found_text = result.iloc[0]['Description']
                        break
            except Exception as e:
                print(f"Error reading {file}: {e}")

        if found_text:
            dispatcher.utter_message(text=f"Details for {legal_section}:\n\n{found_text}")
        else:
            dispatcher.utter_message(
                text=f"I found '{legal_section}' in my list, but I couldn't find the detailed description in the datasets.")

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
