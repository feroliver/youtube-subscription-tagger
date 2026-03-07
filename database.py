import sqlite3
import logging
import json
import os

DATABASE_NAME = 'subscriptions.db'
DEFAULT_TAG_COLOR = '#cccccc'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        return None


def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    thumbnail_url TEXT,
                    tags TEXT DEFAULT '[]',
                    rating INTEGER DEFAULT NULL
                )
            ''')
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS tag_colors (
                    tag TEXT PRIMARY KEY,
                    color TEXT DEFAULT '{DEFAULT_TAG_COLOR}'
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorite_video_cache (
                    video_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    channel_title TEXT NOT NULL,
                    title TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    thumbnail_url TEXT,
                    video_url TEXT NOT NULL,
                    duration_text TEXT
                )
            ''')

            # Check and add rating column if it doesn't exist (for migrations)
            try:
                cursor.execute("SELECT rating FROM channels LIMIT 1")
            except sqlite3.OperationalError:
                logging.info("Adding 'rating' column to existing 'channels' table.")
                cursor.execute("ALTER TABLE channels ADD COLUMN rating INTEGER DEFAULT NULL")

            # Migration for old favorite_video_cache without duration_text
            try:
                cursor.execute("SELECT duration_text FROM favorite_video_cache LIMIT 1")
            except sqlite3.OperationalError:
                logging.info("Adding 'duration_text' column to existing 'favorite_video_cache' table.")
                cursor.execute("ALTER TABLE favorite_video_cache ADD COLUMN duration_text TEXT")

            conn.commit()
            logging.info("Database initialized successfully.")
        except sqlite3.Error as e:
            if "syntax error" in str(e):
                logging.error(f"DATABASE SCHEMA SYNTAX ERROR: {e}")
            else:
                logging.error(f"Error initializing database table: {e}")
        finally:
            conn.close()
    else:
        logging.error("Could not get DB connection for initialization.")


