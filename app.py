import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
import database as db
import youtube_api as yt
import os
import json
import urllib.parse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-replace-in-prod')

def check_authentication():
    """Checks if the user appears to be authenticated (token exists)."""
    return os.path.exists(yt.TOKEN_PICKLE_FILE)

@app.route('/')
def index():
    """Main page: Displays channels and filters."""
    user_channel_title = None # Initialize user title
    service = None # Initialize service

    if not check_authentication():
        logging.info("No token file found, attempting authentication...")
        service = yt.get_authenticated_service()
        if not service:
            return "Authentication required or failed. Please ensure you have 'client_secrets.json', necessary permissions, and run the app again to authorize.", 401
        logging.info("Authentication successful, proceeding.")
    else:
        # If token exists, try to build service anyway to get user info
        service = yt.get_authenticated_service()
        if not service:
            # If service fails even with token, force re-auth potentially
             logging.warning("Token found but failed to build service. Authentication might be needed.")
             # Optionally redirect to an error page or re-auth flow
             return "Error connecting to YouTube service. Please try deleting token.pickle and restarting.", 500

    # --- Obtener título del canal del usuario ---
    if service:
        user_channel_title = yt.get_my_channel_info(service)
    # --- Fin obtener título ---

    # Fetch data from DB
    channels = db.get_all_channels()
    unique_tags = db.get_unique_tags()
    tag_colors = db.get_tag_colors()

    # Optional: If DB is empty and we just authenticated, trigger initial fetch
    if not channels and service and user_channel_title is not None: # Check service to avoid re-auth loop
        logging.info("Database is empty. Fetching subscriptions from YouTube API...")
        yt_subscriptions = yt.get_all_subscriptions(service)
        if yt_subscriptions: # Check if fetch succeeded
            logging.info(f"Adding {len(yt_subscriptions)} channels to the database.")
            for sub in yt_subscriptions:
                db.add_or_update_channel(
                    sub['channel_id'],
                    sub['title'],
                    sub['thumbnail_url']
                )
            channels = db.get_all_channels()
            unique_tags = db.get_unique_tags()
        elif yt_subscriptions is None: # Explicit check for API failure
             logging.error("Failed to fetch subscriptions from YouTube API during initial load.")
             # Show message or handle error - avoid infinite loop if API always fails
             return "Error fetching subscriptions from YouTube. Please check API status or quotas.", 500
        else: # API returned empty list
             logging.warning("Fetched no subscriptions from YouTube API during initial load.")


    return render_template('index.html',
                           channels=channels,
                           unique_tags=unique_tags,
                           tag_colors=tag_colors,
                           DEFAULT_TAG_COLOR=db.DEFAULT_TAG_COLOR,
                           user_channel_title=user_channel_title) # Pasar título a plantilla


@app.route('/refresh_from_youtube', methods=['POST'])
def refresh_from_youtube():
    """Fetches latest subscriptions, adds new ones, updates existing, and REMOVES unsubscribed."""
    logging.info("Attempting to refresh subscriptions from YouTube API...")
    service = yt.get_authenticated_service()
    if not service:
        return jsonify({"success": False, "message": "Authentication failed or required."}), 401

    yt_subscriptions = yt.get_all_subscriptions(service)
    if yt_subscriptions is None: # Check if fetch failed
         return jsonify({"success": False, "message": "Failed to fetch subscriptions from YouTube API."}), 500

    # --- Lógica de Borrado ---
    logging.info(f"Fetched {len(yt_subscriptions)} channels from YouTube. Comparing with database...")
    api_channel_ids = {sub['channel_id'] for sub in yt_subscriptions}
    db_channel_ids = db.get_all_channel_ids()

    ids_to_delete = db_channel_ids - api_channel_ids
    if ids_to_delete:
        logging.info(f"Found {len(ids_to_delete)} channels to remove from local DB.")
        deleted_count = 0
        for channel_id in ids_to_delete:
            if db.delete_channel(channel_id):
                 deleted_count += 1
        logging.info(f"Successfully removed {deleted_count} channels.")
    else:
        logging.info("No channels found to remove from local DB.")
    # --- Fin Lógica de Borrado ---

    # --- Lógica de Añadir/Actualizar (Existente) ---
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
    # --- Fin Lógica de Añadir/Actualizar ---

    logging.info("Database update complete after refresh.")

    # Return the updated list of channels and tags/colors for the frontend
    updated_channels = db.get_all_channels()
    updated_tags = db.get_unique_tags()
    updated_colors = db.get_tag_colors()
    return jsonify({
        "success": True,
        "message": f"Refresh complete. Found {len(yt_subscriptions)} subs. Removed {len(ids_to_delete)}. Processed {added_updated_count}.",
        "channels": updated_channels,
        "unique_tags": updated_tags,
        "tag_colors": updated_colors
        })


@app.route('/api/tags/<channel_id>', methods=['POST'])
def update_tags(channel_id):
    """API endpoint to update tags for a given channel."""
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
    else:
        return jsonify({"success": False, "message": "Failed to update tags in database."}), 500


@app.route('/api/tags/color/<tag_name>', methods=['POST'])
def update_tag_color(tag_name):
    """API endpoint para actualizar el color de un tag."""
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
    else:
        return jsonify({"success": False, "message": "Failed to update tag color in database."}), 500


@app.route('/api/rating/<channel_id>', methods=['POST'])
def update_rating(channel_id):
    """API endpoint to update the rating for a given channel."""
    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({"success": False, "message": "Missing 'rating' in request data."}), 400

    try:
        # Allow None or integer rating
        rating_value = data['rating']
        if rating_value is not None:
            rating_value = int(rating_value)
            if not 1 <= rating_value <= 5:
                raise ValueError("Rating must be between 1 and 5.")
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid rating value. Must be an integer between 1 and 5, or null."}), 400

    success = db.update_channel_rating(channel_id, rating_value)

    if success:
        # Re-fetch the channels to get the updated order
        updated_channels = db.get_all_channels()
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "rating": rating_value,
            # Optionally return all channels if frontend needs to redraw the whole list
            "channels": updated_channels
        })
    else:
        return jsonify({"success": False, "message": "Failed to update rating in database."}), 500


if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, port=5000)
