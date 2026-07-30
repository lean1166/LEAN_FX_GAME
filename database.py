"""
Base de datos SQLite para LEAN FX GAME
Guarda: viewers, balances, wins, losses, historial, configuración
"""
import sqlite3
import os
import sys
from datetime import datetime

# Si esta corriendo como .exe (PyInstaller), guardar la DB al lado del .exe
# (persistente), no en la carpeta temporal donde se extraen los archivos.
if getattr(sys, 'frozen', False):
    DB_DIR = os.path.dirname(sys.executable)
else:
    DB_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(DB_DIR, "lean_fx_game.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crear tablas si no existen"""
    conn = get_connection()
    c = conn.cursor()

    # Tabla de viewers/jugadores
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        balance REAL DEFAULT 10000,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        avatar_url TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Tabla de historial de trades
    c.execute('''CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER,
        trade_type TEXT,
        result TEXT,
        pnl REAL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (player_id) REFERENCES players(id)
    )''')

    # Tabla de configuración
    c.execute('''CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # Tabla de reset mensual
    c.execute('''CREATE TABLE IF NOT EXISTS resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reset_date TEXT DEFAULT CURRENT_TIMESTAMP,
        reason TEXT
    )''')

    # Insertar streamer si no existe
    c.execute('''INSERT OR IGNORE INTO players (username, balance) VALUES (?, ?)''',
              ("LEAN FX", 10000))

    # Insertar config por defecto
    defaults = {
        "timer_duration": "10000",
        "tp_multiplier": "3.0",
        "sl_buffer": "3.0",
        "trade_risk": "100",
        "bot_win_rate": "0.70",
        "bot_cooldown": "300000",
        "bot_max_ops_hour": "4",
        "last_reset": datetime.now().strftime("%Y-%m"),
    }
    for key, value in defaults.items():
        c.execute('''INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)''', (key, value))

    conn.commit()
    conn.close()


def get_player(username):
    """Obtener un jugador por nombre"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE username = ?", (username,))
    player = c.fetchone()
    conn.close()
    return player


def create_player(username):
    """Crear un nuevo jugador con balance inicial"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO players (username) VALUES (?)", (username,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Ya existe
    conn.close()


def update_player_balance(username, new_balance, win=False, loss=False):
    """Actualizar balance y stats de un jugador"""
    conn = get_connection()
    c = conn.cursor()
    if win:
        c.execute("UPDATE players SET balance = ?, wins = wins + 1, last_active = CURRENT_TIMESTAMP WHERE username = ?",
                  (new_balance, username))
    elif loss:
        c.execute("UPDATE players SET balance = ?, losses = losses + 1, last_active = CURRENT_TIMESTAMP WHERE username = ?",
                  (new_balance, username))
    else:
        c.execute("UPDATE players SET balance = ?, last_active = CURRENT_TIMESTAMP WHERE username = ?",
                  (new_balance, username))
    conn.commit()
    conn.close()


def add_trade_history(username, trade_type, result, pnl):
    """Registrar un trade en el historial"""
    conn = get_connection()
    c = conn.cursor()
    player = get_player(username)
    if player:
        c.execute("INSERT INTO trade_history (player_id, trade_type, result, pnl) VALUES (?, ?, ?, ?)",
                  (player["id"], trade_type, result, pnl))
    conn.commit()
    conn.close()


def get_top_players(limit=5):
    """Obtener los top jugadores por balance (excluyendo al streamer)"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT username, balance, wins, losses 
                 FROM players 
                 WHERE username != 'LEAN FX'
                 ORDER BY balance DESC 
                 LIMIT ?""", (limit,))
    players = c.fetchall()
    conn.close()
    return [dict(p) for p in players]


def get_streamer_stats():
    """Obtener stats del streamer"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE username = 'LEAN FX'")
    streamer = c.fetchone()
    conn.close()
    if streamer:
        return dict(streamer)
    return {"username": "LEAN FX", "balance": 10000, "wins": 0, "losses": 0}


def get_config(key, default=None):
    """Obtener un valor de configuración"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default


def set_config(key, value):
    """Guardar un valor de configuración"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def reset_all_players():
    """Reiniciar todos los balances y stats (reset mensual)"""
    import time as _time
    for attempt in range(3):
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("UPDATE players SET balance = 10000, wins = 0, losses = 0")
            c.execute("INSERT INTO resets (reason) VALUES (?)", ("Reset mensual",))
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("last_reset", datetime.now().strftime("%Y-%m")))
            conn.commit()
            conn.close()
            return
        except Exception as e:
            print(f"[DB] Reset intento {attempt+1}/3 falló: {e}")
            _time.sleep(0.5)
    print("[DB] No se pudo resetear después de 3 intentos")


def check_monthly_reset():
    """Verificar si hay que hacer reset mensual"""
    last_reset = get_config("last_reset", "")
    current_month = datetime.now().strftime("%Y-%m")
    if last_reset != current_month:
        reset_all_players()
        return True
    return False


def get_all_players_count():
    """Obtener cantidad total de jugadores"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM players WHERE username != 'LEAN FX'")
    result = c.fetchone()
    conn.close()
    return result["count"]


# Inicializar DB al importar
init_db()



def get_all_players_ranked():
    """Obtener todos los jugadores ordenados por balance (excluyendo streamer)"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT username, balance, wins, losses 
                 FROM players 
                 WHERE username != 'LEAN FX'
                 ORDER BY balance DESC""")
    players = c.fetchall()
    conn.close()
    return [dict(p) for p in players]