def add_or_update_channel(channel_id, title, thumbnail_url):
    """Adds a new channel or updates the title/thumbnail if it already exists. Preserves existing tags and rating."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO channels (channel_id, title, thumbnail_url, tags, rating)
                VALUES (?, ?, ?, '[]', NULL)
            ''', (channel_id, title, thumbnail_url))
            cursor.execute('''
                UPDATE channels
                SET title = ?, thumbnail_url = ?
                WHERE channel_id = ?
            ''', (title, thumbnail_url, channel_id))
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error adding/updating channel {channel_id}: {e}")
        finally:
            conn.close()


def update_channel_tags(channel_id, tags_list):
    """Updates the tags for a specific channel."""
    conn = get_db_connection()
    success = False
    if conn:
        try:
            unique_sorted_tags = sorted(list(set(tag.strip() for tag in tags_list if tag.strip())))
            tags_json = json.dumps(unique_sorted_tags)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE channels
                SET tags = ?
                WHERE channel_id = ?
            ''', (tags_json, channel_id))
            conn.commit()
            logging.info(f"Updated tags for channel {channel_id}: {tags_json}")
            success = True
        except sqlite3.Error as e:
            logging.error(f"Error updating tags for channel {channel_id}: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Error encoding tags for channel {channel_id}: {e}")
        finally:
            conn.close()
    return success


def get_all_channels():
    """Retrieves all channels from the database, ordered by rating (desc, NULLs last) then title."""
    conn = get_db_connection()
    channels = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channels';")
            if cursor.fetchone():
                cursor.execute('''
                    SELECT channel_id, title, thumbnail_url, tags, rating
                    FROM channels
                    ORDER BY rating DESC NULLS LAST, title COLLATE NOCASE ASC
                ''')
                rows = cursor.fetchall()
                for row in rows:
                    channel_dict = dict(row)
                    try:
                        channel_dict['tags'] = json.loads(channel_dict.get('tags', '[]') or '[]')
                    except json.JSONDecodeError:
                        channel_dict['tags'] = []
                    channel_dict['rating'] = channel_dict.get('rating') if channel_dict.get('rating') is not None else None
                    channels.append(channel_dict)
            else:
                logging.warning("Table 'channels' does not exist yet.")

        except sqlite3.Error as e:
            logging.error(f"Error fetching all channels: {e}")
        finally:
            conn.close()
    return channels


def get_favorite_channels(min_rating=4):
    """Retrieves channels with rating >= min_rating."""
    conn = get_db_connection()
    favorites = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT channel_id, title, thumbnail_url, rating
                FROM channels
                WHERE rating >= ?
                ORDER BY rating DESC, title COLLATE NOCASE ASC
            ''', (min_rating,))
            favorites = [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error fetching favorite channels: {e}")
        finally:
            conn.close()
    return favorites


def get_unique_tags():
    """Retrieves a list of all unique tags used across all channels."""
    all_channels = get_all_channels()
    unique_tags = set()
    for channel in all_channels:
        unique_tags.update(channel.get('tags', []))
    return sorted(list(unique_tags))


def set_tag_color(tag, color):
    """Guarda o actualiza el color para un tag específico."""
    conn = get_db_connection()
    success = False
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tag_colors (tag, color)
                VALUES (?, ?)
            ''', (tag, color))
            conn.commit()
            logging.info(f"Set color for tag '{tag}' to {color}")
            success = True
        except sqlite3.Error as e:
            logging.error(f"Error setting color for tag {tag}: {e}")
        finally:
            conn.close()
    return success


def get_tag_colors():
    """Recupera un diccionario con los colores asignados a cada tag."""
    conn = get_db_connection()
    colors = {}
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tag_colors';")
            if cursor.fetchone():
                cursor.execute('SELECT tag, color FROM tag_colors')
                rows = cursor.fetchall()
                for row in rows:
                    colors[row['tag']] = row['color'] if row['color'] else DEFAULT_TAG_COLOR
            else:
                logging.warning("Table 'tag_colors' does not exist yet.")
        except sqlite3.Error as e:
            logging.error(f"Error fetching tag colors: {e}")
        finally:
            conn.close()
    return colors


def get_all_channel_ids():
    """Recupera un set con todos los channel_id de la base de datos."""
    conn = get_db_connection()
    channel_ids = set()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channels';")
            if cursor.fetchone():
                cursor.execute('SELECT channel_id FROM channels')
                rows = cursor.fetchall()
                for row in rows:
                    channel_ids.add(row['channel_id'])
            else:
                logging.warning("Table 'channels' does not exist for get_all_channel_ids.")
        except sqlite3.Error as e:
            logging.error(f"Error fetching all channel IDs: {e}")
        finally:
            conn.close()
    return channel_ids


def delete_channel(channel_id):
    """Elimina un canal específico de la base de datos."""
    conn = get_db_connection()
    success = False
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"Deleted channel with ID: {channel_id}")
                success = True
            else:
                logging.warning(f"Attempted to delete channel ID {channel_id}, but it was not found.")
                success = True
        except sqlite3.Error as e:
            logging.error(f"Error deleting channel {channel_id}: {e}")
        finally:
            conn.close()
    return success


def update_channel_rating(channel_id, rating):
    """Updates the rating for a specific channel."""
    conn = get_db_connection()
    success = False
    if conn:
        try:
            validated_rating = int(rating) if rating is not None and 1 <= int(rating) <= 5 else None

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE channels
                SET rating = ?
                WHERE channel_id = ?
            ''', (validated_rating, channel_id))
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"Updated rating for channel {channel_id} to {validated_rating}")
                success = True
            else:
                logging.warning(f"Attempted to update rating for channel {channel_id}, but it was not found.")
                success = False
        except (sqlite3.Error, ValueError) as e:
            logging.error(f"Error updating rating for channel {channel_id}: {e}")
        finally:
            conn.close()
    return success


def set_app_state(key, value):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO app_state (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (key, value))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Error setting app state for key {key}: {e}")
        return False
    finally:
        conn.close()


def get_app_state(key, default_value=None):
    conn = get_db_connection()
    if not conn:
        return default_value
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM app_state WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default_value
    except sqlite3.Error as e:
        logging.error(f"Error getting app state for key {key}: {e}")
        return default_value
    finally:
        conn.close()


def get_last_favorites_check():
    return get_app_state('favorites_last_check_at')


def set_last_favorites_check(timestamp_iso):
    return set_app_state('favorites_last_check_at', timestamp_iso)


def replace_favorite_video_cache(videos):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM favorite_video_cache')
        cursor.executemany('''
            INSERT INTO favorite_video_cache (
                video_id, channel_id, channel_title, title, published_at, thumbnail_url, video_url, duration_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (
                video.get('video_id'),
                video.get('channel_id'),
                video.get('channel_title'),
                video.get('title'),
                video.get('published_at'),
                video.get('thumbnail_url'),
                video.get('video_url'),
                video.get('duration_text')
            )
            for video in videos
        ])
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Error replacing favorite video cache: {e}")
        return False
    finally:
        conn.close()


def get_favorite_video_cache():
    conn = get_db_connection()
    videos = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT video_id, channel_id, channel_title, title, published_at, thumbnail_url, video_url, duration_text
                FROM favorite_video_cache
                ORDER BY channel_title COLLATE NOCASE ASC, published_at DESC
            ''')
            videos = [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error reading favorite video cache: {e}")
        finally:
            conn.close()
    return videos


def get_favorite_video_cache_count():
    conn = get_db_connection()
    count = 0
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(1) AS total FROM favorite_video_cache')
            row = cursor.fetchone()
            count = row['total'] if row else 0
        except sqlite3.Error as e:
            logging.error(f"Error reading favorite video cache count: {e}")
        finally:
            conn.close()
    return count


# Initialize the database when this module is imported
init_db()
