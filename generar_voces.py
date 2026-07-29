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

# Carpeta de salida
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sound")

# Frases para zona detectada (se eligen al azar en el juego)
FRASES_ZONA = [
    ("ZONA_VOZ_1.mp3", "El precio acaba de llegar a una zona operativa. Ahora piensa y responde, ¿compran o venden?"),
    ("ZONA_VOZ_2.mp3", "¡Zona detectada! Es hora de decidir. ¿Compran o venden?"),
    ("ZONA_VOZ_3.mp3", "¡Atención traders! El precio llegó a la zona. ¿Qué hacemos?"),
    ("ZONA_VOZ_4.mp3", "Se activó una entrada. Tienen pocos segundos para decidir. ¿Compran o venden?"),
    ("ZONA_VOZ_5.mp3", "¡Oportunidad detectada! El precio tocó la zona. ¿Van en compra o en venta?"),
    ("ZONA_VOZ_6.mp3", "¡Llegó el momento! El mercado está en zona operativa. Escriban su decisión."),
]

async def generar_audio(texto, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    print(f"Generando: {filename}...")
    communicate = edge_tts.Communicate(texto, VOICE)
    await communicate.save(filepath)
    print(f"  ✓ Guardado: {filepath}")

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generando {len(FRASES_ZONA)} audios con voz: {VOICE}")
    print(f"Carpeta: {OUTPUT_DIR}\n")
    for filename, texto in FRASES_ZONA:
        await generar_audio(texto, filename)
    print(f"\n¡Listo! {len(FRASES_ZONA)} audios generados.")
    print("Ahora ejecutá el juego y la voz sonará cuando se detecte una zona.")

if __name__ == "__main__":
    asyncio.run(main())
