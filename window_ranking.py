"""
LEAN FX GAME - Ventana del TOP 5 / RANKING (V2, arquitectura multi-ventana)

Proceso pygame independiente, capturable como fuente de TikTok Studio / OBS
separada del gráfico principal (main.py) y del panel streamer (window_streamer.py).

No maneja audio ni conexión a TikTok. Solo lee database.py periódicamente.

--- Calibración de posiciones (30 julio 2026) ---
La imagen panel_top5.png es 1920x1080. La ventana se abre a ese tamaño.
Las posiciones de texto se calibraron con clicks directos sobre la imagen:
  - 25 clicks: 5 filas x 5 columnas (nombre, balance, win, loss, winrate)
"""
import os
import sys
import pygame

from shared_paths import find_asset
from avatar_utils import get_viewer_avatar
from database import get_top_players

REFRESH_INTERVAL_MS = 2000
HIGHLIGHT_DURATION_MS = 2500

# Tamaño de la ventana = tamaño de la imagen
WINDOW_W, WINDOW_H = 1920, 1080

# Posiciones calibradas por el usuario (clicks directos en 1920x1080)
# Cada fila: nombre_xy, balance_xy, win_xy, loss_xy, winrate_xy
CARD_POSITIONS = [
    {"name": (448, 249), "bal": (800, 244), "w": (1029, 256), "l": (1233, 255), "wr": (1425, 256)},
    {"name": (441, 380), "bal": (801, 378), "w": (1035, 390), "l": (1235, 389), "wr": (1422, 390)},
    {"name": (437, 516), "bal": (799, 516), "w": (1033, 528), "l": (1233, 530), "wr": (1424, 529)},
    {"name": (443, 654), "bal": (786, 654), "w": (1035, 668), "l": (1236, 666), "wr": (1439, 664)},
    {"name": (438, 794), "bal": (781, 791), "w": (1034, 803), "l": (1233, 805), "wr": (1428, 800)},
]

pygame.init()

# --- Cargar panel (sin convert_alpha: necesita ventana primero) ---
panel_path = find_asset("panel_top5.png", "panel_top5.jpg")
panel_img_raw = None
if panel_path:
    panel_img_raw = pygame.image.load(panel_path)

# --- Posicionar la ventana (esquina superior izquierda para que entre completa) ---
os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"

screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
pygame.display.set_caption("LEAN FX - TOP 5 RANKING")

icon_path = find_asset("icon.png", "icon.ico")
if icon_path:
    try:
        pygame.display.set_icon(pygame.image.load(icon_path))
    except Exception:
        pass

pygame.font.init()

# Ahora sí se puede convertir (ventana ya existe)
panel_img = None
if panel_img_raw is not None:
    panel_img = panel_img_raw.convert_alpha()
    # Escalar solo si no coincide (por si la imagen no es exactamente 1920x1080)
    if panel_img.get_size() != (WINDOW_W, WINDOW_H):
        panel_img = pygame.transform.smoothscale(panel_img, (WINDOW_W, WINDOW_H))

# Fuentes
font_name = pygame.font.SysFont("Arial", 28, bold=True)
font_bal = pygame.font.SysFont("Arial", 22, bold=True)
font_stat = pygame.font.SysFont("Arial", 24, bold=True)
font_arrow = pygame.font.SysFont("Arial", 22, bold=True)


def load_top_viewers():
    players = get_top_players(5)
    return [{
        "name": p["username"],
        "balance": p["balance"],
        "wins": p["wins"],
        "losses": p["losses"],
    } for p in players]


clock = pygame.time.Clock()
last_refresh = -REFRESH_INTERVAL_MS
top_viewers = []
top5_prev_order = []
top5_highlights = {}  # {"nombre": {"type": "up"/"down", "start_time": ms}}

