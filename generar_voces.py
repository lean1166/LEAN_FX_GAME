"""
Script para generar los audios de voz IA (Jorge de México)
Ejecutar UNA VEZ en tu PC para crear los MP3 en assets/sound/

Requisito: pip install edge-tts
"""
import asyncio
import edge_tts
import os

# Voz de Jorge de México (la misma que Luvvoice)
VOICE = "es-MX-JorgeNeural"
RATE = "+8%"  # 8% más rápido (como en Luvvoice)

# Carpeta de salida
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sound")

# Frases para zona detectada (se eligen al azar en el juego)
FRASES_ZONA = [
    ("ZONA_VOZ_1.mp3", "Traders, el precio llegó a zona operativa, piensen bien, ¿compran o venden?"),
    ("ZONA_VOZ_2.mp3", "Zona detectada, escriban en el chat, ¿compran o venden?"),
    ("ZONA_VOZ_3.mp3", "Atención traders, el precio tocó la zona, ¿qué hacemos?"),
    ("ZONA_VOZ_4.mp3", "Entrada activa, pocos segundos, escriban BUY o SELL en el chat"),
    ("ZONA_VOZ_5.mp3", "Oportunidad detectada, el precio tocó zona, ¿compra o venta?"),
    ("ZONA_VOZ_6.mp3", "Llegó el momento, escriban su decisión en el chat, ¿compra o venta?"),
    ("ZONA_VOZ_7.mp3", "Precio en zona, analicen rápido, escriban en el chat"),
    ("ZONA_VOZ_8.mp3", "Zona activa, ¿quién se anima? escriban BUY o SELL"),
    ("ZONA_VOZ_9.mp3", "El mercado nos da oportunidad, ¿hacia dónde va? decidan ya"),
    ("ZONA_VOZ_10.mp3", "Se activó la zona, el tiempo corre, comenten, ¿compran o venden?"),
    ("ZONA_VOZ_11.mp3", "Momento clave, el precio está en zona importante, ¿cuál es tu jugada?"),
    ("ZONA_VOZ_12.mp3", "Traders, el gráfico habla, escriban en el chat, ¿largos o cortos?"),
]

# Frases cuando LEAN FX opera (bot entra al trade)
FRASES_LEAN_BUY = [
    ("LEAN_BUY_1.mp3", "Yo voy en compra, veamos qué pasa"),
    ("LEAN_BUY_2.mp3", "Me voy largo en esta, vamos a ver"),
    ("LEAN_BUY_3.mp3", "Compra para mí, confío en la zona"),
]

FRASES_LEAN_SELL = [
    ("LEAN_SELL_1.mp3", "Yo voy en venta, veamos cómo sale"),
    ("LEAN_SELL_2.mp3", "Me voy corto, esta zona se ve bien"),
    ("LEAN_SELL_3.mp3", "Venta para mí, a esperar el resultado"),
]

# Frases cuando se resuelve el trade
FRASES_WIN = [
    ("VOZ_WIN_1.mp3", "Ganamos esta, bien jugado traders"),
    ("VOZ_WIN_2.mp3", "¡Victoria! Los que acertaron, felicidades"),
    ("VOZ_WIN_3.mp3", "Take profit tocado, excelente entrada"),
]

FRASES_LOSS = [
    ("VOZ_LOSS_1.mp3", "Se perdió esta, el mercado decidió, a la siguiente"),
    ("VOZ_LOSS_2.mp3", "Stop loss tocado, no siempre se gana, seguimos"),
    ("VOZ_LOSS_3.mp3", "Perdimos esta, pero hay más oportunidades"),
]

async def generar_audio(texto, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    print(f"Generando: {filename}...")
    communicate = edge_tts.Communicate(texto, VOICE, rate=RATE)
    await communicate.save(filepath)
    print(f"  ✓ Guardado: {filepath}")

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_frases = FRASES_ZONA + FRASES_LEAN_BUY + FRASES_LEAN_SELL + FRASES_WIN + FRASES_LOSS
    print(f"Generando {len(all_frases)} audios con voz: {VOICE} (velocidad: {RATE})")
    print(f"Carpeta: {OUTPUT_DIR}\n")
    for filename, texto in all_frases:
        await generar_audio(texto, filename)
    print(f"\n¡Listo! {len(all_frases)} audios generados.")
    print("Ahora ejecutá el juego y las voces sonarán automáticamente.")

if __name__ == "__main__":
    asyncio.run(main())
