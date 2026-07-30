"""
LEAN FX GAME - Ventana del TOP 5 / RANKING (V2, arquitectura multi-ventana)

Proceso pygame independiente, capturable como fuente de OBS separada del
gráfico principal (main.py) y del panel streamer (window_streamer.py).

No maneja audio ni conexión a TikTok. Solo lee database.py periódicamente.

--- Nota sobre la calibración de posiciones ---
En V1, el panel TOP 5 (imagen panel_top5.png) se dibujaba dentro de la
pantalla completa (1920x1080), y el usuario calibró la posición de cada
nombre/W/L/WIN% con 20 clicks, guardados como FRACCIONES DE LA PANTALLA
COMPLETA (ej: nombre de la fila 1 en x=1690/1920, y=343/1080).

Ahora esta ventana ES el panel (no hay pantalla completa alrededor), así
que para no perder ni un pixel de esa calibración, se reconstruye la
geometría original: se calcula dónde estaría el panel dentro de una
pantalla virtual de 1920x1080 (igual que en V1), y luego cada posición se
convierte a coordenadas LOCALES de esta ventana restando el offset del
panel. El resultado visual es idéntico al que tenías en V1, solo que ahora
vive en su propia ventana.

Si el usuario reemplaza panel_top5.png por su nuevo diseño (mencionado
como pendiente), lo único que hay que recalibrar son las fracciones de
CARD_POSITIONS más abajo - el resto del mecanismo no cambia.
"""
import os
import sys
import pygame

from shared_paths import find_asset
from avatar_utils import get_viewer_avatar
from database import get_top_players

REFRESH_INTERVAL_MS = 2000
HIGHLIGHT_DURATION_MS = 2500

# --- Geometría virtual (idéntica a la pantalla 1920x1080 de V1) ---
VIRTUAL_W, VIRTUAL_H = 1920, 1080
PANEL_H = int(VIRTUAL_H * 0.75)          # 810 - igual que en V1
PANEL_Y = int(VIRTUAL_H * 0.20)          # 216 - igual que en V1

# Posiciones calibradas por el usuario en V1 (fracciones de pantalla 1920x1080)
CARD_POSITIONS = [
    {"name": (1690/1920, 343/1080), "w": (1546/1920, 423/1080), "l": (1689/1920, 423/1080), "wr": (1828/1920, 423/1080)},
    {"name": (1690/1920, 484/1080), "w": (1546/1920, 555/1080), "l": (1688/1920, 555/1080), "wr": (1828/1920, 555/1080)},
    {"name": (1690/1920, 618/1080), "w": (1548/1920, 687/1080), "l": (1689/1920, 687/1080), "wr": (1831/1920, 687/1080)},
    {"name": (1690/1920, 751/1080), "w": (1552/1920, 824/1080), "l": (1692/1920, 824/1080), "wr": (1832/1920, 824/1080)},
    {"name": (1690/1920, 885/1080), "w": (1556/1920, 952/1080), "l": (1691/1920, 952/1080), "wr": (1829/1920, 952/1080)},
]
FALLBACK_ASPECT = 0.62  # ancho/alto por si no existe panel_top5.png todavía

pygame.init()

# --- Cargar panel e imagen para calcular ancho real (define el tamaño de ventana) ---
panel_path = find_asset("panel_top5.png", "panel_top5.jpg")
panel_img_raw = None
if panel_path:
    panel_img_raw = pygame.image.load(panel_path).convert_alpha()
    PANEL_W = int(PANEL_H * (panel_img_raw.get_width() / panel_img_raw.get_height()))
else:
    PANEL_W = int(PANEL_H * FALLBACK_ASPECT)

# Offset del panel dentro de la pantalla virtual (igual fórmula que V1)
PANEL_X = VIRTUAL_W - PANEL_W + 50

WINDOW_W = PANEL_W
WINDOW_H = PANEL_H


def local_pos(frac_x, frac_y):
    """Convierte una fracción de pantalla-completa (V1) a coordenadas locales de esta ventana."""
    px = frac_x * VIRTUAL_W - PANEL_X
    py = frac_y * VIRTUAL_H - PANEL_Y
    return int(px), int(py)


# --- Posicionar la ventana (arriba a la derecha, debajo/al lado del panel streamer) ---
_info = pygame.display.Info()
_desktop_w, _desktop_h = _info.current_w, _info.current_h
_pos_x = max(0, _desktop_w - WINDOW_W - 20)
_pos_y = 280  # debajo de window_streamer.py (que ocupa los primeros ~240px + margen)
os.environ['SDL_VIDEO_WINDOW_POS'] = f"{_pos_x},{_pos_y}"

screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.NOFRAME)
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
    panel_img = pygame.transform.smoothscale(panel_img_raw, (WINDOW_W, WINDOW_H))


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

        font_name_top5 = pygame.font.SysFont("Arial", max(14, int(VIRTUAL_H * 0.022)), bold=True)
        font_stat_top5 = pygame.font.SysFont("Arial", max(12, int(VIRTUAL_H * 0.020)), bold=True)
        font_bal_top5 = pygame.font.SysFont("Arial", max(11, int(VIRTUAL_H * 0.016)), bold=True)
        font_arrow = pygame.font.SysFont("Arial", int(VIRTUAL_H * 0.018), bold=True)

        for i, viewer in enumerate(top_viewers):
            if i >= len(CARD_POSITIONS):
                break
            pos = CARD_POSITIONS[i]
            viewer_name = viewer["name"]

            # --- Efecto de cambio de posición (flechita +/-) ---
            highlight_info = top5_highlights.get(viewer_name)
            if highlight_info:
                h_elapsed = current_time - highlight_info["start_time"]
                if h_elapsed > HIGHLIGHT_DURATION_MS:
                    del top5_highlights[viewer_name]
                    highlight_info = None
            if highlight_info:
                h_elapsed = current_time - highlight_info["start_time"]
                h_alpha = max(0, 1.0 - (h_elapsed / HIGHLIGHT_DURATION_MS))
                nx0, ny0 = local_pos(*pos["name"])
                arrow_x = nx0 + 55
                if highlight_info["type"] == "up":
                    arrow_color = (0, int(255 * h_alpha), 0)
                    arrow_txt = font_arrow.render("+", True, arrow_color)
                else:
                    arrow_color = (int(255 * h_alpha), 0, 0)
                    arrow_txt = font_arrow.render("-", True, arrow_color)
                screen.blit(arrow_txt, arrow_txt.get_rect(center=(arrow_x, ny0)))

            # --- Nombre + avatar circulito ---
            nx, ny = local_pos(*pos["name"])
            v_avatar = get_viewer_avatar(viewer_name, 26)
            avatar_x = nx - 75
            if v_avatar is not None:
                screen.blit(v_avatar, (avatar_x, ny - v_avatar.get_height() // 2 + 2))
            max_name_w = int(WINDOW_W * 0.32)
            name_font_size = int(VIRTUAL_H * 0.022)
            font_name_dyn = pygame.font.SysFont("Arial", name_font_size, bold=True)
            n_txt = font_name_dyn.render(viewer_name, True, (255, 255, 255))
            while n_txt.get_width() > max_name_w and name_font_size > 10:
                name_font_size -= 1
                font_name_dyn = pygame.font.SysFont("Arial", name_font_size, bold=True)
                n_txt = font_name_dyn.render(viewer_name, True, (255, 255, 255))
            n_rect = n_txt.get_rect(center=(nx + 5, ny - 2))
            screen.blit(n_txt, n_rect)

            # --- W ---
            w_val = viewer.get("wins", 0)
            wx, wy = local_pos(*pos["w"])
            if w_val > 0:
                w_txt = font_stat_top5.render(str(w_val), True, (38, 166, 154))
            else:
                w_txt = font_stat_top5.render("-", True, (100, 100, 120))
            screen.blit(w_txt, w_txt.get_rect(center=(wx, wy)))

            # --- L ---
            l_val = viewer.get("losses", 0)
            lx, ly = local_pos(*pos["l"])
            if l_val > 0:
                l_txt = font_stat_top5.render(str(l_val), True, (239, 83, 80))
            else:
                l_txt = font_stat_top5.render("-", True, (100, 100, 120))
            screen.blit(l_txt, l_txt.get_rect(center=(lx, ly)))

            # --- WIN% ---
            total = w_val + l_val
            wrx, wry = local_pos(*pos["wr"])
            if total > 0:
                wr_val = int((w_val / total * 100))
                wr_txt = font_stat_top5.render(f"{wr_val}%", True, (0, 220, 255))
            else:
                wr_txt = font_stat_top5.render("-", True, (100, 100, 120))
            screen.blit(wr_txt, wr_txt.get_rect(center=(wrx, wry)))

            # --- Balance FXP (a la derecha del nombre) ---
            bal_val = viewer.get("balance", 10000)
            bal_color = (0, 200, 220) if bal_val >= 10000 else (200, 100, 100)
            bal_txt = font_bal_top5.render(f"{int(bal_val)} FXP", True, bal_color)
            screen.blit(bal_txt, (nx + 90, ny - bal_txt.get_height() // 2))
    else:
        # --- Fallback sin imagen: lista simple pero prolija ---
        pygame.draw.rect(screen, (0, 120, 150), (0, 0, WINDOW_W, WINDOW_H), 2)
        title_font = pygame.font.SysFont("Arial", 20, bold=True)
        title_txt = title_font.render("TOP 5 TRADERS", True, (0, 220, 255))
        screen.blit(title_txt, (15, 12))
        row_font = pygame.font.SysFont("Arial", 15, bold=True)
        row_h = max(30, (WINDOW_H - 60) // 5)
        for i, viewer in enumerate(top_viewers[:5]):
            ry = 50 + i * row_h
            v_avatar = get_viewer_avatar(viewer["name"], 24)
            tx = 15
            if v_avatar is not None:
                screen.blit(v_avatar, (tx, ry))
                tx += 32
            w_val, l_val = viewer.get("wins", 0), viewer.get("losses", 0)
            total = w_val + l_val
            wr = int((w_val / total * 100)) if total > 0 else 0
            line = f"#{i+1} {viewer['name']}  {w_val}W/{l_val}L  {wr}%  {int(viewer.get('balance', 10000))} FXP"
            row_txt = row_font.render(line, True, (220, 220, 230))
            screen.blit(row_txt, (tx, ry + 4))
        avviso = pygame.font.SysFont("Arial", 11, bold=True).render("(panel_top5.png no encontrado)", True, (100, 60, 60))
        screen.blit(avviso, (10, WINDOW_H - 18))

    pygame.display.flip()

pygame.quit()
sys.exit(0)
