import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
import database as db
import youtube_api as yt
import os
import json
import urllib.parse # Necesario para decodificar tag names en la URL

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Required for session management (used implicitly by OAuth flow sometimes, good practice)
# In a production app, use a strong, randomly generated secret key
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-replace-in-prod')

# --- Authentication Check ---
def check_authentication():
    """Checks if the user appears to be authenticated (token exists)."""
    # Usa la existencia del archivo token definido en youtube_api.py
    return os.path.exists(yt.TOKEN_PICKLE_FILE)

# --- Routes ---

@app.route('/')
def index():
    """Main page: Displays channels and filters."""
    if not check_authentication():
        logging.info("No token file found, attempting authentication...")
        service = yt.get_authenticated_service()
        if not service:
            return "Authentication required or failed. Please ensure you have 'client_secrets.json', necessary permissions, and run the app again to authorize.", 401
        logging.info("Authentication successful, proceeding to load data.")

    # Fetch data from DB
    channels = db.get_all_channels()
    unique_tags = db.get_unique_tags()
    tag_colors = db.get_tag_colors() # Obtener colores

    # Optional: If DB is empty, trigger initial fetch from YouTube API
    if not channels:
        logging.info("Database is empty. Fetching subscriptions from YouTube API...")
        service = yt.get_authenticated_service() # Ensure we have a service object
        if service:
            yt_subscriptions = yt.get_all_subscriptions(service)
            if yt_subscriptions:
                logging.info(f"Adding {len(yt_subscriptions)} channels to the database.")
                for sub in yt_subscriptions:
                    db.add_or_update_channel(
                        sub['channel_id'],
                        sub['title'],
                        sub['thumbnail_url']
                    )
                # Re-fetch from DB after adding
                channels = db.get_all_channels()
                unique_tags = db.get_unique_tags()
                # tag_colors will be empty initially, which is fine
            else:
                 logging.warning("Fetched no subscriptions from YouTube API.")
        else:
             logging.error("Could not get authenticated YouTube service to perform initial fetch.")
             return "Error: Could not connect to YouTube API after authentication.", 500

    return render_template('index.html',
                           channels=channels,
                           unique_tags=unique_tags,
                           tag_colors=tag_colors, # Pasar colores a la plantilla
                           DEFAULT_TAG_COLOR=db.DEFAULT_TAG_COLOR) # Pasar color default


@app.route('/refresh_from_youtube', methods=['POST'])
def refresh_from_youtube():
    """Fetches latest subscriptions from YouTube and updates the database."""
    logging.info("Attempting to refresh subscriptions from YouTube API...")
    service = yt.get_authenticated_service()
    if not service:
        return jsonify({"success": False, "message": "Authentication failed or required."}), 401

    yt_subscriptions = yt.get_all_subscriptions(service)
    if yt_subscriptions is None: # Check if fetch failed
         return jsonify({"success": False, "message": "Failed to fetch subscriptions from YouTube API."}), 500

    logging.info(f"Fetched {len(yt_subscriptions)} channels from YouTube. Updating database...")
    # Add/update channels in DB (preserves existing tags)
    for sub in yt_subscriptions:
        db.add_or_update_channel(
            sub['channel_id'],
            sub['title'],
            sub['thumbnail_url']
        )
    logging.info("Database update complete after refresh.")

    # Return the updated list of channels and tags/colors for the frontend
    updated_channels = db.get_all_channels()
    updated_tags = db.get_unique_tags()
    updated_colors = db.get_tag_colors() # Obtener colores actualizados
    return jsonify({
        "success": True,
        "message": f"Refreshed {len(yt_subscriptions)} channels from YouTube.",
        "channels": updated_channels,
        "unique_tags": updated_tags,
        "tag_colors": updated_colors # Enviar colores actualizados
        })


@app.route('/api/tags/<channel_id>', methods=['POST'])
def update_tags(channel_id):
    """API endpoint to update tags for a given channel."""
    data = request.get_json()
    if not data or 'tags' not in data:
        return jsonify({"success": False, "message": "Missing 'tags' in request data."}), 400

    tags_string = data['tags']
    # Convert comma-separated string to a list of cleaned tags
    tags_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]

    success = db.update_channel_tags(channel_id, tags_list)

    if success:
        # Return updated tags list, unique tags, and tag colors
        updated_channel_data = next((c for c in db.get_all_channels() if c['channel_id'] == channel_id), None)
        current_tags = updated_channel_data.get('tags', []) if updated_channel_data else []
        unique_tags = db.get_unique_tags()
        tag_colors = db.get_tag_colors() # Obtener colores
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "tags": current_tags, # Send back the processed list
            "unique_tags": unique_tags,
            "tag_colors": tag_colors # Enviar colores
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
    # Validación simple del color (formato #rrggbb o #rgb)
    if not (color.startswith('#') and (len(color) == 7 or len(color) == 4)):
         # Podríamos permitir nombres de colores CSS aquí si quisiéramos
         return jsonify({"success": False, "message": "Invalid color format (expecting #rrggbb or #rgb)."}), 400

    # Decodificar el tag_name por si tiene caracteres especiales URL-encoded
    # Ej: si un tag es "C++", en la URL podría ser "C%2B%2B"
    decoded_tag_name = urllib.parse.unquote(tag_name)

    success = db.set_tag_color(decoded_tag_name, color)

    if success:
        # Devolver todos los colores actualizados para que JS tenga el mapa completo
        updated_colors = db.get_tag_colors()
        return jsonify({
            "success": True,
            "tag": decoded_tag_name,
            "color": color,
            "all_colors": updated_colors # Enviar el mapa actualizado
            })
    else:
        return jsonify({"success": False, "message": "Failed to update tag color in database."}), 500


if __name__ == '__main__':
    # Ensure DB is created/initialized on first run
    db.init_db()
    # Note: Setting debug=True enables auto-reload and better error pages
    # Recommended for development, disable in production.
    app.run(debug=True, port=5000) # Debug=True está bien para desarrollo local
