import os
import logging
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
CLIENT_SECRETS_FILE = 'client_secrets.json'
TOKEN_PICKLE_FILE = 'token.pickle'

def get_authenticated_service():
    """Authenticates the user and returns a YouTube API service object."""
    credentials = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        try:
            with open(TOKEN_PICKLE_FILE, 'rb') as token:
                credentials = pickle.load(token)
        except Exception as e:
            logging.error(f"Error loading token file: {e}, attempting re-authentication.")
            credentials = None

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logging.info("Credentials refreshed successfully.")
            except Exception as e:
                logging.warning(f"Could not refresh credentials: {e}. Need re-authentication.")
                if os.path.exists(TOKEN_PICKLE_FILE):
                    os.remove(TOKEN_PICKLE_FILE) # Remove invalid token
                credentials = None
        # Re-authenticate if needed
        if not credentials:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                 logging.error(f"'{CLIENT_SECRETS_FILE}' not found. Please download it from Google Cloud Console.")
                 raise FileNotFoundError(f"'{CLIENT_SECRETS_FILE}' not found.")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                # Use run_local_server which handles browser opening and redirect URI better for web context
                credentials = flow.run_local_server(port=0) # Dynamically find a free port
                logging.info("Authentication successful.")
                # Save the credentials for the next run
                try:
                    with open(TOKEN_PICKLE_FILE, 'wb') as token:
                        pickle.dump(credentials, token)
                    logging.info(f"Credentials saved to {TOKEN_PICKLE_FILE}")
                except Exception as e:
                    logging.error(f"Error saving token file: {e}")
            except Exception as e:
                logging.error(f"Authentication flow failed: {e}")
                return None

    # Build the YouTube API service
    try:
        youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
        # Log successful service build
        # logging.info("YouTube service authenticated and built successfully.")
        return youtube_service
    except HttpError as e:
        logging.error(f'An HTTP error {e.resp.status} occurred building service: {e.content}')
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
        logging.error("YouTube service not authenticated for get_all_subscriptions.")
        return None # Return None on failure

    subscriptions = []
    next_page_token = None
    logging.info("Fetching subscriptions from YouTube API...")
    page_count = 0
    max_pages = 50 # Safety break to avoid infinite loops

    while True and page_count < max_pages:
        page_count += 1
        try:
            request = youtube_service.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=next_page_token,
                order="alphabetical"
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
                break

        except HttpError as e:
            logging.error(f'An HTTP error {e.resp.status} occurred while fetching subscriptions page {page_count}: {e.content}')
            return None # Indicate failure
        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching subscriptions page {page_count}: {e}")
            return None # Indicate failure

    if page_count >= max_pages:
         logging.warning(f"Stopped fetching subscriptions after {max_pages} pages. Potential issue?")

    logging.info(f"Fetched {len(subscriptions)} subscriptions across {page_count} pages.")
    return subscriptions

# --- NUEVA FUNCIÓN ---
def get_my_channel_info(youtube_service):
    """Fetches the authenticated user's own channel title."""
    if not youtube_service:
        logging.error("YouTube service not authenticated for get_my_channel_info.")
        return None

    try:
        request = youtube_service.channels().list(
            part="snippet",
            mine=True,
            maxResults=1 # Should only be one channel
        )
        response = request.execute()

        items = response.get('items', [])
        if items:
            title = items[0].get('snippet', {}).get('title')
            logging.info(f"Fetched user's channel title: {title}")
            return title
        else:
            logging.warning("Could not find channel information for the authenticated user.")
            return None
    except HttpError as e:
        logging.error(f'An HTTP error {e.resp.status} occurred fetching user channel info: {e.content}')
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred fetching user channel info: {e}")
        return None
# --- FIN NUEVA FUNCIÓN ---
