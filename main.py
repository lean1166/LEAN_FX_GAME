import sys
import os
import random
import math
import pygame

from shared_paths import BASE_DIR, SOUND_DIR, PROFILE_DIR, find_asset, find_profile_image
from database import (get_top_players, get_streamer_stats,
                      update_player_balance, add_trade_history,
                      check_monthly_reset, get_config, create_player)
from tiktok_chat import TikTokChatReader

# NOTA (arquitectura multi-ventana V2): main.py ya NO dibuja el panel del
# streamer ni el TOP 5 / ranking. Esas ventanas viven en window_streamer.py
# y window_ranking.py (procesos separados, para poder capturarlas como
# fuentes independientes en OBS). main.py sigue siendo el único dueño del
# audio y de la conexión al chat de TikTok. Lanzarlos juntos con launcher.py.

try:
    pygame.init()
    pygame.mixer.init()
    # Detectar resolución de pantalla automáticamente
    display_info = pygame.display.Info()
    SCREEN_W = display_info.current_w
    SCREEN_H = display_info.current_h
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.NOFRAME)
    pygame.display.set_caption("LEAN FX GAME")
except Exception as e:
    print("[ERROR GRAFICO]:", e)
    sys.exit(1)

# Icono del juego (fuera del try principal para que no crashee)
icon_path = find_asset("icon.png", "icon.ico")
if icon_path:
    try:
        pygame.display.set_icon(pygame.image.load(icon_path))
    except:
        print("[AVISO] No se pudo cargar el icono")

# --- CARGAR SONIDOS ---
def load_sound(filename):
    path = os.path.join(SOUND_DIR, filename)
    if os.path.exists(path):
        return pygame.mixer.Sound(path)
    else:
        print(f"[AVISO] Sonido no encontrado: {path}")
        return None

sound_bos = load_sound("BOS.mp3")
sound_fractal = load_sound("FRACTAL.mp3")
sound_win = load_sound("WIN.mp3")
sound_loss = load_sound("LOSS.mp3")
sound_zoom = load_sound("ZOOM.mp3")
sound_tick = load_sound("TICK.mp3")
sound_ambient = load_sound("AMBIENT.mp3")
sound_game_music = load_sound("GAME_MUSIC.mp3")
sound_levelup = load_sound("LEVELUP.mp3")  # Sonido cuando alguien sube en TOP 5

# --- PLAYLIST DE MÚSICA (detecta automáticamente 1.mp3, 2.mp3, etc.) ---
music_playlist = []
for i in range(1, 100):
    mp = os.path.join(SOUND_DIR, f"{i}.mp3")
    if os.path.exists(mp):
        music_playlist.append(mp)
if not music_playlist and sound_game_music is not None:
    music_playlist = []  # Usa GAME_MUSIC como fallback
random.shuffle(music_playlist)
music_current_index = 0
music_playing = False

# --- CARGAR VOCES DE ZONA (Jorge de México) ---
zona_voices = []
for i in range(1, 13):
    sv = load_sound(f"ZONA_VOZ_{i}.mp3")
    if sv is not None:
        zona_voices.append(sv)
zona_voice_last = -1  # Para no repetir la misma voz 2 veces seguidas

# Voces LEAN FX opera
lean_buy_voices = []
for i in range(1, 4):
    sv = load_sound(f"LEAN_BUY_{i}.mp3")
    if sv is not None:
        lean_buy_voices.append(sv)
lean_sell_voices = []
for i in range(1, 4):
    sv = load_sound(f"LEAN_SELL_{i}.mp3")
    if sv is not None:
        lean_sell_voices.append(sv)

# Voces resultado
voz_win_voices = []
for i in range(1, 4):
    sv = load_sound(f"VOZ_WIN_{i}.mp3")
    if sv is not None:
        voz_win_voices.append(sv)
voz_loss_voices = []
for i in range(1, 4):
    sv = load_sound(f"VOZ_LOSS_{i}.mp3")
    if sv is not None:
        voz_loss_voices.append(sv)

# Estado de voz (para que el timer empiece después de que termine de hablar)
zona_voice_playing = False
zona_voice_channel = None
total_operations = 0  # Contador de operaciones totales en el stream
# Freeze por voz: congela el gráfico mientras habla (WIN/LOSS/LEAN FX)
voice_freeze_active = False
voice_freeze_start = 0
VOICE_FREEZE_DURATION = 5000  # 5 seg máximo de freeze por voz de resultado
# --- STREAK SYSTEM ---
viewer_streaks = {}  # {"username": current_streak_count}
streak_display = None  # {"name": str, "streak": int, "start_time": ms} activo en pantalla
STREAK_DISPLAY_DURATION = 4000  # 4 segundos visible
STREAK_MIN = 2  # Mínimo de wins seguidos para mostrar (2 para testing, 3 para producción)

def play_sound(sound):
    if sound is not None and game_started:
        sound.play()

game_started = False  # Se activa al presionar INICIAR

def trade_win(amount):
    """Llamar cuando se gana un trade. Suma al balance"""
    global fxp_balance, wins
    fxp_balance += amount
    wins += 1
    update_player_balance("LEAN FX", fxp_balance, win=True)
    add_trade_history("LEAN FX", "BUY", "WIN", amount)

def trade_loss(amount):
    """Llamar cuando se pierde un trade. Resta del balance"""
    global fxp_balance, losses
    fxp_balance -= amount
    losses += 1
    update_player_balance("LEAN FX", fxp_balance, loss=True)
    add_trade_history("LEAN FX", "SELL", "LOSS", -amount)

pygame.font.init()
font_price = pygame.font.SysFont("Arial", 16, bold=True)
font_hud_title = pygame.font.SysFont("Arial", 18, bold=True)
font_hud_val = pygame.font.SysFont("Arial", 22, bold=True)
font_bos = pygame.font.SysFont("Arial", 16, bold=True)
font_ob = pygame.font.SysFont("Consolas", 13, bold=True)

# --- CARGAR AVATAR DEL STREAMER ---
# Nota: window_streamer.py carga esta misma imagen por su cuenta (es un
# proceso separado); main.py ya no dibuja el panel del streamer, pero
# mantenemos avatar_img aquí por si en el futuro se necesita en el gráfico.
avatar_img = None
_profile_path = find_profile_image()
if _profile_path:
    avatar_img = pygame.image.load(_profile_path).convert_alpha()
    avatar_img = pygame.transform.smoothscale(avatar_img, (200, 200))
else:
    print(f"[AVISO] Avatar no encontrado en: {PROFILE_DIR}")

# get_viewer_avatar() ahora viene de avatar_utils.py (compartido con window_ranking.py)

# --- TOP 5 VIEWERS (desde base de datos) ---
font_top = pygame.font.SysFont("Arial", 14, bold=True)
# Verificar reset mensual
check_monthly_reset()
# Crear jugadores de prueba si la DB está vacía
db_top = get_top_players(10)
# Solo crear jugadores si la DB está vacía
# Solo viewers reales - no crear jugadores de prueba
db_top = get_top_players(10)

# Cargar top viewers desde DB
def load_top_viewers():
    players = get_top_players(5)
    viewers = []
    for p in players:
        total = p["wins"] + p["losses"]
        viewers.append({
            "name": p["username"],
            "balance": p["balance"],
            "wins": p["wins"],
            "losses": p["losses"],
        })
    return viewers

top_viewers = load_top_viewers()
# --- SONIDO LEVELUP cuando alguien sube en el TOP 5 ---
# (El dibujo visual del TOP 5 y sus flechitas +/- ahora vive en window_ranking.py,
# ese proceso no tiene audio propio, así que main.py sigue chequeando el orden
# solo para decidir cuándo reproducir el sonido)
top5_prev_order = [v["name"] for v in top_viewers]
top5_last_refresh = 0
TOP5_REFRESH_INTERVAL = 3000  # Chequear cada 3 segundos

def check_top5_levelup_sound(current_time):
    """Refresca top_viewers y reproduce LEVELUP.mp3 si alguien subió de posición"""
    global top_viewers, top5_prev_order
    new_viewers = load_top_viewers()
    new_order = [v["name"] for v in new_viewers]
    someone_moved_up = False
    for name in new_order:
        if name in top5_prev_order:
            if new_order.index(name) < top5_prev_order.index(name):
                someone_moved_up = True
        else:
            someone_moved_up = True
    if someone_moved_up and sound_levelup is not None and game_started:
        sound_levelup.play()
    top5_prev_order = new_order
    top_viewers = new_viewers
    top5_prev_order = new_order
    top_viewers = new_viewers
# Cargar stats del streamer desde DB
streamer_data = get_streamer_stats()
fxp_balance = streamer_data["balance"]
wins = streamer_data["wins"]
losses = streamer_data["losses"]
STREAMER_NAME = "LEAN FX"
candles = []
price = 1000
trend_dir = random.choice([-1, 1])
# Generador de mercado realista: impulsos + retrocesos variados
is_impulse = True  # Empieza con impulso
trend_length = random.randint(6, 10)
trend_count = 0
trend_strength = random.uniform(4, 10)  # Fuerza del movimiento
for _ in range(180):
    trend_count += 1
    if trend_count >= trend_length:
        trend_dir *= -1
        trend_count = 0
        is_impulse = not is_impulse
        if is_impulse:
            # Impulso: 6-10 velas
            trend_length = random.randint(6, 10)
            trend_strength = random.uniform(4, 12)
        else:
            # Retroceso: variado
            if random.random() < 0.4:
                trend_length = random.randint(3, 6)
                trend_strength = random.uniform(6, 11)
            else:
                trend_length = random.randint(5, 9)
                trend_strength = random.uniform(2, 6)
    # Generar vela
    if random.random() < 0.80:
        body = random.uniform(trend_strength * 0.3, trend_strength) * trend_dir
    else:
        # Vela contra-tendencia (ruido)
        body = random.uniform(1, trend_strength * 0.5) * -trend_dir
    open_p = price
    close_p = open_p + body
    high_p = max(open_p, close_p) + random.uniform(0.5, 3)
    low_p = min(open_p, close_p) - random.uniform(0.5, 3)
    candles.append({"open": open_p, "close": close_p, "high": high_p, "low": low_p})
    price = close_p
current_candle = {"open": candles[-1]["close"], "close": candles[-1]["close"], "high": candles[-1]["close"], "low": candles[-1]["close"]}
buttons_active = False
zone_time_left = 0.0
active_trade = None
TRADE_RISK = 100  # Siempre pierdes 100 FXP, sin importar el tamaño del SL
TP_MULTIPLIER = 3.0  # Risk:Reward 1:3
SL_BUFFER = 1.0  # SL 1 pip debajo/encima de la zona
TIMER_DURATION = 10000  # 10 segundos en ms (temporal para pruebas)
trade_history = []
font_btn = pygame.font.SysFont("Arial", 20, bold=True)
font_trade = pygame.font.SysFont("Arial", 14, bold=True)
font_timer = pygame.font.SysFont("Arial", 48, bold=True)
# Estado del timer y zona
zone_frozen = False  # True cuando el gráfico está congelado
zone_timer_start = 0  # Momento en que se activó el timer
zone_detected = None  # Info de la zona detectada {"high", "low", "type"}
trade_decided = False  # Si ya eligió BUY o SELL durante el timer
zones_mitigated = set()  # Zonas ya mitigadas (no se repiten)
zones_mitigated_info = {}  # {"zone_id": {"index": candle_index, "bos_count": 0}} info de mitigación
# Flash al ganar/perder
flash_active = False
flash_start_time = 0
flash_color = (0, 0, 0)
flash_text = ""
FLASH_DURATION = 2000  # 2 segundos
# Tick-tock
last_tick_second = -1  # Para no repetir el tick en el mismo segundo
# Bot inteligente del streamer
BOT_ENABLED = True
BOT_WIN_RATE = 0.70  # 70% de probabilidad de ganar
BOT_COOLDOWN = 300000  # 5 minutos en ms
BOT_MAX_OPS_HOUR = 4
bot_last_trade_time = 0
bot_ops_this_hour = 0
bot_hour_start = 0
bot_bias_active = False  # True cuando el precio tiene sesgo a favor del bot
bot_bias_direction = 0  # 1 = arriba, -1 = abajo
# --- BOTS SIMULADOS (viewers falsos que operan para testear el ranking) ---
VIEWER_BOTS_ENABLED = False  # Desactivado: solo viewers reales de TikTok
VIEWER_BOT_INTERVAL = 8000  # (ya no se usa, operan en zona)
viewer_bot_last_time = 0

