import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify
import database as db
import youtube_api as yt
import os
import urllib.parse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-replace-in-prod')


def check_authentication():
    """Checks if the user appears to be authenticated (token exists)."""
    return os.path.exists(yt.TOKEN_PICKLE_FILE)


def group_videos_by_channel(videos):
    grouped = OrderedDict()
    for video in videos:
        channel_title = video.get('channel_title', 'Sin canal')
        grouped.setdefault(channel_title, []).append(video)
    return grouped




@app.route('/')
def index():
    """Main page: Displays channels and filters."""
    user_channel_title = None
    service = None

    if not check_authentication():
        logging.info("No token file found, attempting authentication...")
        service = yt.get_authenticated_service()
        if not service:
            return "Authentication required or failed. Please ensure you have 'client_secrets.json', necessary permissions, and run the app again to authorize.", 401
        logging.info("Authentication successful, proceeding.")
    else:
        service = yt.get_authenticated_service()
        if not service:
            logging.warning("Token found but failed to build service. Authentication might be needed.")
            return "Error connecting to YouTube service. Please try deleting token.pickle and restarting.", 500

    if service:
        user_channel_title = yt.get_my_channel_info(service)

    channels = db.get_all_channels()
    unique_tags = db.get_unique_tags()
    tag_colors = db.get_tag_colors()
    favorites_new_count = db.get_favorite_video_cache_count()

    if not channels and service and user_channel_title is not None:
        logging.info("Database is empty. Fetching subscriptions from YouTube API...")
        yt_subscriptions = yt.get_all_subscriptions(service)
        if yt_subscriptions:
            logging.info(f"Adding {len(yt_subscriptions)} channels to the database.")
            for sub in yt_subscriptions:
                db.add_or_update_channel(
                    sub['channel_id'],
                    sub['title'],
                    sub['thumbnail_url']
                )
            channels = db.get_all_channels()
            unique_tags = db.get_unique_tags()
        elif yt_subscriptions is None:
            logging.error("Failed to fetch subscriptions from YouTube API during initial load.")
            return yt.build_user_facing_error_message(
                "Error fetching subscriptions from YouTube. Please check API status or quotas.",
                error_context='subscriptions'
            ), 500
        else:
            logging.warning("Fetched no subscriptions from YouTube API during initial load.")

    return render_template(
        'index.html',
        channels=channels,
        unique_tags=unique_tags,
        tag_colors=tag_colors,
        DEFAULT_TAG_COLOR=db.DEFAULT_TAG_COLOR,
        user_channel_title=user_channel_title,
        favorites_new_count=favorites_new_count
    )


@app.route('/nuevos-favoritos')
def favorites_new_videos():
    view_mode = request.args.get('view', 'channel')
    valid_view_modes = {'channel', 'date_desc', 'date_asc', 'last_7_days', 'last_30_days'}
    if view_mode not in valid_view_modes:
        view_mode = 'channel'

    service = yt.get_authenticated_service()
    if not service:
        return "Authentication required or failed for video fetch.", 401

    favorite_channels = db.get_favorite_channels(min_rating=4)
    last_check = db.get_last_favorites_check()

    if not favorite_channels:
        return render_template(
            'favorites_new.html',
            videos_by_channel=OrderedDict(),
            total_new_videos=0,
            total_channels=0,
            warning_message=None,
            last_check=last_check,
            used_cache=False,
            view_mode=view_mode
        )

    fetched_videos = []
    warning_message = None
    used_cache = False

    for channel in favorite_channels:
        channel_videos = yt.get_new_videos_for_channel(
            service,
            channel_id=channel['channel_id'],
            channel_title=channel['title'],
            published_after=last_check,
            max_pages=3
        )
        if channel_videos is None:
            warning_message = yt.build_user_facing_error_message(
                "No se pudieron actualizar los videos en vivo de YouTube. "
                "Mostrando el último resultado cacheado.",
                error_context='favorite_videos'
            )
            used_cache = True
            break
        fetched_videos.extend(channel_videos)

    if used_cache:
        videos = db.get_favorite_video_cache()
    else:
        videos = sorted(
            fetched_videos,
            key=lambda video: (video.get('channel_title', '').lower(), video.get('published_at', '')),
            reverse=False
        )
        db.replace_favorite_video_cache(videos)
        db.set_last_favorites_check(yt.utc_now_iso())

    videos_by_channel = group_videos_by_channel(videos)
    total_channels = len(videos_by_channel)
    total_new_videos = len(videos)

    return render_template(
        'favorites_new.html',
        videos_by_channel=videos_by_channel,
        total_new_videos=total_new_videos,
        total_channels=total_channels,
        warning_message=warning_message,
        last_check=last_check,
        used_cache=used_cache,
        view_mode=view_mode
    )


