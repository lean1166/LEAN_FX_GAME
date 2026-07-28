import sys
import os
import random
import math
import pygame
from database import (init_db, get_top_players, get_streamer_stats, 
                      update_player_balance, add_trade_history, 
                      check_monthly_reset, get_config, create_player,
                      get_all_players_ranked)

try:
    pygame.init()
    pygame.mixer.init()
    # Detectar resolución de pantalla automáticamente
    display_info = pygame.display.Info()
    SCREEN_W = display_info.current_w
    SCREEN_H = display_info.current_h
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.NOFRAME)
    pygame.display.set_caption("LEAN FX LIVE")
except Exception as e:
    print("[ERROR GRAFICO]:", e)
    sys.exit(1)

# --- CARGAR SONIDOS ---
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sound")

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

def play_sound(sound):
    if sound is not None and game_started:
        sound.play()

game_started = False  # Se activa al presionar INICIAR

def trade_win(amount):
    """Llamar cuando se gana un trade. Suma al balance y reproduce WIN.mp3"""
    global fxp_balance, wins
    fxp_balance += amount
    wins += 1
    play_sound(sound_win)
    update_player_balance("LEAN FX", fxp_balance, win=True)
    add_trade_history("LEAN FX", "BUY", "WIN", amount)

def trade_loss(amount):
    """Llamar cuando se pierde un trade. Resta del balance y reproduce LOSS.mp3"""
    global fxp_balance, losses
    fxp_balance -= amount
    losses += 1
    play_sound(sound_loss)
    update_player_balance("LEAN FX", fxp_balance, loss=True)
    add_trade_history("LEAN FX", "SELL", "LOSS", -amount)

pygame.font.init()
font_price = pygame.font.SysFont("Arial", 16, bold=True)
font_hud_title = pygame.font.SysFont("Arial", 18, bold=True)
font_hud_val = pygame.font.SysFont("Arial", 22, bold=True)
font_bos = pygame.font.SysFont("Arial", 16, bold=True)
font_ob = pygame.font.SysFont("Consolas", 13, bold=True)

# --- CARGAR AVATAR ---
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "profile")
avatar_img = None
# Buscar cualquier imagen en la carpeta profile
if os.path.exists(PROFILE_DIR):
    for f in os.listdir(PROFILE_DIR):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            avatar_img = pygame.image.load(os.path.join(PROFILE_DIR, f)).convert_alpha()
            avatar_img = pygame.transform.smoothscale(avatar_img, (200, 200))
            break
if avatar_img is None:
    print(f"[AVISO] Avatar no encontrado en: {PROFILE_DIR}")

# --- TOP 5 VIEWERS (desde base de datos) ---
font_top = pygame.font.SysFont("Arial", 14, bold=True)
# Verificar reset mensual
check_monthly_reset()
# Crear jugadores de prueba si la DB está vacía
db_top = get_top_players(10)
# Solo crear jugadores si la DB está vacía
if len(db_top) == 0:
    test_players = ["crypto_wolf", "trader_mike", "fx_queen", "bull_master", "sniper_pro",
                    "gold_trader", "scalp_king", "pip_hunter", "chart_ninja", "forex_ace"]
    for p in test_players:
        create_player(p)
    # Todos empiezan iguales: 10000 FXP, 0 operaciones

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
# --- SISTEMA DE ANIMACIÓN TOP 5 (detectar cambios de posición) ---
top5_prev_order = [v["name"] for v in top_viewers]  # Orden anterior
top5_highlights = {}  # {"nombre": {"type": "up"/"down", "start_time": ms}}
TOP5_HIGHLIGHT_DURATION = 2500  # 2.5 segundos de animación
top5_last_refresh = 0
TOP5_REFRESH_INTERVAL = 3000  # Refrescar cada 3 segundos

