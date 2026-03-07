import os
import logging
import pickle
import re
from datetime import datetime, timezone

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
                    os.remove(TOKEN_PICKLE_FILE)
                credentials = None
        if not credentials:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                logging.error(f"'{CLIENT_SECRETS_FILE}' not found. Please download it from Google Cloud Console.")
                raise FileNotFoundError(f"'{CLIENT_SECRETS_FILE}' not found.")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                credentials = flow.run_local_server(port=0)
                logging.info("Authentication successful.")
                try:
                    with open(TOKEN_PICKLE_FILE, 'wb') as token:
                        pickle.dump(credentials, token)
                    logging.info(f"Credentials saved to {TOKEN_PICKLE_FILE}")
                except Exception as e:
                    logging.error(f"Error saving token file: {e}")
            except Exception as e:
                logging.error(f"Authentication flow failed: {e}")
                return None

    try:
        youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
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
        return None

    subscriptions = []
    next_page_token = None
    logging.info("Fetching subscriptions from YouTube API...")
    page_count = 0
    max_pages = 50

    while True and page_count < max_pages:
        page_count += 1
        try:
            request_params = {
                "part": "snippet",
                "mine": True,
                "maxResults": 50
            }
            if next_page_token:
                request_params["pageToken"] = next_page_token

            request = youtube_service.subscriptions().list(
                **request_params
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
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching subscriptions page {page_count}: {e}")
            return None

    if page_count >= max_pages:
        logging.warning(f"Stopped fetching subscriptions after {max_pages} pages. Potential issue?")

    logging.info(f"Fetched {len(subscriptions)} subscriptions across {page_count} pages.")
    return subscriptions


def get_my_channel_info(youtube_service):
    """Fetches the authenticated user's own channel title."""
    if not youtube_service:
        logging.error("YouTube service not authenticated for get_my_channel_info.")
        return None

    try:
        request = youtube_service.channels().list(
            part="snippet",
            mine=True,
            maxResults=1
        )
        response = request.execute()

        items = response.get('items', [])
        if items:
            title = items[0].get('snippet', {}).get('title')
            logging.info(f"Fetched user's channel title: {title}")
            return title

        logging.warning("Could not find channel information for the authenticated user.")
        return None
    except HttpError as e:
        logging.error(f'An HTTP error {e.resp.status} occurred fetching user channel info: {e.content}')
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred fetching user channel info: {e}")
        return None


def _format_duration(duration_iso):
    if not duration_iso:
        return None

    match = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', duration_iso)
    if not match:
        return None

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _load_video_durations(youtube_service, video_ids):
    durations = {}
    if not video_ids:
        return durations

    for start in range(0, len(video_ids), 50):
        chunk = video_ids[start:start + 50]
        try:
            response = youtube_service.videos().list(
                part="contentDetails",
                id=','.join(chunk),
                maxResults=50
            ).execute()
            for item in response.get('items', []):
                vid = item.get('id')
                iso_duration = item.get('contentDetails', {}).get('duration')
                durations[vid] = _format_duration(iso_duration)
        except Exception as e:
            logging.warning(f"Could not fetch video durations for chunk: {e}")

    return durations


def get_new_videos_for_channel(youtube_service, channel_id, channel_title, published_after=None, max_pages=3):
    """Fetches newest videos for a given channel, optionally after a timestamp.

    Uses channel uploads playlist instead of `search.list` to keep quota usage low.
    """
    if not youtube_service:
        return None

    try:
        channel_response = youtube_service.channels().list(
            part="contentDetails",
            id=channel_id,
            maxResults=1
        ).execute()
        channel_items = channel_response.get('items', [])
        if not channel_items:
            return []
        uploads_playlist_id = (
            channel_items[0]
            .get('contentDetails', {})
            .get('relatedPlaylists', {})
            .get('uploads')
        )
        if not uploads_playlist_id:
            return []
    except HttpError as e:
        logging.error(f"YouTube API error fetching uploads playlist for {channel_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching uploads playlist for {channel_id}: {e}")
        return None

    videos = []
    page_token = None
    pages = 0

    while pages < max_pages:
        pages += 1
        try:
            request_params = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": 50
            }
            if page_token:
                request_params["pageToken"] = page_token

            response = youtube_service.playlistItems().list(**request_params).execute()
            items = response.get('items', [])
            if not items:
                break

            for item in items:
                snippet = item.get('snippet', {})
                content_details = item.get('contentDetails', {})
                video_id = content_details.get('videoId') or snippet.get('resourceId', {}).get('videoId')
                published_at = content_details.get('videoPublishedAt') or snippet.get('publishedAt')
                if not video_id:
                    continue
                if published_after and published_at and published_at <= published_after:
                    continue

                videos.append({
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "title": snippet.get('title', 'Untitled'),
                    "published_at": published_at,
                    "thumbnail_url": snippet.get('thumbnails', {}).get('medium', {}).get('url') or snippet.get('thumbnails', {}).get('default', {}).get('url'),
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "duration_text": None
                })

            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            logging.error(f"YouTube API error fetching videos for {channel_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching videos for {channel_id}: {e}")
            return None

    duration_map = _load_video_durations(youtube_service, [video['video_id'] for video in videos])
    for video in videos:
        video['duration_text'] = duration_map.get(video['video_id'])

    videos.sort(key=lambda video: video.get('published_at') or '', reverse=True)
    return videos


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
