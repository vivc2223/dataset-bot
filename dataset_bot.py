import os
import re
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
app = Flask(*name*)
*Environment variables (you'll set these later)*
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = "appwbphX3He0xP3S1"
AIRTABLE_TABLE_NAME = "Dataset"
slack_client = WebClient(token=SLACK_BOT_TOKEN)
def get_airtable_records():
    """Fetch all records from Airtable"""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    all_records = []
    offset = None
    while True:
        params = {}
        if offset:
            params['offset'] = offset
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if 'records' in data:
            all_records.extend(data['records'])
        if 'offset' in data:
            offset = data['offset']
        else:
            break
    return all_records
def search_dataset(query):
    """Search for a dataset by ID or keyword"""
    records = get_airtable_records()
    query_lower = query.lower().strip()
    # Try to extract dataset number (e.g., "DS488", "488", "ds 488")
    dataset_pattern = r'(?:ds\s*)?(\d+)'
    match = re.search(dataset_pattern, query_lower)
    if match:
        dataset_num = match.group(1)
        # Search by dataset ID
        for record in records:
            fields = record.get('fields', {})
            dataset_id = fields.get('Dataset ID', '')
            if dataset_id.lower() == f'ds{dataset_num}' or dataset_id.lower() == dataset_num:
                return record
    # If no exact match, search by title or description
    for record in records:
        fields = record.get('fields', {})
        dataset_title = fields.get('Dataset Title', '').lower()
        dataset_id = fields.get('Dataset ID', '').lower()
        if query_lower in dataset_title or query_lower in dataset_id:
            return record
    return None
def format_dataset_response(record):
    """Format the dataset information into a Slack message"""
    fields = record.get('fields', {})
    dataset_id = fields.get('Dataset ID', 'N/A')
    dataset_title = fields.get('Dataset Title', 'N/A')
    task_domain = fields.get('Task Domain', 'N/A')
    # Get SOP link (it might be a list)
    sop_links = fields.get('Supporting Documentation (from Episode Types)', [])
    sop_link = sop_links[0] if isinstance(sop_links, list) and len(sop_links) > 0 else 'No SOP available'
    # Format the response
    response = f"_Dataset ID:_ {dataset_id}\n"
    response += f"_Task:_ {dataset_title}\n"
    response += f"_Domain:_ {task_domain}\n"
    if sop_link != 'No SOP available':
        response += f"_SOP:_ <{sop_link}>\n"
    else:
        response += f"_SOP:_ {sop_link}\n"
    return response
@app.route('/slack/events', methods=['POST'])
def slack_events():
    """Handle Slack events"""
    data = request.json
    # Handle URL verification challenge
    if 'challenge' in data:
        return jsonify({'challenge': data['challenge']})
    # Handle actual events
    if 'event' in data:
        event = data['event']
        # Ignore bot messages
        if event.get('bot_id'):
            return jsonify({'status': 'ok'})
        # Handle app mentions or direct messages
        if event.get('type') == 'app_mention' or event.get('type') == 'message':
            text = event.get('text', '')
            channel = event.get('channel')
            # Remove bot mention from text
            text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
            # Check if it's a query about a dataset
            if text:
                try:
                    record = search_dataset(text)
                    if record:
                        response_text = format_dataset_response(record)
                    else:
                        response_text = f"Sorry, I couldn't find a dataset matching '{text}'. Try searching by dataset number (e.g., DS488 or 488) or by keyword."
                    slack_client.chat_postMessage(
                        channel=channel,
                        text=response_text
                    )
                except SlackApiError as e:
                    print(f"Error posting message: {e}")
    return jsonify({'status': 'ok'})
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})
if *name* == '*main*':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