def refresh_top5_with_tracking(current_time):
    """Refresca top_viewers y detecta cambios de posición"""
    global top_viewers, top5_prev_order, top5_highlights
    new_viewers = load_top_viewers()
    new_order = [v["name"] for v in new_viewers]
    # Detectar quién subió y quién bajó
    someone_moved_up = False
    for name in new_order:
        if name in top5_prev_order:
            old_pos = top5_prev_order.index(name)
            new_pos = new_order.index(name)
            if new_pos < old_pos:
                top5_highlights[name] = {"type": "up", "start_time": current_time}
                someone_moved_up = True
            elif new_pos > old_pos:
                top5_highlights[name] = {"type": "down", "start_time": current_time}
        else:
            top5_highlights[name] = {"type": "up", "start_time": current_time}
            someone_moved_up = True
    if someone_moved_up and sound_levelup is not None and game_started:
        sound_levelup.play()
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
trend_length = random.randint(8, 15)
trend_count = 0
trend_strength = random.uniform(4, 10)  # Fuerza del movimiento
for _ in range(180):
    trend_count += 1
    if trend_count >= trend_length:
        trend_dir *= -1
        trend_count = 0
        is_impulse = not is_impulse
        if is_impulse:
            # Impulso: 8-15 velas, puede ser fuerte o moderado
            trend_length = random.randint(8, 15)
            trend_strength = random.uniform(4, 12)
        else:
            # Retroceso: variado, a veces suave (más velas, menos fuerza) a veces fuerte (pocas velas, mucha fuerza)
            if random.random() < 0.4:
                # Retroceso fuerte y rápido
                trend_length = random.randint(4, 8)
                trend_strength = random.uniform(6, 11)
            else:
                # Retroceso suave y largo
                trend_length = random.randint(8, 14)
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
SL_BUFFER = 2.0  # Pips de respiro para el SL (reducido 30%)
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
VIEWER_BOTS_ENABLED = True  # Poner False para desactivar
VIEWER_BOT_INTERVAL = 8000  # (ya no se usa, operan en zona)
viewer_bot_last_time = 0
# --- SISTEMA DE VOTOS DE VIEWERS ---
viewer_votes = []  # Lista de {"name": str, "vote": "BUY"/"SELL"} votos pendientes
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
            if active_ob and dec["index"] == active_ob["index"]:
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
            if active_ob and dec["index"] == active_ob["index"]:
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
                if active_ob and dec["index"] == active_ob["index"]:
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
                if active_ob and dec["index"] == active_ob["index"]:
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
menu_bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "menu_bg.png")
if not os.path.exists(menu_bg_path):
    menu_bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "menu_bg.jpg")
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
    btn_ranking = pygame.Rect(int(SCREEN_W * (686/1366)) - btn_w // 2, int(SCREEN_H * (476/768)) - btn_h // 2, btn_w, btn_h)
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
                elif btn_ranking.collidepoint(mx, my):
                    menu_click_btn = "ranking"
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
                if sound_game_music is not None:
                    sound_game_music.set_volume(0.3)
                    sound_game_music.play(loops=-1)
            elif menu_click_btn == "ranking":
                # Pantalla de RANKING MEJORADA
                in_ranking = True
                ranking_scroll = 0
                ranking_enter_time = pygame.time.get_ticks()
                # Partículas del ranking
                rank_particles = []
                for _ in range(25):
                    rank_particles.append({
                        "x": random.randint(0, SCREEN_W),
                        "y": random.randint(0, SCREEN_H),
                        "speed": random.uniform(0.2, 0.8),
                        "size": random.randint(1, 3),
                        "alpha": random.randint(40, 120),
                    })
                while in_ranking:
                    clock.tick(60)
                    current_time = pygame.time.get_ticks()
                    time_in_ranking = current_time - ranking_enter_time
                    screen.fill((8, 12, 20))
                    # --- PARTICULAS DE FONDO ---
                    for p in rank_particles:
                        p["y"] -= p["speed"]
                        if p["y"] < -5:
                            p["y"] = SCREEN_H + 5
                            p["x"] = random.randint(0, SCREEN_W)
                        ps = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
                        pygame.draw.circle(ps, (0, 180, 220, p["alpha"]), (p["size"], p["size"]), p["size"])
                        screen.blit(ps, (int(p["x"]), int(p["y"])))
                    # --- TITULO con sombra/glow ---
                    font_rank_title = pygame.font.SysFont("Arial", int(SCREEN_H * 0.055), bold=True)
                    # Sombra
                    title_shadow = font_rank_title.render("RANKING GENERAL", True, (0, 80, 100))
                    screen.blit(title_shadow, title_shadow.get_rect(center=(SCREEN_W // 2 + 2, int(SCREEN_H * 0.06) + 2)))
                    # Texto principal
                    rank_title = font_rank_title.render("RANKING GENERAL", True, (0, 220, 255))
                    screen.blit(rank_title, rank_title.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.06))))
                    # Total jugadores arriba derecha
                    all_players = get_all_players_ranked()
                    total_txt = font_top.render(f"{len(all_players)} jugadores activos", True, (0, 180, 200))
                    screen.blit(total_txt, (int(SCREEN_W * 0.80), int(SCREEN_H * 0.04)))
                    # --- INDICADOR EN VIVO (puntito verde pulsante) ---
                    live_x = int(SCREEN_W * 0.03)
                    live_y = int(SCREEN_H * 0.04)
                    live_pulse = int(6 + 3 * math.sin(current_time / 300.0))
                    live_alpha = int(180 + 75 * math.sin(current_time / 300.0))
                    # Glow del punto
                    live_glow = pygame.Surface((live_pulse * 4, live_pulse * 4), pygame.SRCALPHA)
                    pygame.draw.circle(live_glow, (0, 255, 80, 40), (live_pulse * 2, live_pulse * 2), live_pulse * 2)
                    screen.blit(live_glow, (live_x - live_pulse * 2, live_y - live_pulse * 2))
                    # Punto principal
                    pygame.draw.circle(screen, (0, min(255, live_alpha + 50), 80), (live_x, live_y), live_pulse)
                    # Texto "EN VIVO"
                    font_live = pygame.font.SysFont("Arial", int(SCREEN_H * 0.015), bold=True)
                    live_txt = font_live.render("EN VIVO", True, (0, 220, 100))
                    screen.blit(live_txt, (live_x + 12, live_y - live_txt.get_height() // 2))
                    # --- PANEL STREAMER MEJORADO ---
                    streamer_now = get_streamer_stats()
                    st_total = streamer_now["wins"] + streamer_now["losses"]
                    st_wr = int((streamer_now["wins"] / st_total * 100)) if st_total > 0 else 0
                    st_panel_w = int(SCREEN_W * 0.55)
                    st_panel_h = int(SCREEN_H * 0.08)
                    st_bg_x = SCREEN_W // 2 - st_panel_w // 2
                    st_bg_y = int(SCREEN_H * 0.10)
                    # Fondo con gradiente sutil
                    st_bg = pygame.Surface((st_panel_w, st_panel_h), pygame.SRCALPHA)
                    for row in range(st_panel_h):
                        alpha = int(100 + 40 * (row / st_panel_h))
                        pygame.draw.line(st_bg, (0, 30, 50, alpha), (0, row), (st_panel_w, row))
                    screen.blit(st_bg, (st_bg_x, st_bg_y))
                    # Borde glow pulsante
                    glow_alpha = int(180 + 60 * math.sin(current_time / 500.0))
                    glow_color = (0, min(255, glow_alpha), 220)
                    pygame.draw.rect(screen, glow_color, (st_bg_x, st_bg_y, st_panel_w, st_panel_h), 2, border_radius=4)
                    # Avatar grande
                    if avatar_img is not None:
                        av_size = int(st_panel_h * 0.75)
                        av_small = pygame.transform.smoothscale(avatar_img, (av_size, av_size))
                        screen.blit(av_small, (st_bg_x + 12, st_bg_y + (st_panel_h - av_size) // 2))
                        info_offset = av_size + 25
                    else:
                        info_offset = 15
                    # Nombre streamer
                    font_st_name = pygame.font.SysFont("Arial", int(SCREEN_H * 0.022), bold=True)
                    st_name = font_st_name.render("LEAN FX", True, (0, 220, 255))
                    screen.blit(st_name, (st_bg_x + info_offset, st_bg_y + int(st_panel_h * 0.15)))
                    # Stats en una línea + PROFIT
                    font_st_info = pygame.font.SysFont("Arial", int(SCREEN_H * 0.016), bold=True)
                    st_profit_pct = ((streamer_now['balance'] - 10000) / 10000) * 100
                    st_profit_str = f"+{st_profit_pct:.1f}%" if st_profit_pct >= 0 else f"{st_profit_pct:.1f}%"
                    st_info = font_st_info.render(f"Balance: {int(streamer_now['balance'])} FXP  |  {st_profit_str}  |  W:{streamer_now['wins']}  L:{streamer_now['losses']}  |  WR: {st_wr}%", True, (180, 200, 210))
                    screen.blit(st_info, (st_bg_x + info_offset, st_bg_y + int(st_panel_h * 0.55)))
                    # --- LINEA SEPARADORA con gradiente ---
                    sep_y = int(SCREEN_H * 0.20)
                    sep_surface = pygame.Surface((int(SCREEN_W * 0.90), 2), pygame.SRCALPHA)
                    for sx in range(int(SCREEN_W * 0.90)):
                        dist = abs(sx - int(SCREEN_W * 0.45)) / (SCREEN_W * 0.45)
                        alpha = int(150 * (1 - dist))
                        pygame.draw.line(sep_surface, (0, 180, 220, alpha), (sx, 0), (sx, 1))
                    screen.blit(sep_surface, (int(SCREEN_W * 0.05), sep_y))
                    # Headers
                    headers = ["#", "JUGADOR", "BALANCE (FXP)", "PROFIT", "W", "L", "WIN RATE"]
                    hx_positions = [0.05, 0.10, 0.30, 0.42, 0.52, 0.59, 0.67]
                    font_header = pygame.font.SysFont("Arial", int(SCREEN_H * 0.016), bold=True)
                    header_y = int(SCREEN_H * 0.22)
                    for i, h in enumerate(headers):
                        h_txt = font_header.render(h, True, (120, 160, 180))
                        screen.blit(h_txt, (int(SCREEN_W * hx_positions[i]), header_y))
                    # Underline debajo de headers
                    underline_y = header_y + int(SCREEN_H * 0.022)
                    underline_surf = pygame.Surface((int(SCREEN_W * 0.92), 1), pygame.SRCALPHA)
                    for ux in range(int(SCREEN_W * 0.92)):
                        dist = abs(ux - int(SCREEN_W * 0.46)) / (SCREEN_W * 0.46)
                        alpha = int(100 * (1 - dist))
                        pygame.draw.line(underline_surf, (0, 150, 180, alpha), (ux, 0), (ux, 0))
                    screen.blit(underline_surf, (int(SCREEN_W * 0.04), underline_y))
                    # --- BARRA LATERAL DECORATIVA CYAN con glow ---
                    bar_deco_x = int(SCREEN_W * 0.035)
                    bar_deco_y1 = int(SCREEN_H * 0.25)
                    bar_deco_y2 = int(SCREEN_H * 0.93)
                    # Glow (barra ancha semitransparente)
                    glow_bar = pygame.Surface((8, bar_deco_y2 - bar_deco_y1), pygame.SRCALPHA)
                    glow_bar.fill((0, 180, 220, 25))
                    screen.blit(glow_bar, (bar_deco_x - 3, bar_deco_y1))
                    # Barra fina principal
                    pygame.draw.line(screen, (0, 180, 220, 180), (bar_deco_x, bar_deco_y1), (bar_deco_x, bar_deco_y2), 2)
                    # --- DIBUJAR FILAS (mejoradas v2) ---
                    row_h = int(SCREEN_H * 0.052)
                    visible_rows = int(SCREEN_H * 0.65) // row_h
                    start_y = int(SCREEN_H * 0.26)
                    font_row_name = pygame.font.SysFont("Arial", int(SCREEN_H * 0.019), bold=True)
                    font_row_stat = pygame.font.SysFont("Arial", int(SCREEN_H * 0.017), bold=True)
                    for idx in range(min(visible_rows, len(all_players) - ranking_scroll)):
                        p_idx = idx + ranking_scroll
                        if p_idx >= len(all_players):
                            break
                        p = all_players[p_idx]
                        # Animación cascada: cada fila aparece con delay
                        row_delay = idx * 80
                        row_alpha_factor = min(1.0, max(0.0, (time_in_ranking - row_delay) / 300.0))
                        if row_alpha_factor <= 0:
                            continue
                        ry = start_y + (idx * row_h)
                        # Slide desde la derecha
                        slide_offset = int((1.0 - row_alpha_factor) * 60)
                        row_x_base = int(SCREEN_W * 0.045) + slide_offset
                        row_width = int(SCREEN_W * 0.92)
                        # Fondo de fila
                        row_bg = pygame.Surface((row_width, row_h - 3), pygame.SRCALPHA)
                        # Degradado de opacidad: filas más abajo se ven más tenues
                        fade_factor = max(0.4, 1.0 - (p_idx * 0.06)) if p_idx >= 3 else 1.0
                        if p_idx == 0:
                            for ry_line in range(row_h - 3):
                                g_alpha = int(row_alpha_factor * (70 + 40 * (ry_line / (row_h - 3))))
                                pygame.draw.line(row_bg, (60, 50, 0, g_alpha), (0, ry_line), (row_width, ry_line))
                        elif p_idx == 1:
                            row_bg.fill((30, 30, 40, int(row_alpha_factor * 100)))
                        elif p_idx == 2:
                            row_bg.fill((35, 25, 15, int(row_alpha_factor * 90)))
                        elif idx % 2 == 0:
                            row_bg.fill((18, 22, 35, int(row_alpha_factor * 100 * fade_factor)))
                        else:
                            row_bg.fill((12, 15, 25, int(row_alpha_factor * 70 * fade_factor)))
                        screen.blit(row_bg, (row_x_base, ry))
                        # --- HIGHLIGHT #1: borde dorado completo + brillo ---
                        if p_idx == 0:
                            # Borde dorado completo alrededor de la fila
                            gold_pulse = int(200 + 55 * math.sin(current_time / 400.0))
                            pygame.draw.rect(screen, (gold_pulse, int(gold_pulse * 0.84), 0), (row_x_base, ry, row_width, row_h - 3), 2, border_radius=3)
                            # Glow exterior
                            glow_s = pygame.Surface((row_width + 6, row_h + 1), pygame.SRCALPHA)
                            glow_s.fill((255, 215, 0, 15))
                            screen.blit(glow_s, (row_x_base - 3, ry - 2))
                        elif p_idx == 1:
                            pygame.draw.rect(screen, (192, 192, 192), (row_x_base, ry, 4, row_h - 3))
                        elif p_idx == 2:
                            pygame.draw.rect(screen, (205, 127, 50), (row_x_base, ry, 4, row_h - 3))
                        # --- MEDALLA: circulo dorado para #1, numeros para el resto ---
                        medal_cx = int(SCREEN_W * hx_positions[0]) + slide_offset + 12
                        medal_cy = ry + (row_h - 3) // 2
                        if p_idx == 0:
                            # Circulo dorado con "1" adentro
                            pygame.draw.circle(screen, (255, 215, 0), (medal_cx, medal_cy), int(SCREEN_H * 0.014))
                            pygame.draw.circle(screen, (200, 160, 0), (medal_cx, medal_cy), int(SCREEN_H * 0.014), 2)
                            one_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.016), bold=True)
                            one_txt = one_font.render("1", True, (40, 20, 0))
                            screen.blit(one_txt, one_txt.get_rect(center=(medal_cx, medal_cy)))
                        elif p_idx == 1:
                            pygame.draw.circle(screen, (192, 192, 192), (medal_cx, medal_cy), int(SCREEN_H * 0.012))
                            two_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.015), bold=True)
                            two_txt = two_font.render("2", True, (30, 30, 30))
                            screen.blit(two_txt, two_txt.get_rect(center=(medal_cx, medal_cy)))
                        elif p_idx == 2:
                            pygame.draw.circle(screen, (205, 127, 50), (medal_cx, medal_cy), int(SCREEN_H * 0.012))
                            three_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.015), bold=True)
                            three_txt = three_font.render("3", True, (30, 15, 0))
                            screen.blit(three_txt, three_txt.get_rect(center=(medal_cx, medal_cy)))
                        else:
                            num_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.017), bold=True)
                            num_txt = num_font.render(str(p_idx + 1), True, (140, 140, 160))
                            screen.blit(num_txt, num_txt.get_rect(center=(medal_cx, medal_cy)))
                        # Nombre
                        if p_idx < 3:
                            name_color = (255, 255, 255)
                        else:
                            nc = int(200 * fade_factor)
                            name_color = (nc, nc, min(255, nc + 10))
                        name_txt = font_row_name.render(p["username"], True, name_color)
                        screen.blit(name_txt, (int(SCREEN_W * hx_positions[1]) + slide_offset, ry + (row_h - 3) // 2 - name_txt.get_height() // 2))
                        # Balance (gris para los que están en negativo)
                        if p['balance'] < 10000:
                            bal_color = (140, 140, 150)
                        elif p_idx < 3:
                            bal_color = (0, 220, 255)
                        else:
                            bal_color = (0, int(180 * fade_factor), int(200 * fade_factor))
                        bal_txt = font_row_name.render(f"{int(p['balance'])} FXP", True, bal_color)
                        screen.blit(bal_txt, (int(SCREEN_W * hx_positions[2]) + slide_offset, ry + (row_h - 3) // 2 - bal_txt.get_height() // 2))
                        # PROFIT (% desde 10,000 FXP iniciales)
                        profit_pct = ((p['balance'] - 10000) / 10000) * 100
                        if profit_pct >= 0:
                            profit_color = (38, 200, 154)
                            profit_str = f"+{profit_pct:.1f}%"
                        else:
                            profit_color = (239, 83, 80)
                            profit_str = f"{profit_pct:.1f}%"
                        profit_txt = font_row_stat.render(profit_str, True, profit_color)
                        screen.blit(profit_txt, (int(SCREEN_W * hx_positions[3]) + slide_offset, ry + (row_h - 3) // 2 - profit_txt.get_height() // 2))
                        # W
                        w_txt = font_row_stat.render(str(p["wins"]), True, (38, 166, 154))
                        screen.blit(w_txt, (int(SCREEN_W * hx_positions[4]) + slide_offset, ry + (row_h - 3) // 2 - w_txt.get_height() // 2))
                        # L
                        l_txt = font_row_stat.render(str(p["losses"]), True, (239, 83, 80))
                        screen.blit(l_txt, (int(SCREEN_W * hx_positions[5]) + slide_offset, ry + (row_h - 3) // 2 - l_txt.get_height() // 2))
                        # --- WIN RATE con barra gradiente + glow ---
                        total = p["wins"] + p["losses"]
                        wr = int((p["wins"] / total * 100)) if total > 0 else 0
                        wr_x = int(SCREEN_W * hx_positions[6]) + slide_offset
                        bar_w_wr = int(SCREEN_W * 0.14)
                        bar_h_wr = int(SCREEN_H * 0.013)
                        bar_y_wr = ry + (row_h - 3) // 2 - bar_h_wr // 2
                        pygame.draw.rect(screen, (25, 25, 35), (wr_x, bar_y_wr, bar_w_wr, bar_h_wr), border_radius=7)
                        fill_w = int(bar_w_wr * (wr / 100))
                        if fill_w > 0:
                            bar_surf = pygame.Surface((fill_w, bar_h_wr), pygame.SRCALPHA)
                            if wr >= 50:
                                c1 = (20, 120, 100)
                                c2 = (38, 220, 180)
                            else:
                                c1 = (180, 40, 40)
                                c2 = (255, 100, 100)
                            for bx in range(fill_w):
                                t = bx / max(fill_w - 1, 1)
                                r_c = int(c1[0] + (c2[0] - c1[0]) * t)
                                g_c = int(c1[1] + (c2[1] - c1[1]) * t)
                                b_c = int(c1[2] + (c2[2] - c1[2]) * t)
                                pygame.draw.line(bar_surf, (r_c, g_c, b_c, 220), (bx, 0), (bx, bar_h_wr))
                            screen.blit(bar_surf, (wr_x, bar_y_wr))
                            if p_idx < 3:
                                glow_surf = pygame.Surface((fill_w + 4, bar_h_wr + 4), pygame.SRCALPHA)
                                glow_surf.fill((c2[0], c2[1], c2[2], 30))
                                screen.blit(glow_surf, (wr_x - 2, bar_y_wr - 2))
                        pygame.draw.rect(screen, (50, 50, 60), (wr_x, bar_y_wr, bar_w_wr, bar_h_wr), 1, border_radius=7)
                        wr_txt = font_row_stat.render(f"{wr}%", True, (220, 220, 230))
                        screen.blit(wr_txt, (wr_x + bar_w_wr + 10, ry + (row_h - 3) // 2 - wr_txt.get_height() // 2))
                    # --- SCROLL INDICATOR (barrita fina a la derecha) ---
                    if len(all_players) > visible_rows:
                        scroll_track_x = int(SCREEN_W * 0.97)
                        scroll_track_y = start_y
                        scroll_track_h = int(SCREEN_H * 0.65)
                        # Track (fondo)
                        pygame.draw.line(screen, (30, 40, 50), (scroll_track_x, scroll_track_y), (scroll_track_x, scroll_track_y + scroll_track_h), 3)
                        # Thumb (posicion actual)
                        thumb_h = max(20, int(scroll_track_h * (visible_rows / len(all_players))))
                        thumb_y = scroll_track_y + int((scroll_track_h - thumb_h) * (ranking_scroll / max(1, len(all_players) - visible_rows)))
                        pygame.draw.line(screen, (0, 180, 220), (scroll_track_x, thumb_y), (scroll_track_x, thumb_y + thumb_h), 4)
                    # --- FOOTER mejorado (sutil, sin ESC para viewers) ---
                    from datetime import datetime
                    now = datetime.now()
                    if now.month == 12:
                        next_month = f"1 Enero {now.year + 1}"
                    else:
                        months = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                        next_month = f"1 {months[now.month + 1]} {now.year}"
                    font_footer = pygame.font.SysFont("Arial", int(SCREEN_H * 0.014))
                    reset_txt = font_footer.render(f"Reset mensual: {next_month}", True, (50, 70, 90))
                    screen.blit(reset_txt, reset_txt.get_rect(center=(SCREEN_W // 2, int(SCREEN_H * 0.96))))
                    pygame.display.flip()
                    for r_event in pygame.event.get():
                        if r_event.type == pygame.QUIT:
                            in_ranking = False
                            in_menu = False
                            app_running = False
                        elif r_event.type == pygame.KEYDOWN:
                            if r_event.key == pygame.K_ESCAPE:
                                in_ranking = False
                            elif r_event.key == pygame.K_DOWN:
                                if ranking_scroll < max(0, len(all_players) - visible_rows):
                                    ranking_scroll += 1
                            elif r_event.key == pygame.K_UP:
                                if ranking_scroll > 0:
                                    ranking_scroll -= 1
            elif menu_click_btn == "config":
                menu_selection = "config"
            menu_click_btn = None
        # Áreas de botones calibradas con clicks en 1366x768
        btn_w = int(SCREEN_W * 0.28)
        btn_h = int(SCREEN_H * 0.08)
        btn_iniciar = pygame.Rect(int(SCREEN_W * (681/1366)) - btn_w // 2, int(SCREEN_H * (341/768)) - btn_h // 2, btn_w, btn_h)
        btn_ranking = pygame.Rect(int(SCREEN_W * (686/1366)) - btn_w // 2, int(SCREEN_H * (476/768)) - btn_h // 2, btn_w, btn_h)
        btn_config = pygame.Rect(int(SCREEN_W * (681/1366)) - btn_w // 2, int(SCREEN_H * (607/768)) - btn_h // 2, btn_w, btn_h)
        # Dibujar efecto click (oscurecer + bajar)
        buttons = [("iniciar", btn_iniciar), ("ranking", btn_ranking), ("config", btn_config)]
        for btn_name, btn_rect in buttons:
            if menu_click_btn == btn_name:
                # Efecto: oscurecer + bajar 3px
                dark_surface = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
                dark_surface.fill((0, 0, 0, 80))
                screen.blit(dark_surface, (btn_rect.x, btn_rect.y + 3))
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
                    pygame.event.clear()  # Limpiar cola para que ESC no se repita
                    pygame.time.wait(100)  # Pequeña espera
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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                print(f"[CLICK] x={mx}, y={my}")
        # --- LOGICA DEL TIMER ---
        if zone_frozen:
            elapsed = current_time - zone_timer_start
            if elapsed >= TIMER_DURATION:
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
                zone_frozen = False
                zone_detected = None
                trade_decided = False
                last_tick_second = -1
        # --- MOVER PRECIO (solo si NO está congelado) ---
        if not zone_frozen:
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
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (38, 166, 154)
                            flash_text = f"WIN +{int(TP_MULTIPLIER)}%"
                        elif current_price <= active_trade["sl"]:
                            trade_loss(TRADE_RISK)
                            trade_history.append({"type": "BUY", "result": "LOSS", "pnl": -TRADE_RISK})
                            active_trade = None
                            bot_bias_active = False
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (239, 83, 80)
                            flash_text = "LOSS -1%"
                    elif active_trade["type"] == "SELL":
                        if current_price <= active_trade["tp"]:
                            trade_win(TRADE_RISK * TP_MULTIPLIER)
                            trade_history.append({"type": "SELL", "result": "WIN", "pnl": TRADE_RISK * TP_MULTIPLIER})
                            active_trade = None
                            bot_bias_active = False
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (38, 166, 154)
                            flash_text = f"WIN +{int(TP_MULTIPLIER)}%"
                        elif current_price >= active_trade["sl"]:
                            trade_loss(TRADE_RISK)
                            trade_history.append({"type": "SELL", "result": "LOSS", "pnl": -TRADE_RISK})
                            active_trade = None
                            bot_bias_active = False
                            flash_active = True
                            flash_start_time = current_time
                            flash_color = (239, 83, 80)
                            flash_text = "LOSS -1%"
                # --- DETECTAR SI PRECIO LLEGA A UNA ZONA (solo 1 vez por zona) ---
                if active_trade is None and not zone_frozen:
                    price_now = current_candle["close"]
                    # Verificar Order Block activo
                    if active_ob is not None:
                        zone_id = f"ob_{active_ob['index']}"
                        if zone_id not in zones_mitigated and active_ob["low"] <= price_now <= active_ob["high"]:
                            zone_frozen = True
                            zone_timer_start = current_time
                            zone_detected = {"high": active_ob["high"], "low": active_ob["low"], "type": active_ob["type"], "source": "EXTREMO"}
                            zones_mitigated.add(zone_id)
                    # Verificar Decisional
                    if not zone_frozen and active_decisional is not None:
                        zone_id = f"dec_{active_decisional['index']}"
                        if zone_id not in zones_mitigated and active_decisional["low"] <= price_now <= active_decisional["high"]:
                            zone_frozen = True
                            zone_timer_start = current_time
                            zone_detected = {"high": active_decisional["high"], "low": active_decisional["low"], "type": active_decisional["type"], "source": "DECISIONAL"}
                            zones_mitigated.add(zone_id)
                    # FVG NO se opera por ahora (solo se dibuja)
                    # if not zone_frozen and active_fvg is not None:
                    #     zone_id = f"fvg_{active_fvg['index']}"
                    #     if zone_id not in zones_mitigated and active_fvg["low"] <= price_now <= active_fvg["high"]:
                    #         zone_frozen = True
                    #         zone_timer_start = current_time
                    #         zone_detected = {"high": active_fvg["high"], "low": active_fvg["low"], "type": active_fvg["type"]}
                    #         zones_mitigated.add(zone_id)
        # --- BOTS VIEWERS (votan durante la ventana, se resuelven con TP/SL) ---
        if VIEWER_BOTS_ENABLED and game_started and zone_frozen and not getattr(pygame, '_viewers_voted_this_zone', False):
            pygame._viewers_voted_this_zone = True
            num_voters = random.randint(2, 4)
            all_viewer_names = [v["name"] for v in load_top_viewers()]
            if all_viewer_names:
                voters = random.sample(all_viewer_names, min(num_voters, len(all_viewer_names)))
                viewer_votes = []
                for chosen in voters:
                    vote = random.choice(["BUY", "SELL"])
                    viewer_votes.append({"name": chosen, "vote": vote})
                # Crear trade de viewers si no hay uno activo
                if zone_detected is not None and viewer_trade_active is None:
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
        if not zone_frozen:
            pygame._viewers_voted_this_zone = False
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
                    p = get_top_players(10)
                    for pl in p:
                        if pl["username"] == v["name"]:
                            if (vt_won and v["vote"] == correct_dir) or (vt_lost and v["vote"] != correct_dir):
                                gain = int(TRADE_RISK * TP_MULTIPLIER)
                                update_player_balance(v["name"], pl["balance"] + gain, win=True)
                            else:
                                update_player_balance(v["name"], max(8000, pl["balance"] - TRADE_RISK), loss=True)
                            break
                viewer_trade_active = None
                viewer_votes = []
        if not zone_frozen and current_time - last_candle_time >= CANDLE_DURATION:
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
        needed_count = max(50, min(needed_count, 150))
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
            hud_x = int(SCREEN_W * 0.86)
            hud_y = int(SCREEN_H * 0.02)
            # --- PANEL STREAMER (imagen PNG + texto dinámico) ---
            streamer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "panel_streamer.png")
            if not hasattr(pygame, '_streamer_loaded'):
                pygame._streamer_loaded = True
                if os.path.exists(streamer_path):
                    pygame._streamer_img = pygame.image.load(streamer_path).convert_alpha()
                else:
                    pygame._streamer_img = None
                    print(f"[AVISO] Panel streamer no encontrado")
            streamer_img = pygame._streamer_img
            if streamer_img is not None:
                # Escalar panel (proporción 1774x887, ancho ~25% de pantalla)
                sp_w = int(SCREEN_W * 0.25)
                sp_h = int(sp_w * (887 / 1774))
                sp_scaled = pygame.transform.smoothscale(streamer_img, (sp_w, sp_h))
                sp_x = SCREEN_W - sp_w - 5
                sp_y = 5
                screen.blit(sp_scaled, (sp_x, sp_y))
                # Avatar dentro del círculo
                if avatar_img is not None:
                    av_size = int(sp_h * 0.35)
                    av_scaled = pygame.transform.smoothscale(avatar_img, (av_size, av_size))
                    # Centro del círculo calibrado: (1502, 107) en 1920x1080
                    av_cx = int(SCREEN_W * (1502/1920))
                    av_cy = int(SCREEN_H * (107/1080))
                    screen.blit(av_scaled, (av_cx - av_size // 2, av_cy - av_size // 2))
                # Nombre (barra superior) - bajado un poco para centrar
                name_x = int(SCREEN_W * (1719/1920))
                name_y = int(SCREEN_H * (75/1080))
                n_txt = font_hud_title.render(STREAMER_NAME, True, (0, 220, 255))
                n_rect = n_txt.get_rect(center=(name_x, name_y))
                screen.blit(n_txt, n_rect)
                # 4 cajitas calibradas con cursor en 1920x1080
                total_trades = wins + losses
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                # Calcular racha
                streak = 0
                for t in reversed(trade_history):
                    if t["result"] == "WIN":
                        streak += 1
                    else:
                        break
                stats_values = [
                    f"{int(fxp_balance)}",
                    f"{win_rate:.0f}%",
                    f"{streak}",
                    f"{total_trades}",
                ]
                stats_colors = [(0, 220, 255), (38, 166, 154), (255, 180, 0), (200, 200, 200)]
                stats_positions_x = [1604/1920, 1686/1920, 1766/1920, 1849/1920]
                stats_y_pct = 142/1080
                font_stat_s = pygame.font.SysFont("Arial", max(8, int(sp_h * 0.08)), bold=True)
                for i, val in enumerate(stats_values):
                    sx = int(SCREEN_W * stats_positions_x[i])
                    sy = int(SCREEN_H * stats_y_pct)
                    s_txt = font_stat_s.render(val, True, stats_colors[i])
                    s_rect = s_txt.get_rect(center=(sx, sy))
                    screen.blit(s_txt, s_rect)
            # --- TOP 5 VIEWERS (imagen PNG + texto calibrado con cursor) ---
            # Refrescar TOP 5 periódicamente y detectar cambios
            if current_time - top5_last_refresh > TOP5_REFRESH_INTERVAL:
                refresh_top5_with_tracking(current_time)
                top5_last_refresh = current_time
            top_panel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "panel_top5.png")
            if not os.path.exists(top_panel_path):
                top_panel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "panel_top5.jpg")
            if not hasattr(pygame, '_top5_panel_loaded2'):
                pygame._top5_panel_loaded2 = True
                if os.path.exists(top_panel_path):
                    pygame._top5_img2 = pygame.image.load(top_panel_path).convert_alpha()
                else:
                    pygame._top5_img2 = None
                    print(f"[AVISO] Panel TOP 5 no encontrado")
            top5_img = pygame._top5_img2
            if top5_img is not None:
                # Escalar
                panel_h = int(SCREEN_H * 0.75)
                panel_w = int(panel_h * (top5_img.get_width() / top5_img.get_height()))
                top5_scaled = pygame.transform.smoothscale(top5_img, (panel_w, panel_h))
                panel_x = SCREEN_W - panel_w + 50
                panel_y = int(SCREEN_H * 0.20)
                screen.blit(top5_scaled, (panel_x, panel_y))
                # Posiciones calibradas con 20 clicks en 1920x1080
                # Convertidas a porcentajes para que funcione en cualquier resolución
                card_positions = [
                    {"name": (1690/1920, 343/1080), "w": (1546/1920, 423/1080), "l": (1689/1920, 423/1080), "wr": (1828/1920, 423/1080)},
                    {"name": (1690/1920, 484/1080), "w": (1546/1920, 555/1080), "l": (1688/1920, 555/1080), "wr": (1828/1920, 555/1080)},
                    {"name": (1690/1920, 618/1080), "w": (1548/1920, 687/1080), "l": (1689/1920, 687/1080), "wr": (1831/1920, 687/1080)},
                    {"name": (1690/1920, 751/1080), "w": (1552/1920, 824/1080), "l": (1692/1920, 824/1080), "wr": (1832/1920, 824/1080)},
                    {"name": (1690/1920, 885/1080), "w": (1556/1920, 952/1080), "l": (1691/1920, 952/1080), "wr": (1829/1920, 952/1080)},
                ]
                font_name_top5 = pygame.font.SysFont("Arial", max(14, int(SCREEN_H * 0.022)), bold=True)
                font_stat_top5 = pygame.font.SysFont("Arial", max(12, int(SCREEN_H * 0.020)), bold=True)
                for i, viewer in enumerate(top_viewers):
                    pos = card_positions[i]
                    # --- EFECTO DE CAMBIO DE POSICIÓN ---
                    viewer_name = viewer['name']
                    highlight_info = top5_highlights.get(viewer_name)
                    if highlight_info:
                        h_elapsed = current_time - highlight_info["start_time"]
                        if h_elapsed > TOP5_HIGHLIGHT_DURATION:
                            del top5_highlights[viewer_name]
                            highlight_info = None
                    # Dibujar efecto si hay highlight activo
                    if highlight_info:
                        h_elapsed = current_time - highlight_info["start_time"]
                        h_alpha = max(0, 1.0 - (h_elapsed / TOP5_HIGHLIGHT_DURATION))
                        # Posición Y del nombre (centro de la tarjeta)
                        card_cy = int(SCREEN_H * pos["name"][1])
                        if highlight_info["type"] == "up":
                            # Flechita ↑ verde al lado del nombre
                            arrow_x = int(SCREEN_W * pos["name"][0]) + 55
                            arrow_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.018), bold=True)
                            arrow_color = (0, int(255 * h_alpha), 0)
                            arrow_txt = arrow_font.render("+", True, arrow_color)
                            screen.blit(arrow_txt, arrow_txt.get_rect(center=(arrow_x, card_cy)))
                        elif highlight_info["type"] == "down":
                            # Flechita ↓ roja al lado del nombre
                            arrow_x = int(SCREEN_W * pos["name"][0]) + 55
                            arrow_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.018), bold=True)
                            arrow_color = (int(255 * h_alpha), 0, 0)
                            arrow_txt = arrow_font.render("-", True, arrow_color)
                            screen.blit(arrow_txt, arrow_txt.get_rect(center=(arrow_x, card_cy)))
                    # Nombre
                    nx = int(SCREEN_W * pos["name"][0])
                    ny = int(SCREEN_H * pos["name"][1])
                    n_txt = font_name_top5.render(viewer['name'], True, (255, 255, 255))
                    n_rect = n_txt.get_rect(center=(nx, ny))
                    screen.blit(n_txt, n_rect)
                    # W
                    w_val = viewer.get('wins', 0)
                    if w_val > 0:
                        w_txt = font_stat_top5.render(str(w_val), True, (38, 166, 154))
                    else:
                        w_txt = font_stat_top5.render("-", True, (100, 100, 120))
                    w_rect = w_txt.get_rect(center=(int(SCREEN_W * pos["w"][0]), int(SCREEN_H * pos["w"][1])))
                    screen.blit(w_txt, w_rect)
                    # L
                    l_val = viewer.get('losses', 0)
                    if l_val > 0:
                        l_txt = font_stat_top5.render(str(l_val), True, (239, 83, 80))
                    else:
                        l_txt = font_stat_top5.render("-", True, (100, 100, 120))
                    l_rect = l_txt.get_rect(center=(int(SCREEN_W * pos["l"][0]), int(SCREEN_H * pos["l"][1])))
                    screen.blit(l_txt, l_rect)
                    # WIN%
                    total = w_val + l_val
                    if total > 0:
                        wr_val = int((w_val / total * 100))
                        wr_txt = font_stat_top5.render(f"{wr_val}%", True, (0, 220, 255))
                    else:
                        wr_txt = font_stat_top5.render("-", True, (100, 100, 120))
                    wr_rect = wr_txt.get_rect(center=(int(SCREEN_W * pos["wr"][0]), int(SCREEN_H * pos["wr"][1])))
                    screen.blit(wr_txt, wr_rect)
            # --- PANEL VIEWERS (arriba centro, donde estaban los botones) ---
            btn_x = int(SCREEN_W * 0.35)
            btn_y = int(SCREEN_H * 0.03)
            if zone_frozen:
                # Timer activo - mostrar panel de votación
                elapsed = current_time - zone_timer_start
                remaining = max(0, TIMER_DURATION - elapsed)
                seconds_left = remaining / 1000.0
                # Tick-tock en los últimos 5 segundos
                current_second = int(seconds_left)
                if seconds_left <= 5.0 and current_second != last_tick_second and seconds_left > 0:
                    play_sound(sound_tick)
                    last_tick_second = current_second
                # Texto "ZONA DETECTADA"
                zone_label = font_btn.render("ZONA DETECTADA", True, (255, 255, 0))
                zone_rect = zone_label.get_rect(center=(int(SCREEN_W * 0.35), int(SCREEN_H * 0.03)))
                screen.blit(zone_label, zone_rect)
                # Timer
                timer_txt = font_timer.render(f"{seconds_left:.1f}s", True, (255, 255, 0))
                timer_rect = timer_txt.get_rect(center=(int(SCREEN_W * 0.35), int(SCREEN_H * 0.08)))
                screen.blit(timer_txt, timer_rect)
                # Barra de progreso del timer
                bar_w = int(SCREEN_W * 0.25)
                bar_h = 12
                bar_x = int(SCREEN_W * 0.35) - bar_w // 2
                bar_y = int(SCREEN_H * 0.12)
                progress = remaining / TIMER_DURATION
                pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
                if progress > 0.5:
                    bar_color = (0, 220, 255)
                elif progress > 0.25:
                    bar_color = (255, 220, 0)
                else:
                    bar_color = (255, 50, 50)
                fill_w = int(bar_w * progress)
                if fill_w > 0:
                    pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=6)
                pygame.draw.rect(screen, (100, 100, 100), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=6)
                # Cuadrito VIEWERS con votos (en la posición de los botones)
                if viewer_votes:
                    buy_count = sum(1 for v in viewer_votes if v["vote"] == "BUY")
                    sell_count = sum(1 for v in viewer_votes if v["vote"] == "SELL")
                    vote_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.018), bold=True)
                    vbox_x = int(SCREEN_W * 0.35) - int(SCREEN_W * 0.10)
                    vbox_y = int(SCREEN_H * 0.15)
                    vbox_w = int(SCREEN_W * 0.20)
                    vbox_h = int(SCREEN_H * 0.05)
                    vote_bg = pygame.Surface((vbox_w, vbox_h), pygame.SRCALPHA)
                    vote_bg.fill((10, 10, 20, 210))
                    screen.blit(vote_bg, (vbox_x, vbox_y))
                    pygame.draw.rect(screen, (0, 150, 180), (vbox_x, vbox_y, vbox_w, vbox_h), 1, border_radius=3)
                    vw_txt = vote_font.render("VIEWERS", True, (0, 200, 220))
                    screen.blit(vw_txt, (vbox_x + 5, vbox_y + 3))
                    buy_txt = vote_font.render(f"BUY: {buy_count}", True, (38, 166, 154))
                    sell_txt = vote_font.render(f"SELL: {sell_count}", True, (239, 83, 80))
                    screen.blit(buy_txt, (vbox_x + 5, vbox_y + int(SCREEN_H * 0.025)))
                    screen.blit(sell_txt, (vbox_x + int(SCREEN_W * 0.10), vbox_y + int(SCREEN_H * 0.025)))
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
                # Viewers también operan al mismo tiempo - mostrar su panel
                if viewer_votes:
                    buy_count = sum(1 for v in viewer_votes if v["vote"] == "BUY")
                    sell_count = sum(1 for v in viewer_votes if v["vote"] == "SELL")
                    vote_font = pygame.font.SysFont("Arial", int(SCREEN_H * 0.016), bold=True)
                    vbox_x = int(SCREEN_W * 0.05)
                    vbox_y = int(SCREEN_H * 0.12)
                    vbox_w = int(SCREEN_W * 0.16)
                    vbox_h = int(SCREEN_H * 0.045)
                    vote_bg = pygame.Surface((vbox_w, vbox_h), pygame.SRCALPHA)
                    vote_bg.fill((10, 10, 20, 200))
                    screen.blit(vote_bg, (vbox_x, vbox_y))
                    pygame.draw.rect(screen, (0, 150, 180), (vbox_x, vbox_y, vbox_w, vbox_h), 1, border_radius=3)
                    vw_txt = vote_font.render("VIEWERS", True, (0, 200, 220))
                    screen.blit(vw_txt, (vbox_x + 5, vbox_y + 2))
                    buy_txt = vote_font.render(f"BUY: {buy_count}", True, (38, 166, 154))
                    sell_txt = vote_font.render(f"SELL: {sell_count}", True, (239, 83, 80))
                    screen.blit(buy_txt, (vbox_x + 5, vbox_y + int(SCREEN_H * 0.022)))
                    screen.blit(sell_txt, (vbox_x + int(SCREEN_W * 0.08), vbox_y + int(SCREEN_H * 0.022)))
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
                # Label "LEAN FX" para distinguir del trade de viewers
                lf_label = font_trade.render("LEAN FX", True, (255, 200, 0))
                screen.blit(lf_label, (line_end_x + 5, entry_y - 8))
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
                # Label "VIEWERS" al lado
                v_label = font_trade.render("VIEWERS", True, (0, 200, 220))
                screen.blit(v_label, (line_end_x + 5, entry_y - 8))
            # (Contador de viewers ya está integrado en el panel de arriba)
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

pygame.quit()
