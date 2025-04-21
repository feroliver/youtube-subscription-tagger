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
                    tags TEXT DEFAULT '[]'
                )
            ''')
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS tag_colors (
                    tag TEXT PRIMARY KEY,
                    color TEXT DEFAULT '{DEFAULT_TAG_COLOR}'
                )
            ''')
            conn.commit()
            logging.info("Database initialized successfully.")
        except sqlite3.Error as e:
            # Asegurarse que el error no sea el de sintaxis anterior
            if "syntax error" in str(e):
                 logging.error(f"DATABASE SCHEMA SYNTAX ERROR: {e}")
                 # Considerar acciones más drásticas si el esquema es inválido
            else:
                 logging.error(f"Error initializing database table: {e}")

        finally:
            conn.close()
    else:
        logging.error("Could not get DB connection for initialization.")

def add_or_update_channel(channel_id, title, thumbnail_url):
    """Adds a new channel or updates the title/thumbnail if it already exists."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO channels (channel_id, title, thumbnail_url, tags)
                VALUES (?, ?, ?, '[]')
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
    """Retrieves all channels from the database."""
    conn = get_db_connection()
    channels = []
    if conn:
        try:
            cursor = conn.cursor()
            # Asegurarse que la tabla existe antes de consultar
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channels';")
            if cursor.fetchone():
                 cursor.execute('SELECT channel_id, title, thumbnail_url, tags FROM channels ORDER BY title COLLATE NOCASE ASC')
                 rows = cursor.fetchall()
                 for row in rows:
                    channel_dict = dict(row)
                    try:
                        channel_dict['tags'] = json.loads(channel_dict.get('tags', '[]') or '[]')
                    except json.JSONDecodeError:
                         channel_dict['tags'] = []
                    channels.append(channel_dict)
            else:
                 logging.warning("Table 'channels' does not exist yet.")

        except sqlite3.Error as e:
            logging.error(f"Error fetching all channels: {e}")
        finally:
            conn.close()
    return channels

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
             # Asegurarse que la tabla existe
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

# --- NUEVAS FUNCIONES ---
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
            # Verificar si se borró algo
            if cursor.rowcount > 0:
                 logging.info(f"Deleted channel with ID: {channel_id}")
                 success = True
            else:
                 logging.warning(f"Attempted to delete channel ID {channel_id}, but it was not found.")
                 success = True # Considerar True si no existía, no es un error de DB
        except sqlite3.Error as e:
            logging.error(f"Error deleting channel {channel_id}: {e}")
        finally:
            conn.close()
    return success
# --- FIN NUEVAS FUNCIONES ---

# Initialize the database when this module is imported
init_db()
