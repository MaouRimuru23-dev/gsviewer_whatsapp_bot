import os
import json
from flask import Flask, request, jsonify
import requests

# Importar tus módulos existentes de Python
try:
    import sync_global_info
except ImportError:
    sync_global_info = None

app = Flask(__name__)

# Cargar diccionario maestro actualizado
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAESTRO_PATH = os.path.join(BASE_DIR, "diccionarios", "diccionario_maestro_gs.json")

def cargar_datos_maestros():
    if os.path.exists(MAESTRO_PATH):
        with open(MAESTRO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

datos_gs = cargar_datos_maestros()

# URL de tu Google Apps Script de Guías de Misiones
GOOGLE_SHEETS_API_URL = "https://script.google.com/macros/s/AKfycbzauS_CZCo8Leqa--MP5nzLL58S1Is8UHeXY0ZGDzYDyislU3-1TlnROR_ZLvV8eVE8zw/exec"

@app.route("/", methods=["GET"])
def home():
    return "🤖 GSViewer WhatsApp Bot Server Activo y Listo!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Punto de entrada que recibe los mensajes desde la API de WhatsApp (Evolution API / Baileys / Twilio)
    """
    data = request.get_json() or {}
    
    # Extraer el mensaje y el número del remitente
    mensaje_usuario = data.get("message", "").strip()
    numero_remitente = data.get("sender", "")

    if not mensaje_usuario:
        return jsonify({"status": "no_message"}), 200

    # Procesar el comando recibido
    respuesta_texto = procesar_comando(mensaje_usuario)

    return jsonify({
        "to": numero_remitente,
        "response": respuesta_texto
    }), 200


def procesar_comando(texto):
    texto_lower = texto.lower().strip()

    # COMANDO 1: Ayuda / Menú Principal
    if texto_lower in ["!ayuda", "!help", "hola", "menu"]:
        return (
            "⚔️ *BIENVENIDO AL AGENTE TÁCTICO GSVIEWER* ⚔️\n\n"
            "Puedes enviarme los siguientes comandos:\n\n"
            "🔹 *!unidad [Nombre]* -> Información, Tier, Rol y Crestas de un Héroe.\n"
            "🔹 *!guia [Misión o Boss]* -> Busca guías comunitarias verificadas.\n"
            "🔹 *!equipo [Nombre]* -> Stats y rareza de un Equipamiento.\n"
            "🔹 *!sync* -> Forzar sincronización con la Wiki oficial.\n\n"
            "💡 *Ejemplo*: `!unidad Shirou Emiya` o `!guia Dungeon 26`"
        )

    # COMANDO 2: Buscar Unidad / Héroe
    if texto_lower.startswith("!unidad ") or texto_lower.startswith("!heroe "):
        nombre_buscado = texto[8:].strip()
        return buscar_unidad_info(nombre_buscado)

    # COMANDO 3: Buscar Guía de Misión en Google Sheets
    if texto_lower.startswith("!guia ") or texto_lower.startswith("!mision "):
        mision_buscada = texto[6:].strip()
        return buscar_guia_mision(mision_buscada)

    # COMANDO 4: Sincronización Automática
    if texto_lower == "!sync":
        if sync_global_info:
            try:
                sync_global_info.ejecutar_sincronizacion_completa()
                global datos_gs
                datos_gs = cargar_datos_maestros()
                return "✅ *Sincronización Completa*: La base de datos de GSViewer ha sido actualizada con la Wiki oficial."
            except Exception as e:
                return f"❌ Error durante la sincronización: {str(e)}"
        return "⚠️ Módulo de sincronización no disponible en el servidor."

    # Respuesta por defecto si no reconoce el comando
    return (
        "🤖 No entendí ese comando.\n"
        "Escribe `!ayuda` para ver la lista de comandos disponibles."
    )


def buscar_unidad_info(nombre):
    # Buscar coincidencia en el diccionario cargado por tus scripts de Python
    unidades = datos_gs.get("personajes", [])
    nombre_norm = nombre.lower()

    coincidencia = None
    for u in unidades:
        if nombre_norm in u.get("nombre", "").lower() or nombre_norm in u.get("nombreOriginal", "").lower():
            coincidencia = u
            break

    if not coincidencia:
        return f"🔍 No encontré a la unidad *'{nombre}'*. Verifica el nombre e intenta de nuevo."

    # Formatear respuesta con emojis
    return (
        f"⚔️ *{coincidencia.get('nombre').upper()}*\n"
        f"🌟 *Rareza / Tier*: {coincidencia.get('rareza', '★5')} | Tier {coincidencia.get('tier', 'N/A')}\n"
        f"🔥 *Elemento*: {coincidencia.get('elemento', 'N/A')} | *Raza*: {coincidencia.get('raza', 'N/A')}\n"
        f"🛡️ *Rol*: {coincidencia.get('rol', 'N/A')}\n\n"
        f"🔮 *Crestas Recomendadas*: {coincidencia.get('crestRecom', 'ATK UP, Equip CT Speed')}\n"
        f"✨ *SuperAwakening*: {'Sí' if coincidencia.get('isSA') else 'No'}"
    )


def buscar_guia_mision(query):
    try:
        res = requests.get(f"{GOOGLE_SHEETS_API_URL}?mode=approved", timeout=8)
        guias = res.json()
        query_norm = query.lower()

        filtradas = [
            g for g in guias
            if query_norm in g.get("nombreMision", "").lower()
            or query_norm in g.get("jefe", "").lower()
            or any(query_norm in h.lower() for h in g.get("hashtags", []))
        ]

        if not filtradas:
            return f"📜 No encontré guías comunitarias para *'{query}'*."

        g = filtradas[0] # Tomar la primera guía coincidente
        equipo_txt = []
        for idx, member in enumerate(g.get("equipo", [])):
            u_id = member.get("idUnidad", "Héroe")
            equipo_txt.append(f"  • Posición {idx+1}: {u_id}")

        return (
            f"⚔️ *GUÍA DE MISIÓN: {g.get('nombreMision')}*\n"
            f"👹 *Boss*: {g.get('jefe', 'N/A')}\n"
            f"👍 *Likes*: {g.get('likes', 0)} | 👎 *Dislikes*: {g.get('dislikes', 0)}\n\n"
            f"🛡️ *Formación*:\n" + "\n".join(equipo_txt) + "\n\n"
            f"📝 *Estrategia*:\n{g.get('estrategiaTexto', 'Sin estrategia escrita.')}\n\n"
            f"📱 *Abre GSViewer para ver la mesa táctica en HD.*"
        )
    except Exception as e:
        return f"❌ Error consultando la base de guías: {str(e)}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)