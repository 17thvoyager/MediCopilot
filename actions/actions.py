import pymongo
import certifi
from datetime import datetime
from typing import Any, Text, Dict, List

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