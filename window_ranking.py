"""
LEAN FX GAME - Ventana del TOP 5 / RANKING (V2, arquitectura multi-ventana)

Proceso pygame independiente, capturable como fuente de TikTok Studio / OBS
separada del gráfico principal (main.py) y del panel streamer (window_streamer.py).

No maneja audio ni conexión a TikTok. Solo lee database.py periódicamente.

--- Calibración de posiciones (30-31 julio 2026) ---
Ventana a 1280x720. Las posiciones de texto se calibraron con 25 clicks
directos sobre la imagen escalada a ese tamaño (nombre, balance, win,
loss, winrate x 5 filas). Nombre en cyan, LOSS y WINRATE alineados a la
misma altura que WIN de cada fila.
"""
import os
import sys
import pygame

from shared_paths import find_asset
from avatar_utils import get_viewer_avatar
from database import get_top_players

REFRESH_INTERVAL_MS = 2000
HIGHLIGHT_DURATION_MS = 2500

WINDOW_W, WINDOW_H = 1280, 720

# Posiciones calibradas directamente en 1280x720
CARD_POSITIONS = [
    {"name": (355, 186), "bal": (620, 186), "w": (791, 196), "l": (948, 199), "wr": (1093, 200)},
    {"name": (351, 292), "bal": (620, 291), "w": (791, 303), "l": (941, 300), "wr": (1088, 301)},
    {"name": (354, 398), "bal": (623, 396), "w": (792, 408), "l": (942, 407), "wr": (1094, 408)},
    {"name": (345, 502), "bal": (619, 500), "w": (785, 508), "l": (943, 509), "wr": (1091, 513)},
    {"name": (344, 606), "bal": (617, 607), "w": (787, 616), "l": (942, 619), "wr": (1093, 615)},
]

pygame.init()

panel_path = find_asset("panel_top5.png", "panel_top5.jpg")
panel_img_raw = None
if panel_path:
    panel_img_raw = pygame.image.load(panel_path)

os.environ['SDL_VIDEO_WINDOW_POS'] = "200,200"

screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
pygame.display.set_caption("LEAN FX - TOP 5 RANKING")

icon_path = find_asset("icon.png", "icon.ico")
if icon_path:
    try:
        pygame.display.set_icon(pygame.image.load(icon_path))
    except Exception:
        pass

pygame.font.init()

panel_img = None
if panel_img_raw is not None:
    panel_img = panel_img_raw.convert_alpha()
    if panel_img.get_size() != (WINDOW_W, WINDOW_H):
        panel_img = pygame.transform.smoothscale(panel_img, (WINDOW_W, WINDOW_H))

font_name = pygame.font.SysFont("Arial", 20, bold=True)
font_bal = pygame.font.SysFont("Arial", 18, bold=True)
font_stat = pygame.font.SysFont("Arial", 24, bold=True)
font_arrow = pygame.font.SysFont("Arial", 15, bold=True)


def load_top_viewers():
    players = get_top_players(5)
    return [{"name": p["username"], "balance": p["balance"], "wins": p["wins"], "losses": p["losses"]} for p in players]


clock = pygame.time.Clock()
last_refresh = -REFRESH_INTERVAL_MS
top_viewers = []
top5_prev_order = []
top5_highlights = {}

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
                arrow_x = nx + 80
                if highlight_info["type"] == "up":
                    arrow_txt = font_arrow.render("\u25B2", True, (0, int(255 * h_alpha), 0))
                else:
                    arrow_txt = font_arrow.render("\u25BC", True, (int(255 * h_alpha), 0, 0))
                screen.blit(arrow_txt, arrow_txt.get_rect(center=(arrow_x, ny)))

            nx, ny = pos["name"]
            v_avatar = get_viewer_avatar(viewer_name, 30)
            if v_avatar is not None:
                screen.blit(v_avatar, (nx - 45, ny - v_avatar.get_height() // 2))
            max_name_w = 200
            name_font_size = 20
            font_name_dyn = pygame.font.SysFont("Arial", name_font_size, bold=True)
            n_txt = font_name_dyn.render(viewer_name, True, (0, 230, 255))
            while n_txt.get_width() > max_name_w and name_font_size > 8:
                name_font_size -= 1
                font_name_dyn = pygame.font.SysFont("Arial", name_font_size, bold=True)
                n_txt = font_name_dyn.render(viewer_name, True, (0, 230, 255))
            screen.blit(n_txt, n_txt.get_rect(center=(nx + 75, ny)))

            bx, by = pos["bal"]
            bal_val = viewer.get("balance", 10000)
            bal_color = (0, 220, 255) if bal_val >= 10000 else (239, 100, 100)
            bal_txt = font_bal.render(f"{int(bal_val)} FXP", True, bal_color)
            screen.blit(bal_txt, bal_txt.get_rect(center=(bx, by)))

            wx, wy = pos["w"]
            w_val = viewer.get("wins", 0)
            w_txt = font_stat.render(str(w_val) if w_val > 0 else "-", True, (38, 166, 154) if w_val > 0 else (100, 100, 120))
            screen.blit(w_txt, w_txt.get_rect(center=(wx, wy)))

            lx, ly = pos["l"][0], pos["w"][1]
            l_val = viewer.get("losses", 0)
            l_txt = font_stat.render(str(l_val) if l_val > 0 else "-", True, (239, 83, 80) if l_val > 0 else (100, 100, 120))
            screen.blit(l_txt, l_txt.get_rect(center=(lx, ly)))

            wrx, wry = pos["wr"][0], pos["w"][1]
            total = w_val + l_val
            if total > 0:
                wr_txt = font_stat.render(f"{int(w_val/total*100)}%", True, (0, 220, 255))
            else:
                wr_txt = font_stat.render("-", True, (100, 100, 120))
            screen.blit(wr_txt, wr_txt.get_rect(center=(wrx, wry)))
    else:
        pygame.draw.rect(screen, (0, 120, 150), (0, 0, WINDOW_W, WINDOW_H), 2)
        font_fb = pygame.font.SysFont("Arial", 20, bold=True)
        screen.blit(font_fb.render("TOP 5 - panel_top5.png no encontrado", True, (200, 60, 60)), (20, 20))

    pygame.display.flip()

pygame.quit()
sys.exit(0)
