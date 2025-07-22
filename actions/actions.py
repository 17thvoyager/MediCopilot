import pymongo
import certifi
from datetime import datetime
from typing import Any, Text, Dict, List

from urllib.parse import quote

import requests
import xml.etree.ElementTree as ET 

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
#kkkkksdfsdfsdfsdf
# --- DATABASE CONNECTION ---
MONGO_CONNECTION_STRING = "mongodb+srv://maxpbav:zCiaKHzaCZuyKzHM@cluster0.7rclpcl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = pymongo.MongoClient(MONGO_CONNECTION_STRING, tlsCAFile=certifi.where())
db = client["MediCopilotDB"]  # This creates a database named MediCopilotDB
symptom_collection = db["symptoms"] # This creates a collection (like a table) named "symptoms"
# -------------------------


class ActionSaveSymptoms(Action):

    def name(self) -> Text:
        return "action_save_symptoms"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Get the user's ID from the conversation tracker
        user_id = tracker.sender_id

        # Get the list of entities extracted by Rasa NLU
        # We look for the 'symptom' and 'body_part' entities
        symptoms = [e["value"] for e in tracker.latest_message['entities'] if e['entity'] == 'symptom']
        body_parts = [e["value"] for e in tracker.latest_message['entities'] if e['entity'] == 'body_part']
        
        # Combine them into one list for simplicity
        all_symptoms = symptoms + body_parts

        # If no symptoms were detected, we don't need to do anything
        if not all_symptoms:
            dispatcher.utter_message(text="I see. Could you please describe your symptoms in more detail?")
            return []

        # Create a record to save in the database
        symptom_record = {
            "user_id": user_id,
            "symptoms": all_symptoms,
            "timestamp": datetime.utcnow()
        }

        # Insert the record into the MongoDB collection
        try:
            symptom_collection.insert_one(symptom_record)
            dispatcher.utter_message(text=f"Thank you for sharing. I've noted that you're experiencing: {', '.join(all_symptoms)}.")
        except Exception as e:
            print(f"Error saving to database: {e}")
            dispatcher.utter_message(text="I'm having trouble noting that down right now. Please try again in a moment.")

        return []

class ActionDescribeDisease(Action):

    def name(self) -> Text:
        return "action_describe_disease"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # 1. Get the disease entity
        disease_query = next(tracker.get_latest_entity_values("disease"), None)

        if not disease_query:
            dispatcher.utter_message(text="What condition would you like to know about?")
            return []

        # 2. Prepare the API request (this time, no special headers)
        api_url = f"https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&term={quote(disease_query)}"

        try:
            # 3. Make the API call
            response = requests.get(api_url)
            response.raise_for_status()

            # 4. Parse the XML response
            root = ET.fromstring(response.content)
            list_element = root.find('list')

            # Check if any results were returned
            if list_element is not None and int(list_element.get('n', 0)) > 0:
                documents = list_element.findall('document')
                
                if len(documents) == 1:
                    # Perfect match
                    doc = documents[0]
                    title_element = doc.find("content[@name='title']")
                    summary_element = doc.find("content[@name='FullSummary']")
                    
                    title = title_element.text if title_element is not None else "N/A"
                    summary = summary_element.text if summary_element is not None else "No summary available."
                    
                    message = f"Here is some information about **{title}** from MedlinePlus:\n\n{summary}"
                    dispatcher.utter_message(text=message)
                else:
                    # Multiple matches
                    suggestions = []
                    for doc in documents[:3]: # Get top 3 suggestions
                        title_element = doc.find("content[@name='title']")
                        if title_element is not None:
                            suggestions.append(title_element.text)
                    
                    message = f"I found a few potential matches for '{disease_query}'. Did you mean one of these? \n- " + "\n- ".join(suggestions)
                    dispatcher.utter_message(text=message)
            else:
                # No results found
                message = f"I'm sorry, I couldn't find any information on '{disease_query}' in the MedlinePlus database. Please try a different term or consult a medical professional."
                dispatcher.utter_message(text=message)

        except requests.exceptions.RequestException as e:
            # Handle network errors
            print(f"API Request Error: {e}")
            message = "I'm having trouble accessing my knowledge base right now. Please check your connection and try again."
            dispatcher.utter_message(text=message)
        except ET.ParseError as e:
            # Handle cases where the response is not valid XML
            print(f"XML Parse Error: {e}")
            message = "I received a response from the knowledge base, but I couldn't understand it. Please try again."
            dispatcher.utter_message(text=message)
            
        return []        