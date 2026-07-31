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
    ("ZONA_VOZ_13.mp3", "Ojo con esta zona, el precio está reaccionando justo donde esperábamos, así que escriban rápido en el chat"),
    ("ZONA_VOZ_14.mp3", "Miren eso, la zona operativa fue alcanzada, es lo que estábamos esperando, así que de esa forma, ¿compran o venden? decidan ahora"),
    ("ZONA_VOZ_15.mp3", "El precio llegó a una zona clave, recuerden que tienen pocos segundos para responder si compran o venden"),
    ("ZONA_VOZ_16.mp3", "Aquí hay una oportunidad clara donde el mercado nos está dando una señal, ¿Qué decisión toman?"),
    ("ZONA_VOZ_17.mp3", "Zona tocada, a ver quién tiene la mejor lectura del mercado hoy, así escriban en el chat si van en compra o en venta"),
    ("ZONA_VOZ_18.mp3", "Atención todos, el precio está testeando una zona importante, es momento de decidir"),
]

# Frases cuando LEAN FX opera (bot entra al trade)
FRASES_LEAN_BUY = [
    ("LEAN_BUY_1.mp3", "Yo voy a entrar en compra en esta zona, ahora solo queda esperar el resultado"),
    ("LEAN_BUY_2.mp3", "Me gusta esta zona para comprar, por lo tanto posiciono una compra y ahora solo queda esperar"),
    ("LEAN_BUY_3.mp3", "Voy en compra, la estructura me da una alta probabilidad de reacción en esta zona"),
    ("LEAN_BUY_4.mp3", "La estructura me dice compra, voy a posicionarme largo en esta zona y veremos qué pasa"),
    ("LEAN_BUY_5.mp3", "Veo presión compradora en esta zona, me posiciono en compras para esperar si el mercado me da la razón"),
    ("LEAN_BUY_6.mp3", "Esta zona tiene buena pinta para compras, colocaré una compra, esperemos que el precio reaccione a favor"),
]

FRASES_LEAN_SELL = [
    ("LEAN_SELL_1.mp3", "Yo voy a entrar en venta en esta zona, ahora solo queda esperar el resultado"),
    ("LEAN_SELL_2.mp3", "Me gusta esta zona para ventas, por lo tanto posiciono una venta y ahora solo queda esperar"),
    ("LEAN_SELL_3.mp3", "Voy en ventas, la estructura me da una alta probabilidad de reacción en esta zona"),
    ("LEAN_SELL_4.mp3", "La estructura me dice venta, voy a posicionarme en ventas en esta zona para ver que pasa"),
    ("LEAN_SELL_5.mp3", "Veo presión vendedora en esta zona, me posiciono en venta, veamos si el mercado me da la razón"),
    ("LEAN_SELL_6.mp3", "Esta zona tiene buena pinta para ventas, por lo tanto tomare una venta, esperemos que el precio reaccione a favor"),
]

# Frases cuando se resuelve el trade
FRASES_WIN = [
    ("VOZ_WIN_1.mp3", "Muy bien, esa operación fue ganadora, los que acertaron felicidades"),
    ("VOZ_WIN_2.mp3", "Take profit alcanzado, excelente lectura del mercado para los que tomaron esta operación"),
    ("VOZ_WIN_3.mp3", "Operación ganadora, el análisis fue correcto, felicidades a los que acertaron"),
    ("VOZ_WIN_4.mp3", "Take profit tocado, por lo tanto tenemos otra operación ganadora, así que todos los que siguieron la estrategia se llevan puntos"),
    ("VOZ_WIN_5.mp3", "Ganamos la operación, donde el análisis fue correcto gracias a la paciencia y disciplina"),
    ("VOZ_WIN_6.mp3", "Excelente, el mercado reaccionó como esperábamos, felicidades a todos los ganadores"),
    ("VOZ_WIN_7.mp3", "Operación cerrada en positivo, vamos sumando puntos al ranking"),
]

FRASES_LOSS = [
    ("VOZ_LOSS_1.mp3", "Esta operación terminó en stop loss, pero no hay que preocuparse ya que habrá mas oportunidades"),
    ("VOZ_LOSS_2.mp3", "El mercado nos sacó en stop loss, pero así es el trading, lo importante es la consistencia"),
    ("VOZ_LOSS_3.mp3", "Stop loss tocado, no siempre se gana, pero la estrategia sigue siendo buena, vamos por la siguiente entrada"),
    ("VOZ_LOSS_4.mp3", "El mercado decidió ir en contra, stop loss activado, pero tranquilos que la siguiente puede ser buena"),
    ("VOZ_LOSS_5.mp3", "Esta vez no salió como esperábamos, el precio toco el stop loss, pero la clave es la consistencia"),
    ("VOZ_LOSS_6.mp3", "Pérdida controlada, eso es lo importante porque siempre hay que operar con gestión de riesgo, así que ahora hay que tener paciencia e ir por la próxima operación"),
    ("VOZ_LOSS_7.mp3", "El stop loss hizo su trabajo y nos protegió de una pérdida mayor, así se maneja el riesgo"),
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
    ("IDLE_VOZ_8.mp3", "Mientras esperamos la siguiente zona, recuerden que la paciencia es la mejor herramienta de un trader"),
    ("IDLE_VOZ_9.mp3", "El mercado está consolidando, en cualquier momento rompe y nos da una nueva oportunidad"),
    ("IDLE_VOZ_10.mp3", "Sigan atentos al chat, cuando aparezca la zona tienen que escribir rápido para participar"),
    ("IDLE_VOZ_11.mp3", "Vamos bien hoy, el ranking se está moviendo, vamos a ver quién termina en el primer lugar"),
    ("IDLE_VOZ_12.mp3", "El precio está formando una nueva tendencia, esto se va a poner bueno en unos segundos"),
    ("IDLE_VOZ_13.mp3", "Para los nuevos que están llegando, escriban compra o venta cuando aparezca la zona para participar"),
    ("IDLE_VOZ_14.mp3", "La próxima zona se esta acercando, el que reaccione más rápido tiene ventaja"),
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