# --- CONEXIÓN TIKTOK LIVE ---
tiktok_chat = TikTokChatReader(username="lean.fx1")
tiktok_chat.start()  # Inicia en hilo separado
TIKTOK_USERNAME = "lean.fx1"
# --- SISTEMA DE VOTOS DE VIEWERS ---
viewer_votes = []  # Lista de {"name": str, "vote": "BUY"/"SELL"} votos pendientes
viewer_votes_display = []  # Copia para mostrar incluso después de resolver
viewer_trade_active = None  # Trade activo de viewers: {"type", "entry", "sl", "tp", "entry_index"}
viewer_trade_is_extremo = False  # Si la zona actual es EXTREMO (streamer también opera)
running = True
clock = pygame.time.Clock()
CANDLE_DURATION = 1000
last_candle_time = pygame.time.get_ticks()
TICK_DELAY = 60
last_tick_time = pygame.time.get_ticks()
bos_markers = []
initial_candle_count = len(candles)
range_phase = "buscando_high"
range_high = None
range_high_index = None
range_low = None
range_low_index = None
pullback_count = 0
prev_pullback_close = None
last_direction = None
prev_range_low = None
prev_range_low_index = None
prev_range_high = None
prev_range_high_index = None
confirmed_fractals = []
active_ob = None
prev_ob = None
active_decisional = None
active_fvg = None
current_visible_count = 100.0
target_visible_count = 100.0

def find_decisional(candles_list, bos_index, bos_type, extreme_index):
    """
    El decisional es la vela que hizo el punto mas alto/bajo del ultimo retroceso
    antes de romper el BOS.
    Para BOS BAJISTA: busca el ultimo retroceso alcista (2 velas verdes, 2da cierra mas alto).
    El decisional es la vela con el high mas alto de ese retroceso (la 2da vela).
    Para BOS ALCISTA: busca el ultimo retroceso bajista (2 velas rojas, 2da cierra mas bajo).
    El decisional es la vela con el low mas bajo de ese retroceso (la 2da vela).
    """
    if extreme_index is None or bos_index is None:
        return None
    start = extreme_index + 1
    end = bos_index
    if end - start < 2:
        return None
    if bos_type == "ALCISTA":
        # Retroceso bajista: 2 velas rojas donde la 2da cierra mas bajo
        # El decisional es la 2da vela (la que hizo el low mas bajo)
        for i in range(end - 1, start, -1):
            c = candles_list[i]
            prev_c = candles_list[i - 1]
            if (c["close"] < c["open"] and prev_c["close"] < prev_c["open"]
                    and c["close"] < prev_c["close"]):
                return {"high": c["high"], "low": c["low"], "index": i}
    elif bos_type == "BAJISTA":
        # Retroceso alcista: 2 velas verdes donde la 2da cierra mas alto
        # El decisional es la 2da vela (la que hizo el high mas alto)
        for i in range(end - 1, start, -1):
            c = candles_list[i]
            prev_c = candles_list[i - 1]
            if (c["close"] > c["open"] and prev_c["close"] > prev_c["open"]
                    and c["close"] > prev_c["close"]):
                return {"high": c["high"], "low": c["low"], "index": i}
    return None

def zonas_se_solapan(zona_a, zona_b):
    """Devuelve True si los rangos de precio [low, high] de dos zonas se solapan/tocan."""
    if zona_a is None or zona_b is None:
        return False
    return zona_a["low"] <= zona_b["high"] and zona_b["low"] <= zona_a["high"]

def find_fvg(candles_list, start_idx, end_idx, bos_type):
    if end_idx - start_idx < 3:
        return None
    for i in range(start_idx, end_idx - 2):
        v1 = candles_list[i]
        v3 = candles_list[i + 2]
        if bos_type == "ALCISTA":
            if v3["low"] > v1["high"]:
                return {"high": v3["low"], "low": v1["high"], "index": i + 1}
        else:
            if v1["low"] > v3["high"]:
                return {"high": v1["low"], "low": v3["high"], "index": i + 1}
    return None

def process_new_candle(candles_list, new_index):
    global range_phase, range_high, range_high_index, range_low, range_low_index
    global pullback_count, prev_pullback_close, last_direction
    global prev_range_low, prev_range_low_index, prev_range_high, prev_range_high_index
    global active_ob, prev_ob, active_decisional, active_fvg
    if new_index < 1:
        return
    c = candles_list[new_index]
    is_bull = c["close"] > c["open"]
    is_bear = c["close"] < c["open"]
    # Mitigar FVG si el precio entra en la zona
    if active_fvg is not None:
        if "type" in active_fvg:
            if active_fvg["type"] == "ALCISTA" and c["close"] < active_fvg["high"]:
                active_fvg = None
            elif active_fvg["type"] == "BAJISTA" and c["close"] > active_fvg["low"]:
                active_fvg = None
        else:
            # Si no tiene type, verificar por posicion
            if c["close"] < active_fvg["high"] and c["close"] > active_fvg["low"]:
                active_fvg = None
    if prev_range_low is not None and is_bear and c["close"] < prev_range_low:
        bos_markers.append({"type": "BAJISTA", "price": prev_range_low, "level_index": prev_range_low_index, "break_index": new_index})
        play_sound(sound_bos)
        # Incrementar bos_count de zonas mitigadas
        for k in zones_mitigated_info:
            zones_mitigated_info[k]["bos_count"] = zones_mitigated_info[k].get("bos_count", 0) + 1
        if range_high is not None:
            confirmed_fractals.append({"price": range_high, "index": range_high_index, "type": "high"})
            play_sound(sound_fractal)
        if range_high_index is not None:
            ob_candle = candles_list[range_high_index]
            prev_ob = active_ob
            if prev_ob is not None:
                prev_ob["end_index"] = new_index
            active_ob = {"type": "BAJISTA", "high": ob_candle["high"], "low": ob_candle["low"], "index": range_high_index}
        dec = find_decisional(candles_list, new_index, "BAJISTA", range_high_index)
        if dec is not None:
            dec["type"] = "BAJISTA"
            if active_ob and (dec["index"] == active_ob["index"] or zonas_se_solapan(dec, active_ob)):
                dec = None
        active_decisional = dec
        active_fvg = find_fvg(candles_list, range_high_index, new_index, "BAJISTA")
        if active_fvg is not None:
            active_fvg["type"] = "BAJISTA"
        prev_range_high = range_high
        prev_range_high_index = range_high_index
        prev_range_low = None
        prev_range_low_index = None
        range_low = c["low"]
        range_low_index = new_index
        range_high = None
        range_high_index = None
        range_phase = "buscando_low"
        pullback_count = 0
        prev_pullback_close = None
        last_direction = None
        return
    if prev_range_high is not None and is_bull and c["close"] > prev_range_high:
        bos_markers.append({"type": "ALCISTA", "price": prev_range_high, "level_index": prev_range_high_index, "break_index": new_index})
        play_sound(sound_bos)
        for k in zones_mitigated_info:
            zones_mitigated_info[k]["bos_count"] = zones_mitigated_info[k].get("bos_count", 0) + 1
        if range_low is not None:
            confirmed_fractals.append({"price": range_low, "index": range_low_index, "type": "low"})
            play_sound(sound_fractal)
        if range_low_index is not None:
            ob_candle = candles_list[range_low_index]
            prev_ob = active_ob
            if prev_ob is not None:
                prev_ob["end_index"] = new_index
            active_ob = {"type": "ALCISTA", "high": ob_candle["high"], "low": ob_candle["low"], "index": range_low_index}
        dec = find_decisional(candles_list, new_index, "ALCISTA", range_low_index)
        if dec is not None:
            dec["type"] = "ALCISTA"
            if active_ob and (dec["index"] == active_ob["index"] or zonas_se_solapan(dec, active_ob)):
                dec = None
        active_decisional = dec
        active_fvg = find_fvg(candles_list, range_low_index, new_index, "ALCISTA")
        if active_fvg is not None:
            active_fvg["type"] = "ALCISTA"
        prev_range_low = range_low
        prev_range_low_index = range_low_index
        prev_range_high = None
        prev_range_high_index = None
        range_high = c["high"]
        range_high_index = new_index
        range_low = None
        range_low_index = None
        range_phase = "buscando_high"
        pullback_count = 0
        prev_pullback_close = None
        last_direction = None
        return
    if range_phase == "buscando_high":
        if range_high is None or c["high"] >= range_high:
            range_high = c["high"]
            range_high_index = new_index
            pullback_count = 0
            prev_pullback_close = None
        if range_high is not None and is_bear and new_index > range_high_index:
            if pullback_count == 0:
                pullback_count = 1
                prev_pullback_close = c["close"]
            elif prev_pullback_close is not None and c["close"] < prev_pullback_close:
                pullback_count = 2
                range_low = c["low"]
                range_low_index = new_index
                range_phase = "rango_definido"
                last_direction = "up"
                pullback_count = 0
                prev_pullback_close = None
                confirmed_fractals.append({"price": range_high, "index": range_high_index, "type": "high"})
                play_sound(sound_fractal)
            else:
                pullback_count = 1
                prev_pullback_close = c["close"]
        elif is_bull and range_high is not None and new_index > range_high_index:
            pullback_count = 0
            prev_pullback_close = None
    elif range_phase == "buscando_low":
        if range_low is None or c["low"] <= range_low:
            range_low = c["low"]
            range_low_index = new_index
            pullback_count = 0
            prev_pullback_close = None
        if range_low is not None and is_bull and new_index > range_low_index:
            if pullback_count == 0:
                pullback_count = 1
                prev_pullback_close = c["close"]
            elif prev_pullback_close is not None and c["close"] > prev_pullback_close:
                pullback_count = 2
                range_high = c["high"]
                range_high_index = new_index
                range_phase = "rango_definido"
                last_direction = "down"
                pullback_count = 0
                prev_pullback_close = None
                confirmed_fractals.append({"price": range_low, "index": range_low_index, "type": "low"})
                play_sound(sound_fractal)
            else:
                pullback_count = 1
                prev_pullback_close = c["close"]
        elif is_bear and range_low is not None and new_index > range_low_index:
            pullback_count = 0
            prev_pullback_close = None
    elif range_phase == "rango_definido":
        if last_direction == "up":
            if c["low"] < range_low:
                range_low = c["low"]
                range_low_index = new_index
        elif last_direction == "down":
            if c["high"] > range_high:
                range_high = c["high"]
                range_high_index = new_index
        if is_bull and c["close"] > range_high:
            bos_markers.append({"type": "ALCISTA", "price": range_high, "level_index": range_high_index, "break_index": new_index})
            play_sound(sound_bos)
            confirmed_fractals.append({"price": range_low, "index": range_low_index, "type": "low"})
            play_sound(sound_fractal)
            if range_low_index is not None:
                ob_candle = candles_list[range_low_index]
                prev_ob = active_ob
                if prev_ob is not None:
                    prev_ob["end_index"] = new_index
                active_ob = {"type": "ALCISTA", "high": ob_candle["high"], "low": ob_candle["low"], "index": range_low_index}
            dec = find_decisional(candles_list, new_index, "ALCISTA", range_low_index)
            if dec is not None:
                dec["type"] = "ALCISTA"
                if active_ob and (dec["index"] == active_ob["index"] or zonas_se_solapan(dec, active_ob)):
                    dec = None
            active_decisional = dec
            active_fvg = find_fvg(candles_list, range_low_index, new_index, "ALCISTA")
            if active_fvg is not None:
                active_fvg["type"] = "ALCISTA"
            prev_range_low = range_low
            prev_range_low_index = range_low_index
            range_high = c["high"]
            range_high_index = new_index
            range_low = None
            range_low_index = None
            range_phase = "buscando_high"
            pullback_count = 0
            prev_pullback_close = None
            last_direction = None
        elif is_bear and c["close"] < range_low:
            bos_markers.append({"type": "BAJISTA", "price": range_low, "level_index": range_low_index, "break_index": new_index})
            play_sound(sound_bos)
            confirmed_fractals.append({"price": range_high, "index": range_high_index, "type": "high"})
            play_sound(sound_fractal)
            if range_high_index is not None:
                ob_candle = candles_list[range_high_index]
                prev_ob = active_ob
                if prev_ob is not None:
                    prev_ob["end_index"] = new_index
                active_ob = {"type": "BAJISTA", "high": ob_candle["high"], "low": ob_candle["low"], "index": range_high_index}
            dec = find_decisional(candles_list, new_index, "BAJISTA", range_high_index)
            if dec is not None:
                dec["type"] = "BAJISTA"
                if active_ob and (dec["index"] == active_ob["index"] or zonas_se_solapan(dec, active_ob)):
                    dec = None
            active_decisional = dec
            active_fvg = find_fvg(candles_list, range_high_index, new_index, "BAJISTA")
            if active_fvg is not None:
                active_fvg["type"] = "BAJISTA"
            prev_range_high = range_high
            prev_range_high_index = range_high_index
            range_low = c["low"]
            range_low_index = new_index
            range_high = None
            range_high_index = None
            range_phase = "buscando_low"
            pullback_count = 0
            prev_pullback_close = None
            last_direction = None
last_checked_index = initial_candle_count
for i in range(1, len(candles)):
    process_new_candle(candles, i)

