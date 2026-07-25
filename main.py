import sys
import os
import random
import pygame

try:
    pygame.init()
    pygame.mixer.init()
    # Detectar resolución de pantalla automáticamente
    display_info = pygame.display.Info()
    SCREEN_W = display_info.current_w
    SCREEN_H = display_info.current_h
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
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

def play_sound(sound):
    if sound is not None:
        sound.play()

def trade_win(amount):
    """Llamar cuando se gana un trade. Suma al balance y reproduce WIN.mp3"""
    global fxp_balance, wins
    fxp_balance += amount
    wins += 1
    play_sound(sound_win)

def trade_loss(amount):
    """Llamar cuando se pierde un trade. Resta del balance y reproduce LOSS.mp3"""
    global fxp_balance, losses
    fxp_balance -= amount
    losses += 1
    play_sound(sound_loss)

pygame.font.init()
font_price = pygame.font.SysFont("Arial", 16, bold=True)
font_hud_title = pygame.font.SysFont("Arial", 18, bold=True)
font_hud_val = pygame.font.SysFont("Arial", 22, bold=True)
font_bos = pygame.font.SysFont("Arial", 16, bold=True)
font_ob = pygame.font.SysFont("Consolas", 13, bold=True)
fxp_balance = 10000
wins = 0
losses = 0
candles = []
price = 1000
trend_dir = random.choice([-1, 1])
trend_length = random.randint(8, 16)
trend_count = 0
for _ in range(180):
    trend_count += 1
    if trend_count >= trend_length:
        trend_dir *= -1
        trend_length = random.randint(8, 16)
        trend_count = 0
    if random.random() < 0.75:
        body = random.uniform(3, 10) * trend_dir
    else:
        body = random.uniform(2, 6) * -trend_dir
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
TRADE_RISK = 100  # Siempre pierdes $100, sin importar el tamaño del SL
TP_MULTIPLIER = 3.0  # Risk:Reward 1:3
SL_BUFFER = 5.0  # Pips de respiro para el SL
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
    trend_length = random.randint(8, 16)
    trend_count = 0
    for _ in range(180):
        trend_count += 1
        if trend_count >= trend_length:
            trend_dir *= -1
            trend_length = random.randint(8, 16)
            trend_count = 0
        if random.random() < 0.75:
            body = random.uniform(3, 10) * trend_dir
        else:
            body = random.uniform(2, 6) * -trend_dir
        open_p = price
        close_p = open_p + body
        high_p = max(open_p, close_p) + random.uniform(0.5, 3)
        low_p = min(open_p, close_p) - random.uniform(0.5, 3)
        candles.append({"open": open_p, "close": close_p, "high": high_p, "low": low_p})
        price = close_p
    for i in range(1, len(candles)):
        process_new_candle(candles, i)

current_candle = {"open": candles[-1]["close"], "close": candles[-1]["close"], "high": candles[-1]["close"], "low": candles[-1]["close"]}

