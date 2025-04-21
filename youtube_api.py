import os
import logging
import pickle # Using pickle for token storage is common, but json is also fine

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Scopes required by the application
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
CLIENT_SECRETS_FILE = 'client_secrets.json'
TOKEN_PICKLE_FILE = 'token.pickle' # Or use token.json

def get_authenticated_service():
    """Authenticates the user and returns a YouTube API service object."""
    credentials = None

    # Load credentials if they exist
    if os.path.exists(TOKEN_PICKLE_FILE):
        try:
            with open(TOKEN_PICKLE_FILE, 'rb') as token:
                credentials = pickle.load(token)
        except Exception as e:
            logging.error(f"Error loading token file: {e}")
            credentials = None # Force re-authentication

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logging.info("Credentials refreshed successfully.")
            except Exception as e:
                logging.warning(f"Could not refresh credentials: {e}. Need re-authentication.")
                credentials = None # Force re-authentication
        else:
            # Run the OAuth 2.0 flow
            if not os.path.exists(CLIENT_SECRETS_FILE):
                 logging.error(f"'{CLIENT_SECRETS_FILE}' not found. Please download it from Google Cloud Console.")
                 raise FileNotFoundError(f"'{CLIENT_SECRETS_FILE}' not found.")

            try:
                # Note: InstalledAppFlow automatically handles opening the browser
                # or printing the URL for the user to visit.
                # For a web server context, Flow.from_client_secrets_file might be
                # combined with manual handling of redirect_uri if not using Flask-OAuthlib etc.
                # Using InstalledAppFlow here for simplicity as described in setup.
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                # This will block until the user completes the flow (might require pasting code in terminal)
                credentials = flow.run_local_server(port=0) # port=0 finds a free port
                logging.info("Authentication successful.")
            except Exception as e:
                logging.error(f"Authentication flow failed: {e}")
                return None # Indicate failure

        # Save the credentials for the next run
        try:
            with open(TOKEN_PICKLE_FILE, 'wb') as token:
                pickle.dump(credentials, token)
            logging.info(f"Credentials saved to {TOKEN_PICKLE_FILE}")
        except Exception as e:
            logging.error(f"Error saving token file: {e}")

    # Build the YouTube API service
    try:
        youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
        return youtube_service
    except HttpError as e:
        logging.error(f'An HTTP error {e.resp.status} occurred: {e.content}')
        # Potentially delete token file if auth related?
        if e.resp.status in [401, 403] and os.path.exists(TOKEN_PICKLE_FILE):
            logging.warning("Received auth error, removing potentially invalid token file.")
            os.remove(TOKEN_PICKLE_FILE)
        return None
    except Exception as e:
        logging.error(f"Failed to build YouTube service: {e}")
        return None


def get_all_subscriptions(youtube_service):
    """Fetches all subscribed channels for the authenticated user."""
    if not youtube_service:
        logging.error("YouTube service not authenticated.")
        return []

    subscriptions = []
    next_page_token = None

    logging.info("Fetching subscriptions from YouTube API...")
    while True:
        try:
            request = youtube_service.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=50, # Max allowed per page
                pageToken=next_page_token,
                order="alphabetical" # Optional: order by title
            )
            response = request.execute()

            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                channel_id = snippet.get('resourceId', {}).get('channelId')
                title = snippet.get('title')
                thumbnail_url = snippet.get('thumbnails', {}).get('default', {}).get('url')

                if channel_id and title:
                    subscriptions.append({
                        'channel_id': channel_id,
                        'title': title,
                        'thumbnail_url': thumbnail_url
                    })

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break # Exit loop if no more pages

        except HttpError as e:
            logging.error(f'An HTTP error {e.resp.status} occurred while fetching subscriptions: {e.content}')
            break # Stop fetching on error
        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching subscriptions: {e}")
            break

    logging.info(f"Fetched {len(subscriptions)} subscriptions.")
    return subscriptions