while len(bos_markers) < 2:
    bos_markers.clear()
    confirmed_fractals.clear()
    active_ob = None
    prev_ob = None
    active_decisional = None
    active_fvg = None
    range_phase = "buscando_high"
    range_high = None
    range_high_index = None
    range_low = None
    range_low_index = None
    prev_range_low = None
    prev_range_low_index = None
    prev_range_high = None
    prev_range_high_index = None
    pullback_count = 0
    prev_pullback_close = None
    last_direction = None
    candles.clear()
    price = 1000
    trend_dir = random.choice([-1, 1])
    is_impulse = True
    trend_length = random.randint(8, 15)
    trend_count = 0
    trend_strength = random.uniform(4, 10)
    for _ in range(180):
        trend_count += 1
        if trend_count >= trend_length:
            trend_dir *= -1
            trend_count = 0
            is_impulse = not is_impulse
            if is_impulse:
                trend_length = random.randint(8, 15)
                trend_strength = random.uniform(4, 12)
            else:
                if random.random() < 0.4:
                    trend_length = random.randint(4, 8)
                    trend_strength = random.uniform(6, 11)
                else:
                    trend_length = random.randint(8, 14)
                    trend_strength = random.uniform(2, 6)
        if random.random() < 0.80:
            body = random.uniform(trend_strength * 0.3, trend_strength) * trend_dir
        else:
            body = random.uniform(1, trend_strength * 0.5) * -trend_dir
        open_p = price
        close_p = open_p + body
        high_p = max(open_p, close_p) + random.uniform(0.5, 3)
        low_p = min(open_p, close_p) - random.uniform(0.5, 3)
        candles.append({"open": open_p, "close": close_p, "high": high_p, "low": low_p})
        price = close_p
    for i in range(1, len(candles)):
        process_new_candle(candles, i)

current_candle = {"open": candles[-1]["close"], "close": candles[-1]["close"], "high": candles[-1]["close"], "low": candles[-1]["close"]}

# === MENÚ DE INICIO ===
font_menu_title = pygame.font.SysFont("Arial", 60, bold=True)
font_menu_btn = pygame.font.SysFont("Arial", 28, bold=True)
in_menu = True
menu_selection = None

# Cargar imagen de fondo del menú
menu_bg_path = os.path.join(BASE_DIR, "assets", "menu_bg.png")
if not os.path.exists(menu_bg_path):
    menu_bg_path = os.path.join(BASE_DIR, "assets", "menu_bg.jpg")
menu_bg = None
if os.path.exists(menu_bg_path):
    menu_bg = pygame.image.load(menu_bg_path).convert()
    menu_bg = pygame.transform.smoothscale(menu_bg, (SCREEN_W, SCREEN_H))
else:
    print("[AVISO] menu_bg no encontrado")

# Efecto click
menu_click_btn = None  # Nombre del botón clickeado
menu_click_time = 0
MENU_CLICK_DURATION = 150  # ms


