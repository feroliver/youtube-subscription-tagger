import sqlite3
import logging
import json
import os # Necesario para borrar DB si hay error grave

DATABASE_NAME = 'subscriptions.db'
DEFAULT_TAG_COLOR = '#cccccc' # Gris claro por defecto

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
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
            # Tabla de canales
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    thumbnail_url TEXT,
                    tags TEXT DEFAULT '[]' -- Store tags as a JSON array string
                )
            ''')
            # Tabla de colores para tags
            cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS tag_colors (
                tag TEXT PRIMARY KEY,
                color TEXT DEFAULT '{DEFAULT_TAG_COLOR}'
                )
            ''') # Usamos f-string para insertar el valor default directamente
            conn.commit()
            logging.info("Database initialized successfully.")
        except sqlite3.Error as e:
            logging.error(f"Error initializing database table: {e}")
            # Podríamos considerar borrar el archivo si falla la inicialización
            # if os.path.exists(DATABASE_NAME):
            #     conn.close() # Cerrar antes de borrar
            #     os.remove(DATABASE_NAME)
            #     logging.warning(f"Removed potentially corrupt DB file: {DATABASE_NAME}")
        finally:
            conn.close()
    else:
        logging.error("Could not get DB connection for initialization.")

def add_or_update_channel(channel_id, title, thumbnail_url):
    """Adds a new channel or updates the title/thumbnail if it already exists, preserving existing tags."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Use INSERT OR IGNORE for new channels, then UPDATE for existing ones
            cursor.execute('''
                INSERT OR IGNORE INTO channels (channel_id, title, thumbnail_url, tags)
                VALUES (?, ?, ?, '[]')
            ''', (channel_id, title, thumbnail_url))

            # Update title and thumbnail in case they changed, but don't overwrite tags
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
    """Updates the tags for a specific channel. Expects tags_list as a Python list."""
    conn = get_db_connection()
    success = False
    if conn:
        try:
            # Store unique tags sorted as JSON string
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
            cursor.execute('SELECT channel_id, title, thumbnail_url, tags FROM channels ORDER BY title COLLATE NOCASE ASC')
            rows = cursor.fetchall()
            for row in rows:
                channel_dict = dict(row)
                # Convert tags JSON string back to list
                try:
                    channel_dict['tags'] = json.loads(channel_dict.get('tags', '[]') or '[]')
                except json.JSONDecodeError:
                     channel_dict['tags'] = [] # Default to empty list on error
                channels.append(channel_dict)
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
            # INSERT OR REPLACE: Inserta si no existe, reemplaza si ya existe
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
            cursor.execute('SELECT tag, color FROM tag_colors')
            rows = cursor.fetchall()
            for row in rows:
                # Asegurarse que el color no sea None si la columna permite NULLs (aunque definimos default)
                colors[row['tag']] = row['color'] if row['color'] else DEFAULT_TAG_COLOR
        except sqlite3.Error as e:
            logging.error(f"Error fetching tag colors: {e}")
        finally:
            conn.close()
    return colors

# Initialize the database when this module is imported
init_db()
