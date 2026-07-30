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
    ("ZONA_VOZ_1.mp3", "Atención, el precio está llegando a una zona interesante, analicen bien antes de decidir"),
    ("ZONA_VOZ_2.mp3", "Traders, el precio acaba de tocar una zona operativa, así que piensen bien y decidan, ¿compran o venden?"),
    ("ZONA_VOZ_3.mp3", "el precio acaba de entrar a una zona, tienen unos segundos para decidir, escriban en el chat si van en compra o en venta"),
    ("ZONA_VOZ_4.mp3", "El precio entró en la zona, esto se pone interesante, ¿Qué opinan? escriban en el chat"),
    ("ZONA_VOZ_5.mp3", "El precio acaba de entrar en una zona importante, decidan rápido, ¿compran o venden?"),
    ("ZONA_VOZ_6.mp3", "Momento de decisión, el mercado nos está dando una oportunidad, por lo tanto escriban en el chat si compran o venden"),
    ("ZONA_VOZ_7.mp3", "El gráfico nos está hablando, ¿para que dirección va? escriban en el chat"),
    ("ZONA_VOZ_8.mp3", "Zona operativa alcanzada, analicen la estructura y decidan, ¿compra o venta?"),
    ("ZONA_VOZ_9.mp3", "Traders, llegó el momento, el precio tocó la zona, escriban su decisión en el chat"),
    ("ZONA_VOZ_10.mp3", "Atención a esta zona, el precio está reaccionando, ¿van en compra o van en venta?"),
    ("ZONA_VOZ_11.mp3", "Se presentó una oportunidad, tienen pocos segundos para tomar una decisión, piensen y escriban en el chat"),
    ("ZONA_VOZ_12.mp3", "El mercado nos da otra entrada, analicen bien, ¿Cuál es su jugada? escriban en el chat, BUY o SELL"),
]

# Frases cuando LEAN FX opera (bot entra al trade)
FRASES_LEAN_BUY = [
    ("LEAN_BUY_1.mp3", "Yo voy a entrar en compra en esta zona, ahora solo queda esperar el resultado"),
    ("LEAN_BUY_2.mp3", "Me gusta esta zona para comprar, por lo tanto posiciono una compra y ahora solo queda esperar"),
    ("LEAN_BUY_3.mp3", "Voy en compra, la estructura me da una alta probabilidad de reacción en esta zona"),
]

FRASES_LEAN_SELL = [
    ("LEAN_SELL_1.mp3", "Yo voy a entrar en venta en esta zona, ahora solo queda esperar el resultado"),
    ("LEAN_SELL_2.mp3", "Me gusta esta zona para ventas, por lo tanto posiciono una venta y ahora solo queda esperar"),
    ("LEAN_SELL_3.mp3", "Voy en ventas, la estructura me da una alta probabilidad de reacción en esta zona"),
]

# Frases cuando se resuelve el trade
FRASES_WIN = [
    ("VOZ_WIN_1.mp3", "Muy bien, esa operación fue ganadora, los que acertaron felicidades"),
    ("VOZ_WIN_2.mp3", "Take profit alcanzado, excelente lectura del mercado para los que tomaron esta operación"),
    ("VOZ_WIN_3.mp3", "Operación ganadora, el análisis fue correcto, felicidades a los que acertaron"),
]

FRASES_LOSS = [
    ("VOZ_LOSS_1.mp3", "Esta operación terminó en stop loss, pero no hay que preocuparse ya que habrá mas oportunidades"),
    ("VOZ_LOSS_2.mp3", "El mercado nos sacó en stop loss, pero así es el trading, lo importante es la consistencia"),
    ("VOZ_LOSS_3.mp3", "Stop loss tocado, no siempre se gana, pero la estrategia sigue siendo buena, vamos por la siguiente entrada"),
]

# Frases entre trades (para mantener la atención)
FRASES_IDLE = [
    ("IDLE_VOZ_1.mp3", "El precio sigue moviéndose, estén atentos que en cualquier momento se activa una zona"),
    ("IDLE_VOZ_2.mp3", "Buscamos la siguiente zona operativa, el mercado está formando estructura"),
    ("IDLE_VOZ_3.mp3", "Paciencia traders, el precio necesita desarrollar antes de darnos otra oportunidad"),
    ("IDLE_VOZ_4.mp3", "Estamos cerca de una zona, prepárense para la siguiente decisión"),
    ("IDLE_VOZ_5.mp3", "Buen trading de los que acertaron la última, sigan así y el ranking se mueve"),
    ("IDLE_VOZ_6.mp3", "El gráfico está formando una nueva estructura, esto se pone interesante"),
    ("IDLE_VOZ_7.mp3", "Recuerden escribir BUY o SELL cuando aparezca la zona, así participan del ranking"),
]

async def generar_audio(texto, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    print(f"Generando: {filename}...")
    communicate = edge_tts.Communicate(texto, VOICE, rate=RATE)
    await communicate.save(filepath)
    print(f"  ✓ Guardado: {filepath}")

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_frases = FRASES_ZONA + FRASES_LEAN_BUY + FRASES_LEAN_SELL + FRASES_WIN + FRASES_LOSS + FRASES_IDLE
    print(f"Generando {len(all_frases)} audios con voz: {VOICE} (velocidad: {RATE})")
    print(f"Carpeta: {OUTPUT_DIR}\n")
    for filename, texto in all_frases:
        await generar_audio(texto, filename)
    print(f"\n¡Listo! {len(all_frases)} audios generados.")
    print("Ahora ejecutá el juego y las voces sonarán automáticamente.")

if __name__ == "__main__":
    asyncio.run(main())