while running:
    clock.tick(60)
    current_time = pygame.time.get_ticks()
    screen.fill((30, 30, 30))
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Solo se puede clickear BUY/SELL durante el timer y si no hay trade activo
            if zone_frozen and not trade_decided and active_trade is None:
                hud_x_click = int(SCREEN_W * 0.86)
                hud_y_click = int(SCREEN_H * 0.06)
                buy_rect = pygame.Rect(hud_x_click, hud_y_click + 190, 120, 45)
                sell_rect = pygame.Rect(hud_x_click + 140, hud_y_click + 190, 120, 45)
                if buy_rect.collidepoint(mx, my):
                    entry_price = current_candle["close"]
                    sl_price = zone_detected["low"] - SL_BUFFER  # SL debajo de la zona + respiro
                    sl_distance = entry_price - sl_price
                    tp_distance = sl_distance * TP_MULTIPLIER
                    active_trade = {
                        "type": "BUY",
                        "entry": entry_price,
                        "sl": sl_price,
                        "tp": entry_price + tp_distance,
                        "entry_index": len(candles),
                    }
                    trade_decided = True
                    play_sound(sound_bos)
                elif sell_rect.collidepoint(mx, my):
                    entry_price = current_candle["close"]
                    sl_price = zone_detected["high"] + SL_BUFFER  # SL encima de la zona + respiro
                    sl_distance = sl_price - entry_price
                    tp_distance = sl_distance * TP_MULTIPLIER
                    active_trade = {
                        "type": "SELL",
                        "entry": entry_price,
                        "sl": sl_price,
                        "tp": entry_price - tp_distance,
                        "entry_index": len(candles),
                    }
                    trade_decided = True
                    play_sound(sound_bos)
    # --- LOGICA DEL TIMER ---
    if zone_frozen:
        elapsed = current_time - zone_timer_start
        if elapsed >= TIMER_DURATION:
            # Timer terminó, reanudar gráfico
            zone_frozen = False
            zone_detected = None
            trade_decided = False
    # --- MOVER PRECIO (solo si NO está congelado) ---
    if not zone_frozen:
        if current_time - last_tick_time >= TICK_DELAY:
            step_size = random.uniform(0.4, 1.8)
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
                    elif current_price <= active_trade["sl"]:
                        trade_loss(TRADE_RISK)
                        trade_history.append({"type": "BUY", "result": "LOSS", "pnl": -TRADE_RISK})
                        active_trade = None
                elif active_trade["type"] == "SELL":
                    if current_price <= active_trade["tp"]:
                        trade_win(TRADE_RISK * TP_MULTIPLIER)
                        trade_history.append({"type": "SELL", "result": "WIN", "pnl": TRADE_RISK * TP_MULTIPLIER})
                        active_trade = None
                    elif current_price >= active_trade["sl"]:
                        trade_loss(TRADE_RISK)
                        trade_history.append({"type": "SELL", "result": "LOSS", "pnl": -TRADE_RISK})
                        active_trade = None
            # --- DETECTAR SI PRECIO LLEGA A UNA ZONA ---
            if active_trade is None and not zone_frozen:
                price_now = current_candle["close"]
                # Verificar Order Block activo
                if active_ob is not None:
                    if active_ob["low"] <= price_now <= active_ob["high"]:
                        zone_frozen = True
                        zone_timer_start = current_time
                        zone_detected = {"high": active_ob["high"], "low": active_ob["low"], "type": active_ob["type"]}
                # Verificar Decisional
                if not zone_frozen and active_decisional is not None:
                    if active_decisional["low"] <= price_now <= active_decisional["high"]:
                        zone_frozen = True
                        zone_timer_start = current_time
                        zone_detected = {"high": active_decisional["high"], "low": active_decisional["low"], "type": active_decisional["type"]}
                # Verificar FVG
                if not zone_frozen and active_fvg is not None:
                    if active_fvg["low"] <= price_now <= active_fvg["high"]:
                        zone_frozen = True
                        zone_timer_start = current_time
                        zone_detected = {"high": active_fvg["high"], "low": active_fvg["low"], "type": active_fvg["type"]}
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
    needed_count = 100
    if prev_range_low_index is not None:
        distance = total_len - prev_range_low_index
        if distance > needed_count:
            needed_count = distance + 10
    if prev_range_high_index is not None:
        distance = total_len - prev_range_high_index
        if distance > needed_count:
            needed_count = distance + 10
    if range_phase == "rango_definido":
        if range_high_index is not None:
            distance = total_len - range_high_index
            if distance > needed_count:
                needed_count = distance + 10
        if range_low_index is not None:
            distance = total_len - range_low_index
            if distance > needed_count:
                needed_count = distance + 10
    needed_count = max(100, min(needed_count, 300))
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
        vertical_zoom = (SCREEN_H * 0.88) / price_range
        view_center_price = min_p + price_range / 2
        center_y = SCREEN_H // 2
        chart_start_x = 0
        chart_end_x = int(SCREEN_W * 0.75)
        # Velas ocupan hasta 70%
        available_width = int(SCREEN_W * 0.70) - chart_start_x
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
        hud_y = int(SCREEN_H * 0.06)
        screen.blit(font_hud_title.render("Balance:", True, (255, 255, 255)), (hud_x, hud_y))
        screen.blit(font_hud_val.render("$" + str(round(fxp_balance, 2)), True, (0, 191, 255)), (hud_x + 110, hud_y))
        screen.blit(font_hud_title.render("Wins:", True, (255, 255, 255)), (hud_x, hud_y + 50))
        screen.blit(font_hud_val.render(str(wins), True, (38, 166, 154)), (hud_x + 110, hud_y + 50))
        screen.blit(font_hud_title.render("Losses:", True, (255, 255, 255)), (hud_x, hud_y + 100))
        screen.blit(font_hud_val.render(str(losses), True, (239, 83, 80)), (hud_x + 110, hud_y + 100))
        # Win Rate
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        screen.blit(font_hud_title.render("Win Rate:", True, (255, 255, 255)), (hud_x, hud_y + 150))
        wr_color = (38, 166, 154) if win_rate >= 50 else (239, 83, 80)
        screen.blit(font_hud_val.render(f"{win_rate:.1f}%", True, wr_color), (hud_x + 110, hud_y + 150))
        # Botones BUY / SELL (solo durante el timer)
        buy_rect = pygame.Rect(hud_x, hud_y + 190, 120, 45)
        sell_rect = pygame.Rect(hud_x + 140, hud_y + 190, 120, 45)
        if zone_frozen and not trade_decided and active_trade is None:
            # Timer activo, mostrar botones
            pygame.draw.rect(screen, (38, 166, 154), buy_rect, border_radius=6)
            pygame.draw.rect(screen, (239, 83, 80), sell_rect, border_radius=6)
            buy_txt = font_btn.render("BUY", True, (255, 255, 255))
            sell_txt = font_btn.render("SELL", True, (255, 255, 255))
            screen.blit(buy_txt, buy_txt.get_rect(center=buy_rect.center))
            screen.blit(sell_txt, sell_txt.get_rect(center=sell_rect.center))
            # Mostrar TIMER grande en el centro del gráfico
            elapsed = current_time - zone_timer_start
            remaining = max(0, TIMER_DURATION - elapsed)
            seconds_left = remaining / 1000.0
            timer_txt = font_timer.render(f"{seconds_left:.1f}s", True, (255, 255, 0))
            timer_rect = timer_txt.get_rect(center=(int(SCREEN_W * 0.35), int(SCREEN_H * 0.10)))
            screen.blit(timer_txt, timer_rect)
            # Texto "ZONA DETECTADA"
            zone_label = font_btn.render("ZONA DETECTADA - DECIDE!", True, (255, 255, 0))
            zone_rect = zone_label.get_rect(center=(int(SCREEN_W * 0.35), int(SCREEN_H * 0.16)))
            screen.blit(zone_label, zone_rect)
        elif active_trade is not None:
            # Mostrar info del trade activo
            pygame.draw.rect(screen, (80, 80, 80), buy_rect, border_radius=6)
            pygame.draw.rect(screen, (80, 80, 80), sell_rect, border_radius=6)
            trade_txt = font_btn.render(f"{active_trade['type']} ACTIVO", True, (255, 255, 0))
            screen.blit(trade_txt, trade_txt.get_rect(center=(hud_x + 130, hud_y + 212)))
            # Mostrar Entry, TP, SL
            entry_txt = font_trade.render(f"Entry: {active_trade['entry']:.2f}", True, (255, 255, 255))
            tp_txt = font_trade.render(f"TP: {active_trade['tp']:.2f}", True, (38, 166, 154))
            sl_txt = font_trade.render(f"SL: {active_trade['sl']:.2f}", True, (239, 83, 80))
            screen.blit(entry_txt, (hud_x, hud_y + 250))
            screen.blit(tp_txt, (hud_x, hud_y + 270))
            screen.blit(sl_txt, (hud_x, hud_y + 290))
            # PnL flotante
            current_price = current_candle["close"]
            if active_trade["type"] == "BUY":
                pnl_points = current_price - active_trade["entry"]
            else:
                pnl_points = active_trade["entry"] - current_price
            pnl_color = (38, 166, 154) if pnl_points >= 0 else (239, 83, 80)
            pnl_txt = font_hud_val.render(f"PnL: {pnl_points:+.1f} pts", True, pnl_color)
            screen.blit(pnl_txt, (hud_x, hud_y + 315))
        # --- DIBUJAR TP/SL EN EL GRAFICO ---
        if active_trade is not None:
            tp_y = center_y - int((active_trade["tp"] - view_center_price) * vertical_zoom)
            sl_y = center_y - int((active_trade["sl"] - view_center_price) * vertical_zoom)
            entry_y = center_y - int((active_trade["entry"] - view_center_price) * vertical_zoom)
            # Calcular X de inicio desde la vela de entrada
            entry_vis = active_trade["entry_index"] - visible_start_global
            if entry_vis < 0:
                line_start_x = 0
            else:
                line_start_x = int(start_x + (entry_vis * spacing)) + (candle_width // 2)
            # Los labels van 3 velas adelante de la ultima vela (minimo 80px)
            last_candle_x = int(start_x + ((len(visible_candles) - 1) * spacing)) + candle_width
            label_offset = max(int(3 * spacing), 80)
            label_x = last_candle_x + label_offset
            # Las zonas van desde entrada hasta los labels
            line_end_x = label_x
            rect_width = line_end_x - line_start_x
            if rect_width > 0:
                # Zona TP (verde claro semi-transparente)
                tp_surface = pygame.Surface((rect_width, abs(tp_y - entry_y)), pygame.SRCALPHA)
                tp_surface.fill((38, 166, 154, 40))
                tp_top = min(tp_y, entry_y)
                screen.blit(tp_surface, (line_start_x, tp_top))
                # Zona SL (rojo/rosa claro semi-transparente)
                sl_surface = pygame.Surface((rect_width, abs(sl_y - entry_y)), pygame.SRCALPHA)
                sl_surface.fill((239, 83, 80, 40))
                sl_top = min(sl_y, entry_y)
                screen.blit(sl_surface, (line_start_x, sl_top))
            # Linea de entrada (blanca punteada)
            for x in range(line_start_x, line_end_x, 12):
                pygame.draw.line(screen, (255, 255, 255), (x, entry_y), (x + 6, entry_y), 1)
            # Linea TP (verde solida)
            pygame.draw.line(screen, (38, 166, 154), (line_start_x, tp_y), (line_end_x, tp_y), 1)
            # Linea SL (roja solida)
            pygame.draw.line(screen, (239, 83, 80), (line_start_x, sl_y), (line_end_x, sl_y), 1)
            # Labels con fondo siempre 5 velas adelante
            # Entry label
            entry_label = font_trade.render(f" {active_trade['entry']:.2f} ", True, (255, 255, 255))
            entry_bg = pygame.Rect(line_end_x + 3, entry_y - 9, entry_label.get_width(), entry_label.get_height())
            pygame.draw.rect(screen, (100, 100, 100), entry_bg)
            screen.blit(entry_label, entry_bg)
            # TP label
            tp_label = font_trade.render(f" {active_trade['tp']:.2f} ", True, (255, 255, 255))
            tp_bg = pygame.Rect(line_end_x + 3, tp_y - 9, tp_label.get_width(), tp_label.get_height())
            pygame.draw.rect(screen, (38, 166, 154), tp_bg)
            screen.blit(tp_label, tp_bg)
            # SL label
            sl_label = font_trade.render(f" {active_trade['sl']:.2f} ", True, (255, 255, 255))
            sl_bg = pygame.Rect(line_end_x + 3, sl_y - 9, sl_label.get_width(), sl_label.get_height())
            pygame.draw.rect(screen, (239, 83, 80), sl_bg)
            screen.blit(sl_label, sl_bg)
    pygame.display.flip()
pygame.quit()