@app.route('/refresh_from_youtube', methods=['POST'])
def refresh_from_youtube():
    """Fetches latest subscriptions, adds new ones, updates existing, and REMOVES unsubscribed."""
    logging.info("Attempting to refresh subscriptions from YouTube API...")
    service = yt.get_authenticated_service()
    if not service:
        return jsonify({"success": False, "message": "Authentication failed or required."}), 401

    yt_subscriptions = yt.get_all_subscriptions(service)
    if yt_subscriptions is None:
        api_error = yt.get_last_api_error() or {}
        return jsonify({
            "success": False,
            "message": yt.build_user_facing_error_message(
                "Failed to fetch subscriptions from YouTube API.",
                error_context='subscriptions'
            ),
            "error_reason": api_error.get('reason'),
            "error_status": api_error.get('status')
        }), 500

    logging.info(f"Fetched {len(yt_subscriptions)} channels from YouTube. Comparing with database...")
    api_channel_ids = {sub['channel_id'] for sub in yt_subscriptions}
    db_channel_ids = db.get_all_channel_ids()

    ids_to_delete = db_channel_ids - api_channel_ids
    new_channel_ids = list(api_channel_ids - db_channel_ids)
    if ids_to_delete:
        logging.info(f"Found {len(ids_to_delete)} channels to remove from local DB.")
        deleted_count = 0
        for channel_id in ids_to_delete:
            if db.delete_channel(channel_id):
                deleted_count += 1
        logging.info(f"Successfully removed {deleted_count} channels.")
    else:
        logging.info("No channels found to remove from local DB.")

    added_updated_count = 0
    logging.info("Adding new subscriptions and updating existing ones...")
    for sub in yt_subscriptions:
        db.add_or_update_channel(
            sub['channel_id'],
            sub['title'],
            sub['thumbnail_url']
        )
        added_updated_count += 1
    logging.info(f"Processed {added_updated_count} channels for add/update.")

    logging.info("Database update complete after refresh.")

    updated_channels = db.get_all_channels()
    updated_tags = db.get_unique_tags()
    updated_colors = db.get_tag_colors()
    return jsonify({
        "success": True,
        "message": f"Refresh complete. Found {len(yt_subscriptions)} subs. New {len(new_channel_ids)}. Removed {len(ids_to_delete)}. Processed {added_updated_count}.",
        "channels": updated_channels,
        "unique_tags": updated_tags,
        "tag_colors": updated_colors,
        "new_channel_ids": new_channel_ids
    })


@app.route('/api/tags/<channel_id>', methods=['POST'])
def update_tags(channel_id):
    data = request.get_json()
    if not data or 'tags' not in data:
        return jsonify({"success": False, "message": "Missing 'tags' in request data."}), 400

    tags_string = data['tags']
    tags_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
    success = db.update_channel_tags(channel_id, tags_list)

    if success:
        updated_channel_data = next((c for c in db.get_all_channels() if c['channel_id'] == channel_id), None)
        current_tags = updated_channel_data.get('tags', []) if updated_channel_data else []
        unique_tags = db.get_unique_tags()
        tag_colors = db.get_tag_colors()
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "tags": current_tags,
            "unique_tags": unique_tags,
            "tag_colors": tag_colors
        })

    return jsonify({"success": False, "message": "Failed to update tags in database."}), 500


@app.route('/api/tags/color/<tag_name>', methods=['POST'])
def update_tag_color(tag_name):
    data = request.get_json()
    if not data or 'color' not in data:
        return jsonify({"success": False, "message": "Missing 'color' in request data."}), 400

    color = data['color']
    if not (color.startswith('#') and (len(color) == 7 or len(color) == 4)):
        return jsonify({"success": False, "message": "Invalid color format (expecting #rrggbb or #rgb)."}), 400

    decoded_tag_name = urllib.parse.unquote(tag_name)
    success = db.set_tag_color(decoded_tag_name, color)

    if success:
        updated_colors = db.get_tag_colors()
        return jsonify({
            "success": True,
            "tag": decoded_tag_name,
            "color": color,
            "all_colors": updated_colors
        })

    return jsonify({"success": False, "message": "Failed to update tag color in database."}), 500


@app.route('/api/rating/<channel_id>', methods=['POST'])
def update_rating(channel_id):
    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({"success": False, "message": "Missing 'rating' in request data."}), 400

    try:
        rating_value = data['rating']
        if rating_value is not None:
            rating_value = int(rating_value)
            if not 1 <= rating_value <= 5:
                raise ValueError("Rating must be between 1 and 5.")
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid rating value. Must be an integer between 1 and 5, or null."}), 400

    success = db.update_channel_rating(channel_id, rating_value)

    if success:
        updated_channels = db.get_all_channels()
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "rating": rating_value,
            "channels": updated_channels
        })

    return jsonify({"success": False, "message": "Failed to update rating in database."}), 500


if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, port=5000)