# === LOOP PRINCIPAL ===
app_running = True
while app_running:
    # Reset variables para volver al menú
    in_menu = True
    menu_click_btn = None
    menu_selection = None
    game_started = False

    # Animaciones del menú
    import math
    # Partículas flotantes
    menu_particles = []
    for _ in range(30):
        menu_particles.append({
            "x": random.randint(0, SCREEN_W),
            "y": random.randint(0, SCREEN_H),
            "speed": random.uniform(0.3, 1.2),
            "size": random.randint(1, 3),
            "color": random.choice([(0, 220, 255), (255, 200, 0), (0, 180, 200), (200, 170, 0)]),
            "alpha": random.randint(80, 200),
        })
    # Velas japonesas de fondo
    menu_candles = []
    for i in range(15):
        h = random.randint(30, 120)
        menu_candles.append({
            "x": random.randint(0, SCREEN_W),
            "y": random.randint(int(SCREEN_H * 0.2), int(SCREEN_H * 0.8)),
            "w": random.randint(8, 14),
            "h": h,
            "color": random.choice([(38, 166, 154), (239, 83, 80)]),
            "speed": random.uniform(0.2, 0.6),
        })
    # Línea de precio animada (tipo chart)
    menu_price_points = []
    price_val = SCREEN_H * 0.5
    for i in range(int(SCREEN_W * 0.8)):
        price_val += random.uniform(-2, 2)
        price_val = max(SCREEN_H * 0.3, min(SCREEN_H * 0.7, price_val))
        menu_price_points.append(price_val)
    menu_price_offset = 0
    # Definir áreas de botones (para glow y clicks)
    btn_w = int(SCREEN_W * 0.28)
    btn_h = int(SCREEN_H * 0.08)
    btn_iniciar = pygame.Rect(int(SCREEN_W * (681/1366)) - btn_w // 2, int(SCREEN_H * (341/768)) - btn_h // 2, btn_w, btn_h)
    btn_config = pygame.Rect(int(SCREEN_W * (681/1366)) - btn_w // 2, int(SCREEN_H * (607/768)) - btn_h // 2, btn_w, btn_h)

    # --- MENÚ ---
    # Reproducir música ambient en loop
    if sound_ambient is not None:
        sound_ambient.play(loops=-1)
    while in_menu and app_running:
        clock.tick(60)
        current_time = pygame.time.get_ticks()
        # Fondo
        if menu_bg is not None:
            screen.blit(menu_bg, (0, 0))
        else:
            screen.fill((15, 15, 25))
        # --- ANIMACIONES DEL MENÚ ---
        # Velas japonesas de fondo (opacidad baja)
        candle_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for c in menu_candles:
            c["x"] -= c["speed"]
            if c["x"] < -20:
                c["x"] = SCREEN_W + 20
                c["y"] = random.randint(int(SCREEN_H * 0.2), int(SCREEN_H * 0.8))
            col = (c["color"][0], c["color"][1], c["color"][2], 35)
            pygame.draw.rect(candle_surface, col, (int(c["x"]), int(c["y"]), c["w"], c["h"]))
            # Mecha
            wick_col = (c["color"][0], c["color"][1], c["color"][2], 25)
            pygame.draw.line(candle_surface, wick_col, (int(c["x"]) + c["w"] // 2, int(c["y"]) - 15), (int(c["x"]) + c["w"] // 2, int(c["y"])), 1)
            pygame.draw.line(candle_surface, wick_col, (int(c["x"]) + c["w"] // 2, int(c["y"]) + c["h"]), (int(c["x"]) + c["w"] // 2, int(c["y"]) + c["h"] + 15), 1)
        screen.blit(candle_surface, (0, 0))
        # Partículas flotantes
        for p in menu_particles:
            p["y"] -= p["speed"]
            if p["y"] < -5:
                p["y"] = SCREEN_H + 5
                p["x"] = random.randint(0, SCREEN_W)
            ps = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (p["color"][0], p["color"][1], p["color"][2], p["alpha"]), (p["size"], p["size"]), p["size"])
            screen.blit(ps, (int(p["x"]), int(p["y"])))
        # Línea de precio animada (se mueve de derecha a izquierda)
        menu_price_offset += 1
        if menu_price_offset >= len(menu_price_points):
            menu_price_offset = 0
            # Generar nuevos puntos
            price_val = SCREEN_H * 0.5
            for i in range(len(menu_price_points)):
                price_val += random.uniform(-2, 2)
                price_val = max(SCREEN_H * 0.3, min(SCREEN_H * 0.7, price_val))
                menu_price_points[i] = price_val
        price_line_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        visible_points = menu_price_points[menu_price_offset:] + menu_price_points[:menu_price_offset]
        step = max(1, len(visible_points) // SCREEN_W)
        for i in range(1, SCREEN_W - 1):
            idx1 = min((i - 1) * step, len(visible_points) - 1)
            idx2 = min(i * step, len(visible_points) - 1)
            y1 = int(visible_points[idx1])
            y2 = int(visible_points[idx2])
            pygame.draw.line(price_line_surface, (0, 200, 220, 40), (i - 1, y1), (i, y2), 2)
        screen.blit(price_line_surface, (0, 0))
        # Niebla sutil (nubes transparentes que se mueven)
        fog_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        fog_time = current_time / 3000.0
        for fi in range(3):
            fog_x = int((fog_time * 20 + fi * 400) % (SCREEN_W + 300)) - 150
            fog_y = int(SCREEN_H * (0.7 + fi * 0.08))
            fog_w = 300 + fi * 50
            fog_h = 40
            for fy in range(fog_h):
                fog_alpha = int(12 * (1 - abs(fy - fog_h // 2) / (fog_h // 2)))
                pygame.draw.line(fog_surface, (100, 150, 180, fog_alpha), (fog_x, fog_y + fy), (fog_x + fog_w, fog_y + fy))
        screen.blit(fog_surface, (0, 0))
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                # Diálogo ¿Cerrar juego?
                confirming = True
                pygame.event.clear()
                pygame.time.wait(100)
                while confirming:
                    confirm_overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    confirm_overlay.fill((0, 0, 0, 150))
                    screen.blit(confirm_overlay, (0, 0))
                    confirm_txt = font_timer.render("¿CERRAR EL JUEGO?", True, (255, 255, 255))
                    screen.blit(confirm_txt, confirm_txt.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.35))))
                    btn_si = pygame.Rect(SCREEN_W // 2 - 150, int(SCREEN_H * 0.50), 120, 50)
                    btn_no = pygame.Rect(SCREEN_W // 2 + 30, int(SCREEN_H * 0.50), 120, 50)
                    pygame.draw.rect(screen, (239, 83, 80), btn_si, border_radius=8)
                    pygame.draw.rect(screen, (38, 166, 154), btn_no, border_radius=8)
                    si_txt = font_btn.render("SI", True, (255, 255, 255))
                    no_txt = font_btn.render("NO", True, (255, 255, 255))
                    screen.blit(si_txt, si_txt.get_rect(center=btn_si.center))
                    screen.blit(no_txt, no_txt.get_rect(center=btn_no.center))
                    pygame.display.flip()
                    for c_event in pygame.event.get():
                        if c_event.type == pygame.QUIT:
                            confirming = False
                            app_running = False
                            in_menu = False
                        elif c_event.type == pygame.KEYDOWN:
                            if c_event.key == pygame.K_ESCAPE:
                                confirming = False
                        elif c_event.type == pygame.MOUSEBUTTONDOWN and c_event.button == 1:
                            cmx, cmy = c_event.pos
                            if btn_si.collidepoint(cmx, cmy):
                                confirming = False
                                app_running = False
                                in_menu = False
                            elif btn_no.collidepoint(cmx, cmy):
                                confirming = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                print(f"[MENU CLICK] x={mx}, y={my}")
                if btn_iniciar.collidepoint(mx, my):
                    menu_click_btn = "iniciar"
                    menu_click_time = current_time
                elif btn_config.collidepoint(mx, my):
                    menu_click_btn = "config"
                    menu_click_time = current_time
        # Verificar si el efecto click terminó
        if menu_click_btn and current_time - menu_click_time > MENU_CLICK_DURATION:
            if menu_click_btn == "iniciar":
                in_menu = False
                game_started = True
                if sound_ambient is not None:
                    sound_ambient.stop()
                # Iniciar playlist de música
                if music_playlist:
                    random.shuffle(music_playlist)
                    music_current_index = 0
                    pygame.mixer.music.load(music_playlist[music_current_index])
                    vol = int(get_config("vol_music", "30")) / 100.0
                    pygame.mixer.music.set_volume(vol)
                    pygame.mixer.music.play()
                    music_playing = True
                elif sound_game_music is not None:
                    sound_game_music.set_volume(0.3)
                    sound_game_music.play(loops=-1)
            elif menu_click_btn == "config":
                # === PANTALLA DE CONFIGURACIÓN ===
                in_config = True
                # Cargar valores actuales
                cfg_timer = int(get_config("timer_duration", "10000")) // 1000  # en segundos
                cfg_risk = int(get_config("trade_risk", "100"))
                cfg_tp_mult = float(get_config("tp_multiplier", "3.0"))
                cfg_bot_enabled = get_config("bot_enabled", "1") == "1"
                cfg_bot_wr = int(float(get_config("bot_win_rate", "0.70")) * 100)
                cfg_viewers_enabled = get_config("viewers_enabled", "1") == "1"
                cfg_vol_music = int(get_config("vol_music", "30"))
                cfg_vol_fx = int(get_config("vol_fx", "100"))
                # Opciones de config
                config_options = [
                    {"label": "Timer (segundos)", "key": "timer", "type": "number", "min": 3, "max": 30, "step": 1},
                    {"label": "Riesgo por trade (FXP)", "key": "risk", "type": "number", "min": 50, "max": 500, "step": 50},
                    {"label": "Ratio TP:SL", "key": "tp_mult", "type": "number", "min": 1.0, "max": 5.0, "step": 0.5},
                    {"label": "Bot LEAN FX", "key": "bot_enabled", "type": "toggle"},
                    {"label": "Bot Win Rate %", "key": "bot_wr", "type": "number", "min": 50, "max": 90, "step": 5},
                    {"label": "Bots Viewers", "key": "viewers_enabled", "type": "toggle"},
                    {"label": "Volumen Musica %", "key": "vol_music", "type": "number", "min": 0, "max": 100, "step": 10},
                    {"label": "Volumen Efectos %", "key": "vol_fx", "type": "number", "min": 0, "max": 100, "step": 10},
                    {"label": "RESET RANKING", "key": "reset", "type": "button"},
                ]
                config_selected = 0  # Índice de opción seleccionada
                config_confirm_reset = False
                while in_config:
                    clock.tick(60)
                    current_time = pygame.time.get_ticks()
                    screen.fill((8, 12, 20))
                    # Título
                    font_cfg_title = pygame.font.SysFont("Arial", int(SCREEN_H * 0.05), bold=True)
                    cfg_title = font_cfg_title.render("CONFIGURACION", True, (0, 220, 255))
                    screen.blit(cfg_title, cfg_title.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.06))))
                    # Dibujar opciones
                    font_cfg_label = pygame.font.SysFont("Arial", int(SCREEN_H * 0.022), bold=True)
                    font_cfg_val = pygame.font.SysFont("Arial", int(SCREEN_H * 0.024), bold=True)
                    opt_start_y = int(SCREEN_H * 0.15)
                    opt_h = int(SCREEN_H * 0.07)
                    for idx, opt in enumerate(config_options):
                        oy = opt_start_y + (idx * opt_h)
                        # Fondo de fila (highlight si seleccionada)
                        row_bg = pygame.Surface((int(SCREEN_W * 0.60), opt_h - 4), pygame.SRCALPHA)
                        if idx == config_selected:
                            row_bg.fill((0, 40, 60, 150))
                        else:
                            row_bg.fill((15, 18, 28, 80))
                        row_x = SCREEN_W // 2 - int(SCREEN_W * 0.30)
                        screen.blit(row_bg, (row_x, oy))
                        if idx == config_selected:
                            pygame.draw.rect(screen, (0, 180, 220), (row_x, oy, int(SCREEN_W * 0.60), opt_h - 4), 1, border_radius=3)
                        # Label
                        lbl = font_cfg_label.render(opt["label"], True, (200, 200, 210))
                        screen.blit(lbl, (row_x + 15, oy + (opt_h - 4) // 2 - lbl.get_height() // 2))
                        # Valor
                        val_x = row_x + int(SCREEN_W * 0.40)
                        val_cy = oy + (opt_h - 4) // 2
                        if opt["type"] == "number":
                            # Obtener valor actual
                            if opt["key"] == "timer": val = cfg_timer
                            elif opt["key"] == "risk": val = cfg_risk
                            elif opt["key"] == "tp_mult": val = cfg_tp_mult
                            elif opt["key"] == "bot_wr": val = cfg_bot_wr
                            elif opt["key"] == "vol_music": val = cfg_vol_music
                            elif opt["key"] == "vol_fx": val = cfg_vol_fx
                            else: val = 0
                            if opt["key"] == "tp_mult":
                                val_str = f"1:{val:.1f}"
                            else:
                                val_str = str(int(val))
                            # Flechas < >
                            arrow_color = (0, 220, 255) if idx == config_selected else (80, 80, 100)
                            left_arrow = font_cfg_val.render("<", True, arrow_color)
                            right_arrow = font_cfg_val.render(">", True, arrow_color)
                            val_txt = font_cfg_val.render(val_str, True, (255, 255, 255))
                            screen.blit(left_arrow, (val_x, val_cy - left_arrow.get_height() // 2))
                            screen.blit(val_txt, val_txt.get_rect(center=(val_x + 60, val_cy)))
                            screen.blit(right_arrow, (val_x + 100, val_cy - right_arrow.get_height() // 2))
                        elif opt["type"] == "toggle":
                            if opt["key"] == "bot_enabled": val = cfg_bot_enabled
                            elif opt["key"] == "viewers_enabled": val = cfg_viewers_enabled
                            else: val = False
                            toggle_color = (38, 166, 154) if val else (239, 83, 80)
                            toggle_txt = font_cfg_val.render("ON" if val else "OFF", True, toggle_color)
                            screen.blit(toggle_txt, toggle_txt.get_rect(center=(val_x + 60, val_cy)))
                        elif opt["type"] == "button":
                            btn_color = (239, 83, 80) if idx == config_selected else (100, 40, 40)
                            btn_rect = pygame.Rect(val_x, val_cy - 15, 120, 30)
                            pygame.draw.rect(screen, btn_color, btn_rect, border_radius=5)
                            btn_txt = font_cfg_label.render("RESET", True, (255, 255, 255))
                            screen.blit(btn_txt, btn_txt.get_rect(center=btn_rect.center))
                    # Instrucciones abajo
                    font_cfg_hint = pygame.font.SysFont("Arial", int(SCREEN_H * 0.015))
                    hint_txt = font_cfg_hint.render("Flechas = Navegar | Izq/Der = Cambiar | ESC = Volver", True, (60, 80, 100))
                    screen.blit(hint_txt, hint_txt.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.94))))
                    # Confirmación de reset
                    if config_confirm_reset:
                        confirm_overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                        confirm_overlay.fill((0, 0, 0, 180))
                        screen.blit(confirm_overlay, (0, 0))
                        confirm_txt = font_cfg_title.render("RESETEAR RANKING?", True, (255, 80, 80))
                        screen.blit(confirm_txt, confirm_txt.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.40))))
                        sub_txt = font_cfg_label.render("Todos los balances vuelven a 10000 FXP", True, (200, 200, 200))
                        screen.blit(sub_txt, sub_txt.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.48))))
                        hint2 = font_cfg_label.render("ENTER = Confirmar | ESC = Cancelar", True, (100, 150, 180))
                        screen.blit(hint2, hint2.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.56))))
                    pygame.display.flip()
                    for cfg_event in pygame.event.get():
                        if cfg_event.type == pygame.QUIT:
                            in_config = False
                            in_menu = False
                            app_running = False
                        elif cfg_event.type == pygame.KEYDOWN:
                            if config_confirm_reset:
                                if cfg_event.key == pygame.K_RETURN:
                                    from database import reset_all_players
                                    try:
                                        reset_all_players()
                                    except Exception as e:
                                        print(f"[ERROR RESET] {e}")
                                    fxp_balance = 10000
                                    wins = 0
                                    losses = 0
                                    trade_history.clear()
                                    top_viewers = load_top_viewers()
                                    config_confirm_reset = False
                                elif cfg_event.key == pygame.K_ESCAPE:
                                    config_confirm_reset = False
                            else:
                                if cfg_event.key == pygame.K_ESCAPE:
                                    # Guardar config y salir
                                    from database import set_config as _set_cfg
                                    _set_cfg("timer_duration", str(cfg_timer * 1000))
                                    _set_cfg("trade_risk", str(cfg_risk))
                                    _set_cfg("tp_multiplier", str(cfg_tp_mult))
                                    _set_cfg("bot_enabled", "1" if cfg_bot_enabled else "0")
                                    _set_cfg("bot_win_rate", str(cfg_bot_wr / 100.0))
                                    _set_cfg("viewers_enabled", "1" if cfg_viewers_enabled else "0")
                                    _set_cfg("vol_music", str(cfg_vol_music))
                                    _set_cfg("vol_fx", str(cfg_vol_fx))
                                    # Aplicar al juego
                                    TIMER_DURATION = cfg_timer * 1000
                                    TRADE_RISK = cfg_risk
                                    TP_MULTIPLIER = cfg_tp_mult
                                    BOT_ENABLED = cfg_bot_enabled
                                    BOT_WIN_RATE = cfg_bot_wr / 100.0
                                    VIEWER_BOTS_ENABLED = cfg_viewers_enabled
                                    if sound_game_music is not None:
                                        sound_game_music.set_volume(cfg_vol_music / 100.0)
                                    if music_playing:
                                        pygame.mixer.music.set_volume(cfg_vol_music / 100.0)
                                    if sound_ambient is not None:
                                        sound_ambient.set_volume(cfg_vol_music / 100.0)
                                    if sound_ambient is not None:
                                        sound_ambient.set_volume(cfg_vol_music / 100.0)
                                    # Aplicar volumen de efectos a todos los sonidos
                                    fx_vol = cfg_vol_fx / 100.0
                                    for s in [sound_bos, sound_fractal, sound_win, sound_loss, sound_zoom, sound_tick, sound_levelup]:
                                        if s is not None:
                                            s.set_volume(fx_vol)
                                    for s in zona_voices + lean_buy_voices + lean_sell_voices + voz_win_voices + voz_loss_voices:
                                        if s is not None:
                                            s.set_volume(fx_vol)
                                    in_config = False
                                elif cfg_event.key == pygame.K_DOWN:
                                    config_selected = (config_selected + 1) % len(config_options)
                                elif cfg_event.key == pygame.K_UP:
                                    config_selected = (config_selected - 1) % len(config_options)
                                elif cfg_event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                                    opt = config_options[config_selected]
                                    direction = 1 if cfg_event.key == pygame.K_RIGHT else -1
                                    if opt["type"] == "number":
                                        if opt["key"] == "timer":
                                            cfg_timer = max(opt["min"], min(opt["max"], cfg_timer + opt["step"] * direction))
                                        elif opt["key"] == "risk":
                                            cfg_risk = max(opt["min"], min(opt["max"], cfg_risk + opt["step"] * direction))
                                        elif opt["key"] == "tp_mult":
                                            cfg_tp_mult = max(opt["min"], min(opt["max"], cfg_tp_mult + opt["step"] * direction))
                                        elif opt["key"] == "bot_wr":
                                            cfg_bot_wr = max(opt["min"], min(opt["max"], cfg_bot_wr + opt["step"] * direction))
                                        elif opt["key"] == "vol_music":
                                            cfg_vol_music = max(opt["min"], min(opt["max"], cfg_vol_music + opt["step"] * direction))
                                        elif opt["key"] == "vol_fx":
                                            cfg_vol_fx = max(opt["min"], min(opt["max"], cfg_vol_fx + opt["step"] * direction))
                                    elif opt["type"] == "toggle":
                                        if opt["key"] == "bot_enabled":
                                            cfg_bot_enabled = not cfg_bot_enabled
                                        elif opt["key"] == "viewers_enabled":
                                            cfg_viewers_enabled = not cfg_viewers_enabled
                                elif cfg_event.key == pygame.K_RETURN:
                                    opt = config_options[config_selected]
                                    if opt["type"] == "button" and opt["key"] == "reset":
                                        config_confirm_reset = True
            menu_click_btn = None
        # Áreas de botones calibradas con clicks en 1366x768
        btn_w = int(SCREEN_W * 0.28)
        btn_h = int(SCREEN_H * 0.08)
        btn_iniciar = pygame.Rect(int(SCREEN_W * (681/1366)) - btn_w // 2, int(SCREEN_H * (341/768)) - btn_h // 2, btn_w, btn_h)
        btn_config = pygame.Rect(int(SCREEN_W * (952/1920)) - btn_w // 2, int(SCREEN_H * (862/1080)) - btn_h // 2, btn_w, btn_h)
        # Dibujar efecto click (oscurecer en el centro del botón)
        buttons = [("iniciar", btn_iniciar), ("config", btn_config)]
        for btn_name, btn_rect in buttons:
            if menu_click_btn == btn_name:
                dark_surface = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
                dark_surface.fill((0, 0, 0, 80))
                screen.blit(dark_surface, (btn_rect.x, btn_rect.y))
        pygame.display.flip()
    

    # --- GAME LOOP ---
    running = True
    # === GAME LOOP ===
    while running and app_running:
        clock.tick(60)
        current_time = pygame.time.get_ticks()
        screen.fill((30, 30, 30))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Diálogo de pausa: ¿Volver al menú o cerrar?
                    paused = True
                    pygame.event.clear()
                    pygame.time.wait(100)
                    while paused:
                        # Fondo oscuro semi-transparente
                        pause_overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                        pause_overlay.fill((0, 0, 0, 150))
                        screen.blit(pause_overlay, (0, 0))
                        # Texto
                        pause_title = font_timer.render("PAUSA", True, (255, 255, 0))
                        screen.blit(pause_title, pause_title.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.30))))
                        # Botones
                        btn_resume = pygame.Rect(SCREEN_W // 2 - 140, int(SCREEN_H * 0.42), 280, 50)
                        btn_menu = pygame.Rect(SCREEN_W // 2 - 140, int(SCREEN_H * 0.52), 280, 50)
                        btn_quit = pygame.Rect(SCREEN_W // 2 - 140, int(SCREEN_H * 0.62), 280, 50)
                        pygame.draw.rect(screen, (38, 166, 154), btn_resume, border_radius=8)
                        pygame.draw.rect(screen, (100, 100, 100), btn_menu, border_radius=8)
                        pygame.draw.rect(screen, (239, 83, 80), btn_quit, border_radius=8)
                        res_txt = font_btn.render("CONTINUAR", True, (255, 255, 255))
                        menu_txt = font_btn.render("VOLVER AL MENU", True, (255, 255, 255))
                        quit_txt = font_btn.render("CERRAR JUEGO", True, (255, 255, 255))
                        screen.blit(res_txt, res_txt.get_rect(center=btn_resume.center))
                        screen.blit(menu_txt, menu_txt.get_rect(center=btn_menu.center))
                        screen.blit(quit_txt, quit_txt.get_rect(center=btn_quit.center))
                        pygame.display.flip()
                        for p_event in pygame.event.get():
                            if p_event.type == pygame.QUIT:
                                paused = False
                                running = False
                            elif p_event.type == pygame.KEYDOWN:
                                if p_event.key == pygame.K_ESCAPE:
                                    paused = False  # Continuar
                            elif p_event.type == pygame.MOUSEBUTTONDOWN and p_event.button == 1:
                                pmx, pmy = p_event.pos
                                if btn_resume.collidepoint(pmx, pmy):
                                    paused = False
                                elif btn_menu.collidepoint(pmx, pmy):
                                        paused = False
                                        running = False
                                        if sound_game_music is not None:
                                            sound_game_music.stop()
                                elif btn_quit.collidepoint(pmx, pmy):
                                    paused = False
                                    running = False
                                    app_running = False
                elif event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS or event.key == pygame.K_EQUALS:
                    TIMER_DURATION = min(30000, TIMER_DURATION + 1000)
                elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                    TIMER_DURATION = max(3000, TIMER_DURATION - 1000)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                print(f"[CLICK] x={mx}, y={my}")
        # --- LOGICA DEL TIMER ---
        # --- LOGICA DEL TIMER ---
        if zone_frozen:
            elapsed = current_time - zone_timer_start
            # Delay de voz: el timer no cuenta hasta que la voz termine (4 seg aprox)
            VOICE_DELAY = 4000
            timer_elapsed = max(0, elapsed - VOICE_DELAY)
            if timer_elapsed >= TIMER_DURATION:
                # Timer terminó, reanudar gráfico
                # Si nadie eligió, el bot decide automáticamente
                if not trade_decided and BOT_ENABLED and active_trade is None:
                    can_trade = True
                    # Verificar cooldown
                    if current_time - bot_last_trade_time < BOT_COOLDOWN and bot_last_trade_time > 0:
                        can_trade = False
                    # Verificar máx ops/hora
                    if current_time - bot_hour_start > 3600000:
                        bot_ops_this_hour = 0
                        bot_hour_start = current_time
                    if bot_ops_this_hour >= BOT_MAX_OPS_HOUR:
                        can_trade = False
                    if can_trade and zone_detected is not None and zone_detected.get("source") == "EXTREMO":
                        entry_price = current_candle["close"]
                        # Bot LEAN FX: solo opera EXTREMO
                        if zone_detected["type"] == "ALCISTA":
                            bot_decision = "BUY"
                        else:
                            bot_decision = "SELL"
                        if bot_decision == "BUY":
                            sl_price = zone_detected["low"] - SL_BUFFER
                            sl_distance = entry_price - sl_price
                            tp_distance = sl_distance * TP_MULTIPLIER
                            active_trade = {
                                "type": "BUY",
                                "entry": entry_price,
                                "sl": sl_price,
                                "tp": entry_price + tp_distance,
                                "entry_index": len(candles),
                            }
                        else:
                            sl_price = zone_detected["high"] + SL_BUFFER
                            sl_distance = sl_price - entry_price
                            tp_distance = sl_distance * TP_MULTIPLIER
                            active_trade = {
                                "type": "SELL",
                                "entry": entry_price,
                                "sl": sl_price,
                                "tp": entry_price - tp_distance,
                                "entry_index": len(candles),
                            }
                        # Activar sesgo del precio a favor del bot (70% win rate)
                        if random.random() < BOT_WIN_RATE:
                            bot_bias_active = True
                            bot_bias_direction = 1 if bot_decision == "BUY" else -1
                        else:
                            bot_bias_active = True
                            bot_bias_direction = -1 if bot_decision == "BUY" else 1
                        bot_last_trade_time = current_time
                        bot_ops_this_hour += 1
                        trade_decided = True
                        play_sound(sound_bos)
                        # Voz LEAN FX anuncia su trade
                        if bot_decision == "BUY" and lean_buy_voices:
                            random.choice(lean_buy_voices).play()
                            voice_freeze_active = True
                            voice_freeze_start = current_time
                        elif bot_decision == "SELL" and lean_sell_voices:
                            random.choice(lean_sell_voices).play()
                            voice_freeze_active = True
                            voice_freeze_start = current_time
                zone_frozen = False
                # Crear trade de viewers ahora que terminó el timer
                if viewer_votes and viewer_trade_active is None and zone_detected is not None:
                    entry_price = current_candle["close"]
                    current_zone_id = list(zones_mitigated)[-1] if zones_mitigated else ""
                    viewer_trade_is_extremo = current_zone_id.startswith("ob_")
                    if zone_detected["type"] == "ALCISTA":
                        sl_price = zone_detected["low"] - SL_BUFFER
                        sl_distance = entry_price - sl_price
                        tp_distance = sl_distance * TP_MULTIPLIER
                        viewer_trade_active = {
                            "type": "BUY", "entry": entry_price,
                            "sl": sl_price, "tp": entry_price + tp_distance,
                            "entry_index": len(candles),
                        }
                    else:
                        sl_price = zone_detected["high"] + SL_BUFFER
                        sl_distance = sl_price - entry_price
                        tp_distance = sl_distance * TP_MULTIPLIER
                        viewer_trade_active = {
                            "type": "SELL", "entry": entry_price,
                            "sl": sl_price, "tp": entry_price - tp_distance,
                            "entry_index": len(candles),
                        }
                zone_detected = None
                trade_decided = False
                last_tick_second = -1
        # --- Descongelar voice freeze ---
        if voice_freeze_active and current_time - voice_freeze_start > VOICE_FREEZE_DURATION:
            voice_freeze_active = False
        # --- PLAYLIST: pasar a siguiente canción cuando termina ---
        if music_playing and not pygame.mixer.music.get_busy():
            music_current_index = (music_current_index + 1) % len(music_playlist)
            try:
                pygame.mixer.music.load(music_playlist[music_current_index])
                pygame.mixer.music.play()
            except:
                pass
        # --- VOZ ENTRE TRADES (mantener atención) ---
        if game_started and not zone_frozen and not voice_freeze_active and active_trade is None and viewer_trade_active is None:
            if not hasattr(pygame, '_idle_voice_last'):
                pygame._idle_voice_last = current_time
            if current_time - pygame._idle_voice_last > 35000:  # Cada 35 segundos
                pygame._idle_voice_last = current_time
                idle_voices = []
                for i in range(1, 8):
                    sv = load_sound(f"IDLE_VOZ_{i}.mp3")
                    if sv is not None:
                        idle_voices.append(sv)
                if idle_voices:
                    random.choice(idle_voices).play()
        # --- MOVER PRECIO (solo si NO está congelado y NO hay voice freeze) ---
        if not zone_frozen and not voice_freeze_active:
            if current_time - last_tick_time >= TICK_DELAY:
                step_size = random.uniform(0.4, 1.8)
                # Sesgo del bot: 65% probabilidad de ir en su dirección
                if bot_bias_active and active_trade is not None:
                    tick_move = step_size * bot_bias_direction if random.random() < 0.65 else -step_size * bot_bias_direction
                else:
                    tick_move = step_size if random.random() < 0.5 else -step_size
                current_candle["close"] += tick_move
                current_candle["high"] = max(current_candle["high"], current_candle["close"])
                current_candle["low"] = min(current_candle["low"], current_candle["close"])
                last_tick_time = current_time
                # --- EVALUAR TRADE ACTIVO ---
                if active_trade is not None:
                    current_price = current_candle["close"]
                    if active_trade["type"] == "BUY":
                        if current_price >= active_trade["tp"]:
                            trade_win(TRADE_RISK * TP_MULTIPLIER)
                            trade_history.append({"type": "BUY", "result": "WIN", "pnl": TRADE_RISK * TP_MULTIPLIER})
                            active_trade = None
                            bot_bias_active = False
                            viewer_votes_display = []
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (38, 166, 154)
                            flash_text = f"WIN +{int(TP_MULTIPLIER)}%"
                            total_operations += 1
                            if voz_win_voices and viewer_trade_active is None:
                                random.choice(voz_win_voices).play()
                                voice_freeze_active = True
                                voice_freeze_start = current_time
                        elif current_price <= active_trade["sl"]:
                            trade_loss(TRADE_RISK)
                            trade_history.append({"type": "BUY", "result": "LOSS", "pnl": -TRADE_RISK})
                            active_trade = None
                            bot_bias_active = False
                            viewer_votes_display = []
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (239, 83, 80)
                            flash_text = "LOSS -1%"
                            total_operations += 1
                            if voz_loss_voices and viewer_trade_active is None:
                                random.choice(voz_loss_voices).play()
                                voice_freeze_active = True
                                voice_freeze_start = current_time
                    elif active_trade["type"] == "SELL":
                        if current_price <= active_trade["tp"]:
                            trade_win(TRADE_RISK * TP_MULTIPLIER)
                            trade_history.append({"type": "SELL", "result": "WIN", "pnl": TRADE_RISK * TP_MULTIPLIER})
                            active_trade = None
                            bot_bias_active = False
                            viewer_votes_display = []
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (38, 166, 154)
                            flash_text = f"WIN +{int(TP_MULTIPLIER)}%"
                            total_operations += 1
                            if voz_win_voices and viewer_trade_active is None:
                                random.choice(voz_win_voices).play()
                                voice_freeze_active = True
                                voice_freeze_start = current_time
                        elif current_price >= active_trade["sl"]:
                            trade_loss(TRADE_RISK)
                            trade_history.append({"type": "SELL", "result": "LOSS", "pnl": -TRADE_RISK})
                            active_trade = None
                            bot_bias_active = False
                            viewer_votes_display = []
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (239, 83, 80)
                            flash_text = "LOSS -1%"
                            total_operations += 1
                            if voz_loss_voices and viewer_trade_active is None:
                                random.choice(voz_loss_voices).play()
                                voice_freeze_active = True
                                voice_freeze_start = current_time
                # --- DETECTAR SI PRECIO LLEGA A UNA ZONA (solo 1 vez por zona) ---
                if active_trade is None and not zone_frozen and viewer_trade_active is None and not voice_freeze_active:
                    price_now = current_candle["close"]
                    # Verificar Order Block activo
                    if active_ob is not None:
                        zone_id = f"ob_{active_ob['index']}"
                        # También verificar por precio (evitar reactivar zona similar)
                        zone_price_id = f"ob_{int(active_ob['high']*10)}_{int(active_ob['low']*10)}"
                        if zone_id not in zones_mitigated and zone_price_id not in zones_mitigated and active_ob["low"] <= price_now <= active_ob["high"]:
                            zone_frozen = True
                            zone_timer_start = current_time
                            zone_detected = {"high": active_ob["high"], "low": active_ob["low"], "type": active_ob["type"], "source": "EXTREMO"}
                            zones_mitigated.add(zone_id)
                            zones_mitigated.add(zone_price_id)
                            zones_mitigated_info[zone_id] = {"index": len(candles), "bos_count": 0}
                            zones_mitigated_info[zone_price_id] = {"index": len(candles), "bos_count": 0}
                            # Si el Decisional se superpone, mitigarlo también (no activar 2 entradas)
                            if active_decisional is not None:
                                dec_id = f"dec_{active_decisional['index']}"
                                dec_price_id = f"dec_{int(active_decisional['high']*10)}_{int(active_decisional['low']*10)}"
                                if active_decisional["low"] <= price_now <= active_decisional["high"]:
                                    zones_mitigated.add(dec_id)
                                    zones_mitigated.add(dec_price_id)
                                    zones_mitigated_info[dec_id] = {"index": len(candles), "bos_count": 0}
                                    zones_mitigated_info[dec_price_id] = {"index": len(candles), "bos_count": 0}
                            # Reproducir voz aleatoria de zona
                            if zona_voices:
                                vi = random.randint(0, len(zona_voices) - 1)
                                while vi == zona_voice_last and len(zona_voices) > 1:
                                    vi = random.randint(0, len(zona_voices) - 1)
                                zona_voice_last = vi
                                zona_voices[vi].play()
                    # Verificar Decisional
                    if not zone_frozen and active_decisional is not None:
                        zone_id = f"dec_{active_decisional['index']}"
                        zone_price_id = f"dec_{int(active_decisional['high']*10)}_{int(active_decisional['low']*10)}"
                        if zone_id not in zones_mitigated and zone_price_id not in zones_mitigated and active_decisional["low"] <= price_now <= active_decisional["high"]:
                            zone_frozen = True
                            zone_timer_start = current_time
                            zone_detected = {"high": active_decisional["high"], "low": active_decisional["low"], "type": active_decisional["type"], "source": "DECISIONAL"}
                            zones_mitigated.add(zone_id)
                            zones_mitigated.add(zone_price_id)
                            zones_mitigated_info[zone_id] = {"index": len(candles), "bos_count": 0}
                            zones_mitigated_info[zone_price_id] = {"index": len(candles), "bos_count": 0}
                            # Reproducir voz aleatoria de zona
                            if zona_voices:
                                vi = random.randint(0, len(zona_voices) - 1)
                                while vi == zona_voice_last and len(zona_voices) > 1:
                                    vi = random.randint(0, len(zona_voices) - 1)
                                zona_voice_last = vi
                                zona_voices[vi].play()
                    # FVG NO se opera por ahora (solo se dibuja)
                    # if not zone_frozen and active_fvg is not None:
                    #     zone_id = f"fvg_{active_fvg['index']}"
                    #     if zone_id not in zones_mitigated and active_fvg["low"] <= price_now <= active_fvg["high"]:
                    #         zone_frozen = True
                    #         zone_timer_start = current_time
                    #         zone_detected = {"high": active_fvg["high"], "low": active_fvg["low"], "type": active_fvg["type"]}
                    #         zones_mitigated.add(zone_id)
        # --- VIEWERS: TikTok Live real O bots simulados ---
        if game_started and zone_frozen and not getattr(pygame, '_viewers_voted_this_zone', False):
            pygame._viewers_voted_this_zone = True
            # Abrir votación en TikTok
            tiktok_chat.open_voting()

        # Recoger votos de TikTok (se actualizan en tiempo real)
        if game_started and zone_frozen and tiktok_chat.is_connected():
            tiktok_votes = tiktok_chat.get_votes()
            if tiktok_votes:
                # Usar votos reales de TikTok
                viewer_votes = []
                for tv in tiktok_votes:
                    viewer_votes.append({"name": tv["name"], "vote": tv["vote"]})
                    # Crear jugador en DB si no existe
                    from database import get_player
                    if not get_player(tv["name"]):
                        create_player(tv["name"])
                viewer_votes_display = viewer_votes.copy()
        # Bots de backup (solo si TikTok no está conectado o no hay votos reales)
        elif VIEWER_BOTS_ENABLED and game_started and zone_frozen and not tiktok_chat.is_connected():
            if not viewer_votes:
                num_voters = random.randint(2, 4)
                all_viewer_names = [v["name"] for v in load_top_viewers()]
                if all_viewer_names:
                    voters = random.sample(all_viewer_names, min(num_voters, len(all_viewer_names)))
                    viewer_votes = []
                    for chosen in voters:
                        vote = random.choice(["BUY", "SELL"])
                        viewer_votes.append({"name": chosen, "vote": vote})
                    viewer_votes_display = viewer_votes.copy()
        # Cerrar votación cuando se descongela
        if not zone_frozen:
            pygame._viewers_voted_this_zone = False
            tiktok_chat.close_voting()
        # --- RESOLVER TRADE DE VIEWERS (cuando precio toca TP/SL) ---
        if viewer_trade_active is not None and not zone_frozen:
            vt_price = current_candle["close"]
            vt_won = False
            vt_lost = False
            if viewer_trade_active["type"] == "BUY":
                if vt_price >= viewer_trade_active["tp"]:
                    vt_won = True
                elif vt_price <= viewer_trade_active["sl"]:
                    vt_lost = True
            else:
                if vt_price <= viewer_trade_active["tp"]:
                    vt_won = True
                elif vt_price >= viewer_trade_active["sl"]:
                    vt_lost = True
            if vt_won or vt_lost:
                correct_dir = viewer_trade_active["type"]
                for v in viewer_votes:
                    # Buscar player directamente por nombre
                    from database import get_player
                    pl = get_player(v["name"])
                    if pl:
                        if (vt_won and v["vote"] == correct_dir) or (vt_lost and v["vote"] != correct_dir):
                            gain = int(TRADE_RISK * TP_MULTIPLIER)
                            update_player_balance(v["name"], pl["balance"] + gain, win=True)
                        else:
                            update_player_balance(v["name"], max(8000, pl["balance"] - TRADE_RISK), loss=True)
                # Flash + voz al resolver trade de viewers
                if vt_won:
                    flash_active = True
                    flash_start_time = current_time
                    flash_color = (38, 166, 154)
                    flash_text = f"WIN +{int(TP_MULTIPLIER)}%"
                    total_operations += 1
                    if voz_win_voices:
                        random.choice(voz_win_voices).play()
                        voice_freeze_active = True
                        voice_freeze_start = current_time
                else:
                    flash_active = True
                    flash_start_time = current_time
                    flash_color = (239, 83, 80)
                    flash_text = "LOSS -1%"
                    total_operations += 1
                    if voz_loss_voices:
                        random.choice(voz_loss_voices).play()
                        voice_freeze_active = True
                        voice_freeze_start = current_time
                # Refrescar TOP 5 después de resolver
                # Actualizar streaks
                correct_dir = viewer_trade_active["type"] if vt_won else ("SELL" if viewer_trade_active["type"] == "BUY" else "BUY")
                for v in viewer_votes:
                    won_trade = (vt_won and v["vote"] == viewer_trade_active["type"]) or (vt_lost and v["vote"] != viewer_trade_active["type"])
                    if won_trade:
                        viewer_streaks[v["name"]] = viewer_streaks.get(v["name"], 0) + 1
                        if viewer_streaks[v["name"]] >= STREAK_MIN:
                            streak_display = {"name": v["name"], "streak": viewer_streaks[v["name"]], "start_time": current_time}
                    else:
                        viewer_streaks[v["name"]] = 0
                check_top5_levelup_sound(current_time)
                viewer_trade_active = None
                viewer_votes = []
                if active_trade is None:
                    viewer_votes_display = []
        if not zone_frozen and not voice_freeze_active and current_time - last_candle_time >= CANDLE_DURATION:
            candles.append(current_candle.copy())
            if len(candles) > 1000:
                candles.pop(0)
                for bos in bos_markers:
                    bos["level_index"] -= 1
                    bos["break_index"] -= 1
                bos_markers[:] = [b for b in bos_markers if b["break_index"] >= 0]
                for f in confirmed_fractals:
                    f["index"] -= 1
                confirmed_fractals[:] = [f for f in confirmed_fractals if f["index"] >= 0]
                last_checked_index -= 1
                if range_high_index is not None:
                    range_high_index -= 1
                if range_low_index is not None:
                    range_low_index -= 1
                if prev_range_low_index is not None:
                    prev_range_low_index -= 1
                if prev_range_high_index is not None:
                    prev_range_high_index -= 1
                if active_ob is not None:
                    active_ob["index"] -= 1
                    if "end_index" in active_ob:
                        active_ob["end_index"] -= 1
                    if active_ob["index"] < 0:
                        active_ob = None
                if prev_ob is not None:
                    prev_ob["index"] -= 1
                    if "end_index" in prev_ob:
                        prev_ob["end_index"] -= 1
                    if prev_ob["index"] < 0:
                        prev_ob = None
                if active_decisional is not None:
                    active_decisional["index"] -= 1
                    if active_decisional["index"] < 0:
                        active_decisional = None
                if active_fvg is not None:
                    active_fvg["index"] -= 1
                    if active_fvg["index"] < 0:
                        active_fvg = None
                if active_trade is not None and "entry_index" in active_trade:
                    active_trade["entry_index"] -= 1
                if viewer_trade_active is not None and "entry_index" in viewer_trade_active:
                    viewer_trade_active["entry_index"] -= 1
            current_len = len(candles)
            bos_markers[:] = [b for b in bos_markers if current_len - b["break_index"] <= 999]
            confirmed_fractals[:] = [f for f in confirmed_fractals if current_len - f["index"] <= 999]
            process_new_candle(candles, len(candles) - 1)
            last_checked_index = len(candles)
            current_candle = {"open": candles[-1]["close"], "close": candles[-1]["close"], "high": candles[-1]["close"], "low": candles[-1]["close"]}
            last_candle_time = current_time
        all_candles = candles + [current_candle]
        total_len = len(all_candles)
        needed_count = 60  # Base: mostrar últimas 60 velas
        # Solo mirar el último rango (no ir tan atrás)
        if prev_range_low_index is not None:
            distance = total_len - prev_range_low_index
            if distance > needed_count and distance < 120:
                needed_count = distance + 10
        if prev_range_high_index is not None:
            distance = total_len - prev_range_high_index
            if distance > needed_count and distance < 120:
                needed_count = distance + 10
        if range_phase == "rango_definido":
            if range_high_index is not None:
                distance = total_len - range_high_index
                if distance > needed_count and distance < 120:
                    needed_count = distance + 10
            if range_low_index is not None:
                distance = total_len - range_low_index
                if distance > needed_count and distance < 120:
                    needed_count = distance + 10
        needed_count = max(50, min(needed_count, 100))
        new_target = float(needed_count)
        # Sonido de ZOOM cuando el zoom cambia significativamente
        if abs(new_target - target_visible_count) > 15:
            play_sound(sound_zoom)
        target_visible_count = new_target
        current_visible_count += (target_visible_count - current_visible_count) * 0.08
        num_visible = int(current_visible_count)
        visible_candles = all_candles[-num_visible:]
        if visible_candles:
            all_highs = [c["high"] for c in visible_candles]
            all_lows = [c["low"] for c in visible_candles]
            max_p = max(all_highs)
            min_p = min(all_lows)
            price_range = max_p - min_p
            if price_range == 0:
                price_range = 1.0
            vertical_zoom = (SCREEN_H * 0.75) / price_range
            view_center_price = min_p + price_range / 2
            center_y = int(SCREEN_H * 0.55)
            chart_start_x = 0
            chart_end_x = int(SCREEN_W * 0.75)
            # Velas ocupan hasta 70%
            available_width = int(SCREEN_W * 0.67) - chart_start_x
            spacing = available_width / max(num_visible - 1, 1)
            candle_width = max(3, int(spacing * 0.65))
            start_x = chart_start_x
            total_candles = len(all_candles)
            visible_start_global = total_candles - len(visible_candles)
            # --- RENDERIZAR ORDER BLOCKS, DECISIONAL, FVG ---
            ob_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for ob_data, ob_opacity, ob_label in [(prev_ob, 20, ""), (active_ob, 40, "EXTREMO")]:
                if ob_data is None:
                    continue
                # No dibujar si ya fue mitigada
                ob_zone_id = f"ob_{ob_data['index']}"
                ob_price_id = f"ob_{int(ob_data['high']*10)}_{int(ob_data['low']*10)}"
                # Si fue mitigada, dibujar solo hasta el punto de mitigación
                mitigated = ob_zone_id in zones_mitigated or ob_price_id in zones_mitigated
                if mitigated:
                    info = zones_mitigated_info.get(ob_zone_id) or zones_mitigated_info.get(ob_price_id)
                    if info and info.get("bos_count", 0) >= 2:
                        continue  # Ya pasaron 2 BOS, borrar
                ob_vis = ob_data["index"] - visible_start_global
                if ob_vis >= len(visible_candles):
                    continue
                if ob_vis < 0:
                    ob_x_start = 0
                else:
                    ob_x_start = int(start_x + (ob_vis * spacing))
                if "end_index" in ob_data:
                    ob_end_vis = ob_data["end_index"] - visible_start_global
                    if ob_end_vis < 0:
                        continue
                    ob_x_end = int(start_x + (ob_end_vis * spacing)) + candle_width
                else:
                    ob_x_end = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
                # Si fue mitigada, limitar hasta el punto de mitigación
                if mitigated:
                    info = zones_mitigated_info.get(ob_zone_id) or zones_mitigated_info.get(ob_price_id)
                    if info:
                        mit_vis = info["index"] - visible_start_global
                        if 0 <= mit_vis < len(visible_candles):
                            ob_x_end = int(start_x + (mit_vis * spacing)) + candle_width
                ob_y_high = center_y - int((ob_data["high"] - view_center_price) * vertical_zoom)
                ob_y_low = center_y - int((ob_data["low"] - view_center_price) * vertical_zoom)
                ob_height = max(1, ob_y_low - ob_y_high)
                ob_width = max(1, ob_x_end - ob_x_start)
                if ob_data["type"] == "ALCISTA":
                    ob_color = (38, 166, 154, ob_opacity)
                else:
                    ob_color = (239, 83, 80, ob_opacity)
                pygame.draw.rect(ob_surface, ob_color, (ob_x_start, ob_y_high, ob_width, ob_height))
                if ob_label:
                    label_txt = font_ob.render(ob_label, True, (255, 255, 255))
                    label_rect = label_txt.get_rect(center=(ob_x_start + ob_width // 2, ob_y_high + ob_height // 2))
                    ob_surface.blit(label_txt, label_rect)
            if active_decisional is not None:
                # No dibujar si ya fue mitigada
                dec_zone_id = f"dec_{active_decisional['index']}"
                dec_price_id = f"dec_{int(active_decisional['high']*10)}_{int(active_decisional['low']*10)}"
                if dec_zone_id not in zones_mitigated and dec_price_id not in zones_mitigated:
                    dec_vis = active_decisional["index"] - visible_start_global
                    if 0 <= dec_vis < len(visible_candles):
                        dec_x_start = int(start_x + (dec_vis * spacing))
                        dec_x_end = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
                        dec_y_high = center_y - int((active_decisional["high"] - view_center_price) * vertical_zoom)
                        dec_y_low = center_y - int((active_decisional["low"] - view_center_price) * vertical_zoom)
                        dec_height = max(1, dec_y_low - dec_y_high)
                        dec_width = max(1, dec_x_end - dec_x_start)
                        if active_decisional["type"] == "ALCISTA":
                            dec_color = (38, 166, 154, 30)
                        else:
                            dec_color = (239, 83, 80, 30)
                        pygame.draw.rect(ob_surface, dec_color, (dec_x_start, dec_y_high, dec_width, dec_height))
                        dec_txt = font_ob.render("DECISIONAL", True, (255, 255, 255))
                        dec_rect = dec_txt.get_rect(center=(dec_x_start + dec_width // 2, dec_y_high + dec_height // 2))
                        ob_surface.blit(dec_txt, dec_rect)
                else:
                    # Mitigada: dibujar hasta punto de mitigación, borrar después de 2 BOS
                    info = zones_mitigated_info.get(dec_zone_id) or zones_mitigated_info.get(dec_price_id)
                    if info and info.get("bos_count", 0) < 2:
                        dec_vis = active_decisional["index"] - visible_start_global
                        if 0 <= dec_vis < len(visible_candles):
                            dec_x_start = int(start_x + (dec_vis * spacing))
                            mit_vis = info["index"] - visible_start_global
                            if 0 <= mit_vis < len(visible_candles):
                                dec_x_end = int(start_x + (mit_vis * spacing)) + candle_width
                            else:
                                dec_x_end = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
                            dec_y_high = center_y - int((active_decisional["high"] - view_center_price) * vertical_zoom)
                            dec_y_low = center_y - int((active_decisional["low"] - view_center_price) * vertical_zoom)
                            dec_height = max(1, dec_y_low - dec_y_high)
                            dec_width = max(1, dec_x_end - dec_x_start)
                            if active_decisional["type"] == "ALCISTA":
                                dec_color = (38, 166, 154, 15)
                            else:
                                dec_color = (239, 83, 80, 15)
                            pygame.draw.rect(ob_surface, dec_color, (dec_x_start, dec_y_high, dec_width, dec_height))
            if active_fvg is not None:
                fvg_vis = active_fvg["index"] - visible_start_global
                if 0 <= fvg_vis < len(visible_candles):
                    fvg_x_start = int(start_x + (fvg_vis * spacing))
                    fvg_x_end = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
                    fvg_y_high = center_y - int((active_fvg["high"] - view_center_price) * vertical_zoom)
                    fvg_y_low = center_y - int((active_fvg["low"] - view_center_price) * vertical_zoom)
                    fvg_height = max(1, fvg_y_low - fvg_y_high)
                    fvg_width = max(1, fvg_x_end - fvg_x_start)
                    pygame.draw.rect(ob_surface, (255, 255, 0, 25), (fvg_x_start, fvg_y_high, fvg_width, fvg_height))
                    fvg_txt = font_ob.render("FVG", True, (255, 255, 0))
                    fvg_rect = fvg_txt.get_rect(center=(fvg_x_start + fvg_width // 2, fvg_y_high + fvg_height // 2))
                    ob_surface.blit(fvg_txt, fvg_rect)
            screen.blit(ob_surface, (0, 0))
            for index, candle in enumerate(visible_candles):
                x_pos = int(start_x + (index * spacing))
                y_open = center_y - int((candle["open"] - view_center_price) * vertical_zoom)
                y_close = center_y - int((candle["close"] - view_center_price) * vertical_zoom)
                y_high = center_y - int((candle["high"] - view_center_price) * vertical_zoom)
                y_low = center_y - int((candle["low"] - view_center_price) * vertical_zoom)
                is_bullish = candle["close"] >= candle["open"]
                color = (38, 166, 154) if is_bullish else (239, 83, 80)
                center_x = x_pos + (candle_width // 2)
                top_body = min(y_open, y_close)
                bottom_body = max(y_open, y_close)
                body_height = max(1, bottom_body - top_body)
                pygame.draw.line(screen, color, (center_x, y_high), (center_x, top_body), 1)
                pygame.draw.line(screen, color, (center_x, bottom_body), (center_x, y_low), 1)
                pygame.draw.rect(screen, color, (x_pos, top_body, candle_width, body_height))
            fractal_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            total_fractals = len(confirmed_fractals)
            for idx, frac in enumerate(confirmed_fractals):
                vis_f = frac["index"] - visible_start_global
                if vis_f < 0 or vis_f >= len(visible_candles):
                    continue
                age = (total_fractals - 1 - idx) // 2
                if age == 0:
                    opacity = 204
                elif age == 1:
                    opacity = 128
                elif age == 2:
                    opacity = 90
                else:
                    opacity = 64
                fx = int(start_x + (vis_f * spacing)) + (candle_width // 2)
                fy = center_y - int((frac["price"] - view_center_price) * vertical_zoom)
                if frac["type"] == "high":
                    pygame.draw.circle(fractal_surface, (255, 255, 0, opacity), (fx, fy - 10), 8)
                else:
                    pygame.draw.circle(fractal_surface, (255, 255, 0, opacity), (fx, fy + 10), 8)
            screen.blit(fractal_surface, (0, 0))
            for bos in bos_markers:
                vis_level = bos["level_index"] - visible_start_global
                vis_break = bos["break_index"] - visible_start_global
                if vis_break < 0 or vis_break >= len(visible_candles):
                    continue
                if vis_level >= len(visible_candles):
                    continue
                if vis_level < 0:
                    x_bos_start = start_x
                else:
                    x_bos_start = int(start_x + (vis_level * spacing)) + (candle_width // 2)
                x_bos_end = int(start_x + (vis_break * spacing)) + (candle_width // 2)
                y_level = center_y - int((bos["price"] - view_center_price) * vertical_zoom)
                bos_text = font_bos.render("BOS", True, (255, 255, 255))
                text_rect = bos_text.get_rect(center=((x_bos_start + x_bos_end) // 2, y_level))
                text_margin = 6
                left_end = text_rect.left - text_margin
                for x in range(x_bos_start, left_end, 10):
                    seg_end = min(x + 5, left_end)
                    pygame.draw.line(screen, (255, 255, 255), (x, y_level), (seg_end, y_level), 1)
                right_start = text_rect.right + text_margin
                for x in range(right_start, x_bos_end, 10):
                    seg_end = min(x + 5, x_bos_end)
                    pygame.draw.line(screen, (255, 255, 255), (x, y_level), (seg_end, y_level), 1)
                screen.blit(bos_text, text_rect)
            # --- PANEL VIEWERS (arriba centro, donde estaban los botones) ---
            btn_x = int(SCREEN_W * 0.35)
            btn_y = int(SCREEN_H * 0.03)
            if zone_frozen:
                # Timer activo - mostrar panel de votación
                elapsed = current_time - zone_timer_start
                timer_elapsed_render = max(0, elapsed - 4000)  # VOICE_DELAY
                remaining = max(0, TIMER_DURATION - timer_elapsed_render)
                seconds_left = remaining / 1000.0
                # Tick-tock en los últimos 5 segundos
                current_second = int(seconds_left)
                if seconds_left <= 5.0 and current_second != last_tick_second and seconds_left > 0:
                    play_sound(sound_tick)
                    last_tick_second = current_second
                # === Mix C+A: Panel lateral con estilo banner (sin "ZONA DETECTADA") ===
                slide_progress = min(1.0, (elapsed) / 200.0)  # 200ms slide rápido
                panel_w = int(SCREEN_W * 0.20)
                panel_h = int(SCREEN_H * 0.14)
                panel_x_final = int(SCREEN_W * 0.02)
                panel_x = int(panel_x_final - (1.0 - slide_progress) * (panel_w + 20))
                panel_y = int(SCREEN_H * 0.02)
                # Fondo oscuro
                panel_bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
                panel_bg.fill((5, 10, 20, 230))
                screen.blit(panel_bg, (panel_x, panel_y))
                # Borde dorado pulsante
                border_pulse = int(200 + 55 * math.sin(current_time / 200.0))
                pygame.draw.rect(screen, (border_pulse, int(border_pulse * 0.75), 0), (panel_x, panel_y, panel_w, panel_h), 2, border_radius=6)
                # Barra cyan izquierda (más gruesa, glow)
                pygame.draw.rect(screen, (0, 220, 255), (panel_x, panel_y, 4, panel_h))
                glow_bar = pygame.Surface((8, panel_h), pygame.SRCALPHA)
                glow_bar.fill((0, 200, 255, 40))
                screen.blit(glow_bar, (panel_x, panel_y))
                # Timer grande con glow
                font_timer_mix = pygame.font.SysFont("Arial", int(SCREEN_H * 0.042), bold=True)
                timer_txt = font_timer_mix.render(f"{seconds_left:.1f}s", True, (255, 255, 255))
                # Sombra del timer
                timer_shadow = font_timer_mix.render(f"{seconds_left:.1f}s", True, (0, 100, 130))
                screen.blit(timer_shadow, (panel_x + 14, panel_y + int(panel_h * 0.10) + 2))
                screen.blit(timer_txt, (panel_x + 12, panel_y + int(panel_h * 0.10)))
                # Barra de progreso (más ancha, con glow)
                bar_w_m = int(panel_w * 0.85)
                bar_h_m = 8
                bar_x_m = panel_x + 12
                bar_y_m = panel_y + int(panel_h * 0.58)
                progress = remaining / TIMER_DURATION
                pygame.draw.rect(screen, (20, 25, 35), (bar_x_m, bar_y_m, bar_w_m, bar_h_m), border_radius=4)
                if progress > 0.5:
                    bar_color = (0, 220, 255)
                elif progress > 0.25:
                    bar_color = (255, 220, 0)
                else:
                    bar_color = (255, 50, 50)
                fill_w = int(bar_w_m * progress)
                if fill_w > 0:
                    pygame.draw.rect(screen, bar_color, (bar_x_m, bar_y_m, fill_w, bar_h_m), border_radius=4)
                    # Glow de la barra
                    bar_glow = pygame.Surface((fill_w, bar_h_m + 6), pygame.SRCALPHA)
                    bar_glow.fill((bar_color[0], bar_color[1], bar_color[2], 30))
                    screen.blit(bar_glow, (bar_x_m, bar_y_m - 3))
                # "ESCRIBE BUY O SELL" más grande
                font_escribe_m = pygame.font.SysFont("Arial", int(SCREEN_H * 0.022), bold=True)
                escribe_txt = font_escribe_m.render("ESCRIBE BUY O SELL", True, (0, 200, 220))
                screen.blit(escribe_txt, (panel_x + 12, panel_y + int(panel_h * 0.78)))
                # --- PANEL VIEWERS centrado arriba ---
                if viewer_votes:
                    buy_count = sum(1 for v in viewer_votes if v["vote"] == "BUY")
                    sell_count = sum(1 for v in viewer_votes if v["vote"] == "SELL")
                    total_votes = buy_count + sell_count
                    vbox_w = int(SCREEN_W * 0.24)
                    vbox_h = int(SCREEN_H * 0.07)
                    vbox_x = SCREEN_W // 2 - vbox_w // 2
                    vbox_y = int(SCREEN_H * 0.01)
                    # Fondo
                    vote_bg = pygame.Surface((vbox_w, vbox_h), pygame.SRCALPHA)
                    vote_bg.fill((5, 10, 20, 230))
                    screen.blit(vote_bg, (vbox_x, vbox_y))
                    # Borde cyan
                    pygame.draw.rect(screen, (0, 180, 220), (vbox_x, vbox_y, vbox_w, vbox_h), 2, border_radius=5)
                    # "VIEWERS" centrado arriba
                    font_vw_label = pygame.font.SysFont("Arial", int(SCREEN_H * 0.013), bold=True)
                    vw_lbl = font_vw_label.render(f"VIEWERS ({total_votes})", True, (0, 200, 220))
                    screen.blit(vw_lbl, vw_lbl.get_rect(center=(vbox_x + vbox_w // 2, vbox_y + int(vbox_h * 0.22))))
                    # BUY y SELL grandes
                    font_vote_big = pygame.font.SysFont("Arial", int(SCREEN_H * 0.022), bold=True)
                    buy_txt = font_vote_big.render(f"BUY: {buy_count}", True, (38, 200, 154))
                    sell_txt = font_vote_big.render(f"SELL: {sell_count}", True, (239, 83, 80))
                    screen.blit(buy_txt, buy_txt.get_rect(center=(vbox_x + int(vbox_w * 0.28), vbox_y + int(vbox_h * 0.65))))
                    screen.blit(sell_txt, sell_txt.get_rect(center=(vbox_x + int(vbox_w * 0.72), vbox_y + int(vbox_h * 0.65))))
                    # Separador vertical
                    pygame.draw.line(screen, (0, 100, 130), (vbox_x + vbox_w // 2, vbox_y + int(vbox_h * 0.40)), (vbox_x + vbox_w // 2, vbox_y + int(vbox_h * 0.85)), 1)
            elif active_trade is not None:
                # LEAN FX operando - mostrar info del trade
                info_x = int(SCREEN_W * 0.05)
                info_y = int(SCREEN_H * 0.03)
                trade_color = (38, 166, 154) if active_trade["type"] == "BUY" else (239, 83, 80)
                trade_txt = font_hud_val.render(f"LEAN FX: {active_trade['type']}", True, trade_color)
                screen.blit(trade_txt, (info_x, info_y))
                # PnL grande
                current_price = current_candle["close"]
                if active_trade["type"] == "BUY":
                    pnl_points = current_price - active_trade["entry"]
                else:
                    pnl_points = active_trade["entry"] - current_price
                pnl_color = (38, 166, 154) if pnl_points >= 0 else (239, 83, 80)
                pnl_pct = (pnl_points / active_trade["entry"]) * 100
                pnl_txt = font_timer.render(f"{pnl_pct:+.1f}%", True, pnl_color)
                screen.blit(pnl_txt, (info_x, info_y + 25))
                # Viewers también operan al mismo tiempo - panel centrado arriba
                if viewer_votes_display:
                    buy_count = sum(1 for v in viewer_votes_display if v["vote"] == "BUY")
                    sell_count = sum(1 for v in viewer_votes_display if v["vote"] == "SELL")
                    total_votes = buy_count + sell_count
                    vbox_w = int(SCREEN_W * 0.24)
                    vbox_h = int(SCREEN_H * 0.07)
                    vbox_x = SCREEN_W // 2 - vbox_w // 2
                    vbox_y = int(SCREEN_H * 0.01)
                    vote_bg = pygame.Surface((vbox_w, vbox_h), pygame.SRCALPHA)
                    vote_bg.fill((5, 10, 20, 230))
                    screen.blit(vote_bg, (vbox_x, vbox_y))
                    pygame.draw.rect(screen, (0, 180, 220), (vbox_x, vbox_y, vbox_w, vbox_h), 2, border_radius=5)
                    font_vw_label = pygame.font.SysFont("Arial", int(SCREEN_H * 0.013), bold=True)
                    vw_lbl = font_vw_label.render(f"VIEWERS ({total_votes})", True, (0, 200, 220))
                    screen.blit(vw_lbl, vw_lbl.get_rect(center=(vbox_x + vbox_w // 2, vbox_y + int(vbox_h * 0.22))))
                    font_vote_big = pygame.font.SysFont("Arial", int(SCREEN_H * 0.022), bold=True)
                    buy_txt = font_vote_big.render(f"BUY: {buy_count}", True, (38, 200, 154))
                    sell_txt = font_vote_big.render(f"SELL: {sell_count}", True, (239, 83, 80))
                    screen.blit(buy_txt, buy_txt.get_rect(center=(vbox_x + int(vbox_w * 0.28), vbox_y + int(vbox_h * 0.65))))
                    screen.blit(sell_txt, sell_txt.get_rect(center=(vbox_x + int(vbox_w * 0.72), vbox_y + int(vbox_h * 0.65))))
                    pygame.draw.line(screen, (0, 100, 130), (vbox_x + vbox_w // 2, vbox_y + int(vbox_h * 0.40)), (vbox_x + vbox_w // 2, vbox_y + int(vbox_h * 0.85)), 1)
            elif viewer_trade_active is not None:
                # Viewers operando - mostrar cuadrito
                info_x = int(SCREEN_W * 0.05)
                info_y = int(SCREEN_H * 0.03)
                if viewer_votes:
                    buy_count = sum(1 for v in viewer_votes if v["vote"] == "BUY")
                    sell_count = sum(1 for v in viewer_votes if v["vote"] == "SELL")
                    vote_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.018), bold=True)
                    vbox_w = int(SCREEN_W * 0.20)
                    vbox_h = int(SCREEN_H * 0.05)
                    vote_bg = pygame.Surface((vbox_w, vbox_h), pygame.SRCALPHA)
                    vote_bg.fill((10, 10, 20, 210))
                    screen.blit(vote_bg, (info_x, info_y))
                    pygame.draw.rect(screen, (0, 150, 180), (info_x, info_y, vbox_w, vbox_h), 1, border_radius=3)
                    vw_txt = vote_font.render("VIEWERS", True, (0, 200, 220))
                    screen.blit(vw_txt, (info_x + 5, info_y + 3))
                    buy_txt = vote_font.render(f"BUY: {buy_count}", True, (38, 166, 154))
                    sell_txt = vote_font.render(f"SELL: {sell_count}", True, (239, 83, 80))
                    screen.blit(buy_txt, (info_x + 5, info_y + int(SCREEN_H * 0.025)))
                    screen.blit(sell_txt, (info_x + int(SCREEN_W * 0.10), info_y + int(SCREEN_H * 0.025)))
            # --- DIBUJAR TP/SL EN EL GRAFICO ---
            # Trade del streamer (EXTREMO)
            if active_trade is not None:
                tp_y = center_y - int((active_trade["tp"] - view_center_price) * vertical_zoom)
                sl_y = center_y - int((active_trade["sl"] - view_center_price) * vertical_zoom)
                entry_y = center_y - int((active_trade["entry"] - view_center_price) * vertical_zoom)
                entry_vis = active_trade["entry_index"] - visible_start_global
                if entry_vis < 0:
                    line_start_x = 0
                else:
                    line_start_x = int(start_x + (entry_vis * spacing)) + (candle_width // 2)
                last_candle_x = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
                label_offset = max(int(3 * spacing), 80)
                label_x = last_candle_x + label_offset
                line_end_x = label_x
                rect_width = line_end_x - line_start_x
                if rect_width > 0:
                    tp_surface = pygame.Surface((rect_width, abs(tp_y - entry_y)), pygame.SRCALPHA)
                    tp_surface.fill((38, 166, 154, 40))
                    tp_top = min(tp_y, entry_y)
                    screen.blit(tp_surface, (line_start_x, tp_top))
                    sl_surface = pygame.Surface((rect_width, abs(sl_y - entry_y)), pygame.SRCALPHA)
                    sl_surface.fill((239, 83, 80, 40))
                    sl_top = min(sl_y, entry_y)
                    screen.blit(sl_surface, (line_start_x, sl_top))
                for x in range(line_start_x, line_end_x, 12):
                    pygame.draw.line(screen, (255, 255, 255), (x, entry_y), (x + 6, entry_y), 1)
                pygame.draw.line(screen, (38, 166, 154), (line_start_x, tp_y), (line_end_x, tp_y), 1)
                pygame.draw.line(screen, (239, 83, 80), (line_start_x, sl_y), (line_end_x, sl_y), 1)
                # Label según quién opera - debajo SL (compra) o encima SL (venta)
                if active_trade["type"] == "BUY":
                    # Compra: label debajo del SL
                    label_text = "LEAN FX - VIEWERS" if viewer_votes_display else "LEAN FX"
                    lf_label = font_trade.render(label_text, True, (255, 200, 0))
                    screen.blit(lf_label, (line_start_x, sl_y + 5))
                else:
                    # Venta: label encima del SL
                    label_text = "LEAN FX - VIEWERS" if viewer_votes_display else "LEAN FX"
                    lf_label = font_trade.render(label_text, True, (255, 200, 0))
                    screen.blit(lf_label, (line_start_x, sl_y - 18))
            elif viewer_trade_active is not None:
                tp_y = center_y - int((viewer_trade_active["tp"] - view_center_price) * vertical_zoom)
                sl_y = center_y - int((viewer_trade_active["sl"] - view_center_price) * vertical_zoom)
                entry_y = center_y - int((viewer_trade_active["entry"] - view_center_price) * vertical_zoom)
                entry_vis = viewer_trade_active["entry_index"] - visible_start_global
                if entry_vis < 0:
                    line_start_x = 0
                else:
                    line_start_x = int(start_x + (entry_vis * spacing)) + (candle_width // 2)
                last_candle_x = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
                label_offset = max(int(3 * spacing), 80)
                label_x = last_candle_x + label_offset
                line_end_x = label_x
                rect_width = line_end_x - line_start_x
                if rect_width > 0:
                    tp_surface = pygame.Surface((rect_width, abs(tp_y - entry_y)), pygame.SRCALPHA)
                    tp_surface.fill((38, 166, 154, 35))
                    tp_top = min(tp_y, entry_y)
                    screen.blit(tp_surface, (line_start_x, tp_top))
                    sl_surface = pygame.Surface((rect_width, abs(sl_y - entry_y)), pygame.SRCALPHA)
                    sl_surface.fill((239, 83, 80, 35))
                    sl_top = min(sl_y, entry_y)
                    screen.blit(sl_surface, (line_start_x, sl_top))
                for x in range(line_start_x, line_end_x, 12):
                    pygame.draw.line(screen, (200, 200, 200), (x, entry_y), (x + 4, entry_y), 1)
                pygame.draw.line(screen, (38, 166, 154), (line_start_x, tp_y), (line_end_x, tp_y), 1)
                pygame.draw.line(screen, (239, 83, 80), (line_start_x, sl_y), (line_end_x, sl_y), 1)
                # Label "VIEWERS" debajo SL (compra) o encima SL (venta)
                if viewer_trade_active["type"] == "BUY":
                    v_label = font_trade.render("VIEWERS", True, (0, 200, 220))
                    screen.blit(v_label, (line_start_x, sl_y + 5))
                else:
                    v_label = font_trade.render("VIEWERS", True, (0, 200, 220))
                    screen.blit(v_label, (line_start_x, sl_y - 18))
            # (Contador de viewers ya está integrado en el panel de arriba)
        # --- INDICADOR RECONEXIÓN TIKTOK ---
        if tiktok_chat.is_reconnecting():
            font_recon = pygame.font.SysFont("Arial", int(SCREEN_H * 0.014), bold=True)
            dots = "." * (1 + (current_time // 500) % 3)
            recon_txt = font_recon.render(f"RECONECTANDO{dots}", True, (255, 200, 0))
            screen.blit(recon_txt, (int(SCREEN_W * 0.02), int(SCREEN_H * 0.96)))
        # --- STREAK INDICATOR ---
        if streak_display and current_time - streak_display["start_time"] < STREAK_DISPLAY_DURATION:
            s_name = streak_display["name"]
            s_count = streak_display["streak"]
            s_elapsed = current_time - streak_display["start_time"]
            s_alpha = max(0.4, 1.0 - (s_elapsed / STREAK_DISPLAY_DURATION) * 0.6)
            # Notificación grande abajo centrada
            font_streak = pygame.font.SysFont("Arial", int(SCREEN_H * 0.030), bold=True)
            streak_txt = font_streak.render(f"{s_name} lleva {s_count} wins seguidos!", True, (255, 220, 50))
            # Cargar imagen fuego (cache)
            if not hasattr(pygame, '_fire_img_loaded'):
                pygame._fire_img_loaded = True
                fire_path = os.path.join(BASE_DIR, "assets", "fire.png")
                if os.path.exists(fire_path):
                    pygame._fire_img = pygame.image.load(fire_path).convert_alpha()
                    fire_size = int(SCREEN_H * 0.035)
                    pygame._fire_img = pygame.transform.smoothscale(pygame._fire_img, (fire_size, fire_size))
                else:
                    pygame._fire_img = None
            fire_img = pygame._fire_img
            fire_w = fire_img.get_width() if fire_img else 0
            streak_w = streak_txt.get_width() + fire_w * 2 + 50
            streak_h = streak_txt.get_height() + 20
            s_x = SCREEN_W // 2 - streak_w // 2
            s_y = int(SCREEN_H * 0.88)
            # Fondo con gradiente dorado
            streak_bg = pygame.Surface((streak_w, streak_h), pygame.SRCALPHA)
            for row in range(streak_h):
                a = int(200 * s_alpha * (0.8 + 0.2 * (row / streak_h)))
                pygame.draw.line(streak_bg, (40, 25, 0, a), (0, row), (streak_w, row))
            screen.blit(streak_bg, (s_x, s_y))
            # Borde dorado pulsante
            pulse = int(220 + 35 * math.sin(current_time / 150.0))
            pygame.draw.rect(screen, (pulse, int(pulse * 0.75), 0), (s_x, s_y, streak_w, streak_h), 2, border_radius=6)
            # Glow exterior
            glow_s = pygame.Surface((streak_w + 8, streak_h + 8), pygame.SRCALPHA)
            glow_s.fill((255, 180, 0, int(25 * s_alpha)))
            screen.blit(glow_s, (s_x - 4, s_y - 4))
            # Fuego izquierdo + texto + fuego derecho
            content_x = s_x + 15
            content_y = s_y + (streak_h - streak_txt.get_height()) // 2
            if fire_img:
                screen.blit(fire_img, (content_x, s_y + (streak_h - fire_w) // 2))
                content_x += fire_w + 8
            screen.blit(streak_txt, (content_x, content_y))
            if fire_img:
                screen.blit(fire_img, (content_x + streak_txt.get_width() + 8, s_y + (streak_h - fire_w) // 2))
        elif streak_display and current_time - streak_display["start_time"] >= STREAK_DISPLAY_DURATION:
            streak_display = None
        # --- FLASH AL GANAR/PERDER ---
        if flash_active:
            flash_elapsed = current_time - flash_start_time
            if flash_elapsed >= FLASH_DURATION:
                flash_active = False
            else:
                # Fade out (opacidad disminuye)
                alpha = max(0, 180 - int(180 * (flash_elapsed / FLASH_DURATION)))
                # Flash de pantalla completa
                flash_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                flash_surface.fill((flash_color[0], flash_color[1], flash_color[2], alpha // 3))
                screen.blit(flash_surface, (0, 0))
                # Texto grande en el centro
                font_flash = pygame.font.SysFont("Arial", int(SCREEN_H * 0.08), bold=True)
                flash_txt = font_flash.render(flash_text, True, (flash_color[0], flash_color[1], flash_color[2]))
                flash_txt.set_alpha(alpha)
                flash_rect = flash_txt.get_rect(center=(int(SCREEN_W * 0.50), int(SCREEN_H * 0.45)))
                screen.blit(flash_txt, flash_rect)
        pygame.display.flip()

    # Parar música al salir del game loop (volver al menú)
    if sound_game_music is not None:
        sound_game_music.stop()
    if music_playing:
        pygame.mixer.music.stop()
        music_playing = False

pygame.quit()
