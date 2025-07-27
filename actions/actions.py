import pymongo
import certifi

import re

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

# Make sure this import is at the top of the file

class ActionDescribeDisease(Action):

    def name(self) -> Text:
        return "action_describe_disease"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        disease_query = next(tracker.get_latest_entity_values("disease"), None)
        if not disease_query:
            dispatcher.utter_message(text="What condition would you like to know about?")
            return []

        api_url = f"https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&term={quote(disease_query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            
            # --- NEW SIMPLIFIED LOGIC ---
            # Find the first 'document' tag directly within the XML root
            first_doc = root.find(".//document")

            if first_doc is not None:
                # If we found at least one document, parse it
                title_element = first_doc.find("content[@name='title']")
                summary_element = first_doc.find("content[@name='FullSummary']")
                
                title_text = title_element.text if title_element is not None else "N/A"
                summary_text = summary_element.text if summary_element is not None else "No summary available."

                # Clean the HTML tags from the text
                clean_title = re.sub('<[^<]+?>', '', title_text)
                clean_summary = re.sub('<[^<]+?>', '', summary_text)
                
                message = f"Here is some information about **{clean_title}** from MedlinePlus:\n\n{clean_summary}"
                dispatcher.utter_message(text=message)
            else:
                # If no <document> tag was found anywhere in the response
                message = f"I'm sorry, I couldn't find any information on '{disease_query}' in the MedlinePlus database. Please try a different term."
                dispatcher.utter_message(text=message)
            # --- END OF NEW LOGIC ---

        except requests.exceptions.RequestException as e:
            print(f"API Request Error: {e}")
            message = "I'm having trouble accessing my knowledge base right now."
            dispatcher.utter_message(text=message)
        except ET.ParseError as e:
            print(f"XML Parse Error: {e}")
            message = "I received a response from the knowledge base, but I couldn't understand it."
            dispatcher.utter_message(text=message)
            
        return []



# This comes after your ActionDescribeDisease class

class ActionWellnessInfo(Action):

    def name(self) -> Text:
        return "action_wellness_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # 1. Get the 'wellness_topic' entity instead of 'disease'
        topic_query = next(tracker.get_latest_entity_values("wellness_topic"), None)
        if not topic_query:
            dispatcher.utter_message(text="What wellness topic are you interested in?")
            return []

        # 2. Prepare the API request - this is all the same logic we debugged
        api_url = f"https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&term={quote(topic_query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            first_doc = root.find(".//document")

            if first_doc is not None:
                title_element = first_doc.find("content[@name='title']")
                summary_element = first_doc.find("content[@name='FullSummary']")
                
                title_text = title_element.text if title_element is not None else "N/A"
                summary_text = summary_element.text if summary_element is not None else "No summary available."

                clean_title = re.sub('<[^<]+?>', '', title_text)
                clean_summary = re.sub('<[^<]+?>', '', summary_text)
                
                # 3. IMPORTANT: Add the wellness disclaimer to the message
                message = (f"Here is some general information about **{clean_title}** from MedlinePlus:\n\n"
                           f"{clean_summary}\n\n"
                           f"--- \n"
                           f"*For personal health or dietary advice, it's always best to speak with a doctor or registered dietitian.*")
                dispatcher.utter_message(text=message)
            else:
                message = (f"I couldn't find specific information on '{topic_query}' in my knowledge base. "
                           f"For personal health questions, please consult a healthcare professional.")
                dispatcher.utter_message(text=message)

        except Exception as e:
            # This generic error handling will catch our RequestException and ParseError
            print(f"An error occurred in ActionWellnessInfo: {e}")
            dispatcher.utter_message(text="I'm having trouble accessing my knowledge base right now. Please try again in a moment.")
            
        return []
    

 # In actions/actions.py

class ActionBenefitInfo(Action):

    def name(self) -> Text:
        return "action_benefit_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        topic_query = next(tracker.get_latest_entity_values("wellness_topic"), None)
        if not topic_query:
            dispatcher.utter_message(text="What topic's benefits are you interested in?")
            return []

        # --- This is the new, conversational part ---
        # A dictionary of conversational "lead-in" text
        lead_in_text = {
            "probiotics": "Yes, many people find probiotics beneficial for gut health.",
            "sleep": "Absolutely, getting enough quality sleep is crucial for overall health.",
            "meditation": "Yes, meditation is widely considered to have many benefits for mental and physical well-being.",
            "vitamins": "Vitamins are essential for your body to function properly."
        }
        
        # Use the synonym "Probiotics" to find the lead-in for "yogurt"
        canonical_topic = tracker.get_slot("wellness_topic") or topic_query

        # Start building the final message
        final_message = lead_in_text.get(canonical_topic, f"Regarding {canonical_topic}, here is some general information.")
        final_message += "\n\nMedlinePlus provides more detail:\n\n"
        # --- End of new part ---

        # Now, we do the same API call as before to get the details
        api_url = f"https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&term={topic_query}"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            list_element = root.find('list')

            if list_element is not None and int(list_element.get('n', 0)) > 0:
                doc = list_element.find('document')
                if doc is not None:
                    summary_element = doc.find("content[@name='FullSummary']")
                    summary = summary_element.text if summary_element is not None else "No detailed summary available."
                    final_message += summary
            else:
                final_message += "I couldn't find a detailed summary in my knowledge base."

        except Exception as e:
            print(f"API Error in ActionBenefitInfo: {e}")
            final_message += "I'm having trouble accessing my knowledge base for more details right now."
        
        # Add the final disclaimer
        final_message += "\n\n*For personal health or dietary advice, it's always best to speak with a doctor or registered dietitian.*"
        dispatcher.utter_message(text=final_message)

        return []   