running = True
while running:
    clock.tick(30)
    current_time = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    if current_time - last_refresh >= REFRESH_INTERVAL_MS:
        try:
            new_viewers = load_top_viewers()
            new_order = [v["name"] for v in new_viewers]
            for name in new_order:
                if name in top5_prev_order:
                    old_pos = top5_prev_order.index(name)
                    new_pos = new_order.index(name)
                    if new_pos < old_pos:
                        top5_highlights[name] = {"type": "up", "start_time": current_time}
                    elif new_pos > old_pos:
                        top5_highlights[name] = {"type": "down", "start_time": current_time}
                else:
                    top5_highlights[name] = {"type": "up", "start_time": current_time}
            top5_prev_order = new_order
            top_viewers = new_viewers
        except Exception as e:
            print(f"[window_ranking] Error leyendo DB: {e}")
        last_refresh = current_time

    screen.fill((10, 12, 20))

    if panel_img is not None:
        screen.blit(panel_img, (0, 0))

        for i, viewer in enumerate(top_viewers):
            if i >= len(CARD_POSITIONS):
                break
            pos = CARD_POSITIONS[i]
            viewer_name = viewer["name"]

            # --- Efecto de cambio de posición (flechita animada) ---
            highlight_info = top5_highlights.get(viewer_name)
            if highlight_info:
                h_elapsed = current_time - highlight_info["start_time"]
                if h_elapsed > HIGHLIGHT_DURATION_MS:
                    del top5_highlights[viewer_name]
                    highlight_info = None
            if highlight_info:
                h_elapsed = current_time - highlight_info["start_time"]
                h_alpha = max(0, 1.0 - (h_elapsed / HIGHLIGHT_DURATION_MS))
                nx, ny = pos["name"]
                arrow_x = nx + 120
                if highlight_info["type"] == "up":
                    arrow_color = (0, int(255 * h_alpha), 0)
                    arrow_txt = font_arrow.render("\u25B2", True, arrow_color)
                else:
                    arrow_color = (int(255 * h_alpha), 0, 0)
                    arrow_txt = font_arrow.render("\u25BC", True, arrow_color)
                screen.blit(arrow_txt, arrow_txt.get_rect(center=(arrow_x, ny)))

            # --- NOMBRE + avatar circulito ---
            nx, ny = pos["name"]
            v_avatar = get_viewer_avatar(viewer_name, 32)
            if v_avatar is not None:
                screen.blit(v_avatar, (nx - 90, ny - v_avatar.get_height() // 2))
            # Nombre con autoescalado si es muy largo
            max_name_w = 280
            name_font_size = 28
            font_name_dyn = pygame.font.SysFont("Arial", name_font_size, bold=True)
            n_txt = font_name_dyn.render(viewer_name, True, (255, 255, 255))
            while n_txt.get_width() > max_name_w and name_font_size > 12:
                name_font_size -= 1
                font_name_dyn = pygame.font.SysFont("Arial", name_font_size, bold=True)
                n_txt = font_name_dyn.render(viewer_name, True, (255, 255, 255))
            screen.blit(n_txt, n_txt.get_rect(center=(nx, ny)))

            # --- BALANCE ---
            bx, by = pos["bal"]
            bal_val = viewer.get("balance", 10000)
            if bal_val >= 10000:
                bal_color = (0, 220, 255)
            else:
                bal_color = (239, 100, 100)
            bal_txt = font_bal.render(f"{int(bal_val)} FXP", True, bal_color)
            screen.blit(bal_txt, bal_txt.get_rect(center=(bx, by)))

            # --- WIN ---
            wx, wy = pos["w"]
            w_val = viewer.get("wins", 0)
            if w_val > 0:
                w_txt = font_stat.render(str(w_val), True, (38, 166, 154))
            else:
                w_txt = font_stat.render("-", True, (100, 100, 120))
            screen.blit(w_txt, w_txt.get_rect(center=(wx, wy)))

            # --- LOSS ---
            lx, ly = pos["l"]
            l_val = viewer.get("losses", 0)
            if l_val > 0:
                l_txt = font_stat.render(str(l_val), True, (239, 83, 80))
            else:
                l_txt = font_stat.render("-", True, (100, 100, 120))
            screen.blit(l_txt, l_txt.get_rect(center=(lx, ly)))

            # --- WINRATE ---
            wrx, wry = pos["wr"]
            total = w_val + l_val
            if total > 0:
                wr_val = int((w_val / total * 100))
                wr_txt = font_stat.render(f"{wr_val}%", True, (0, 220, 255))
            else:
                wr_txt = font_stat.render("-", True, (100, 100, 120))
            screen.blit(wr_txt, wr_txt.get_rect(center=(wrx, wry)))

    else:
        # --- Fallback sin imagen ---
        pygame.draw.rect(screen, (0, 120, 150), (0, 0, WINDOW_W, WINDOW_H), 2)
        title_font = pygame.font.SysFont("Arial", 36, bold=True)
        title_txt = title_font.render("TOP 5 TRADERS", True, (0, 220, 255))
        screen.blit(title_txt, (30, 20))
        row_font = pygame.font.SysFont("Arial", 24, bold=True)
        row_h = max(50, (WINDOW_H - 120) // 5)
        for i, viewer in enumerate(top_viewers[:5]):
            ry = 80 + i * row_h
            v_avatar = get_viewer_avatar(viewer["name"], 30)
            tx = 30
            if v_avatar is not None:
                screen.blit(v_avatar, (tx, ry))
                tx += 40
            w_val, l_val = viewer.get("wins", 0), viewer.get("losses", 0)
            total = w_val + l_val
            wr = int((w_val / total * 100)) if total > 0 else 0
            line = f"#{i+1} {viewer['name']}  {int(viewer.get('balance', 10000))} FXP  {w_val}W/{l_val}L  {wr}%"
            row_txt = row_font.render(line, True, (220, 220, 230))
            screen.blit(row_txt, (tx, ry + 4))
        avviso = pygame.font.SysFont("Arial", 16, bold=True).render("(panel_top5.png no encontrado)", True, (100, 60, 60))
        screen.blit(avviso, (30, WINDOW_H - 40))

    pygame.display.flip()

pygame.quit()
sys.exit(0)
