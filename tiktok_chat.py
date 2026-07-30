"""
Módulo de conexión a TikTok Live Chat
Lee mensajes del chat en tiempo real y detecta votos BUY/SELL

Requisito: pip install TikTokLive
"""
import threading
import asyncio
import time
import os
import urllib.request

from shared_paths import AVATARS_DIR

def download_avatar(username, url):
    """Descarga avatar de TikTok y lo guarda localmente"""
    if not url:
        return
    filepath = os.path.join(AVATARS_DIR, f"{username}.jpg")
    if os.path.exists(filepath):
        return  # Ya lo tenemos
    try:
        urllib.request.urlretrieve(url, filepath)
        print(f"[AVATAR] Descargado: {username}")
    except Exception as e:
        print(f"[AVATAR] Error descargando {username}: {e}")

# Intentar importar TikTokLive
try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent
    TIKTOK_AVAILABLE = True
except ImportError:
    TIKTOK_AVAILABLE = False
    print("[AVISO] TikTokLive no instalado. Ejecutá: pip install TikTokLive")


class TikTokChatReader:
    """Lee el chat de TikTok Live en un hilo separado"""

    def __init__(self, username="lean.fx1"):
        self.username = username
        self.connected = False
        self.votes = []  # Lista de {"name": str, "vote": "BUY"/"SELL", "avatar_url": str}
        self.voting_open = False  # True cuando se puede votar (zona activa)
        self.voters_this_zone = set()  # Viewers que ya votaron en esta zona (cooldown)
        self.all_comments = []  # Todos los comentarios (para debug)
        self.thread = None
        self.loop = None
        self.client = None
        self.reconnect_attempts = 0
        self.max_reconnect = 999  # Reintentos infinitos
        self.reconnecting = False  # Indicador para mostrar en pantalla

    def start(self):
        """Iniciar la conexión en un hilo separado"""
        if not TIKTOK_AVAILABLE:
            print("[TIKTOK] Librería no disponible. Usando bots simulados.")
            return False
        self.thread = threading.Thread(target=self._run_async, daemon=True)
        self.thread.start()
        return True

    def _run_async(self):
        """Correr el loop asyncio en el hilo"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())

    async def _connect(self):
        """Conectar al live de TikTok"""
        while self.reconnect_attempts < self.max_reconnect:
            try:
                self.client = TikTokLiveClient(unique_id=self.username)

                @self.client.on(ConnectEvent)
                async def on_connect(event: ConnectEvent):
                    self.connected = True
                    self.reconnecting = False
                    self.reconnect_attempts = 0
                    print(f"[TIKTOK] Conectado al live de @{self.username}")

                @self.client.on(DisconnectEvent)
                async def on_disconnect(event: DisconnectEvent):
                    self.connected = False
                    print(f"[TIKTOK] Desconectado del live")

                @self.client.on(CommentEvent)
                async def on_comment(event: CommentEvent):
                    try:
                        username = event.user.nickname or str(event.user.id)
                        unique_id = str(event.user.id)
                        comment = event.comment.strip().upper()
                        avatar_url = ""
                        if hasattr(event.user, 'avatar_jpg') and event.user.avatar_jpg:
                            avatar_url = event.user.avatar_jpg
                        elif hasattr(event.user, 'avatar_url') and event.user.avatar_url:
                            avatar_url = event.user.avatar_url

                        # Guardar todos los comentarios (debug)
                        self.all_comments.append({
                            "name": username,
                            "unique_id": unique_id,
                            "comment": comment,
                            "avatar_url": avatar_url,
                            "time": time.time()
                        })
                        # Solo mantener últimos 50
                        if len(self.all_comments) > 50:
                            self.all_comments.pop(0)

                        # Detectar voto BUY/SELL
                        if self.voting_open:
                            vote = None
                            if "BUY" in comment or "COMPRA" in comment or "COMPRAS" in comment or "LARGO" in comment or "LARGOS" in comment or "ALCISTA" in comment:
                                vote = "BUY"
                            elif "SELL" in comment or "VENTA" in comment or "VENTAS" in comment or "CORTO" in comment or "CORTOS" in comment or "BAJISTA" in comment:
                                vote = "SELL"

                            if vote and unique_id not in self.voters_this_zone:
                                self.voters_this_zone.add(unique_id)
                                self.votes.append({
                                    "name": username,
                                    "unique_id": unique_id,
                                    "vote": vote,
                                    "avatar_url": avatar_url
                                })
                                # Descargar avatar en background
                                threading.Thread(target=download_avatar, args=(username, avatar_url), daemon=True).start()
                                print(f"[VOTO] {username} -> {vote}")
                    except Exception as comment_err:
                        print(f"[TIKTOK] Error procesando comentario: {comment_err}")

                print(f"[TIKTOK] Conectando a @{self.username}...")
                await self.client.connect()

            except Exception as e:
                self.connected = False
                self.reconnecting = True
                self.reconnect_attempts += 1
                wait_time = min(30, 5 * self.reconnect_attempts)  # Espera progresiva: 5s, 10s, 15s... max 30s
                print(f"[TIKTOK] Error: {e}. Reintento en {wait_time}s (intento #{self.reconnect_attempts})")
                await asyncio.sleep(wait_time)

        print("[TIKTOK] Máximo de reintentos alcanzado. Usando bots simulados.")

    def open_voting(self):
        """Abrir votación (cuando se detecta zona)"""
        self.voting_open = True
        self.votes = []
        self.voters_this_zone = set()

    def close_voting(self):
        """Cerrar votación (cuando termina el timer)"""
        self.voting_open = False

    def get_votes(self):
        """Obtener votos actuales"""
        return self.votes.copy()

    def get_vote_count(self):
        """Obtener conteo de votos"""
        buy = sum(1 for v in self.votes if v["vote"] == "BUY")
        sell = sum(1 for v in self.votes if v["vote"] == "SELL")
        return buy, sell

    def is_connected(self):
        """Verificar si está conectado"""
        return self.connected

    def is_reconnecting(self):
        """Verificar si está intentando reconectar"""
        return self.reconnecting and not self.connected

    def has_real_voters(self):
        """Verificar si hay voters reales (para desactivar bots)"""
        return len(self.votes) > 0
