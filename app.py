import os 
import json 
from flask import Flask, request, jsonify 
import requests

# Importar tus módulos de Python existentes
try: 
    import sync_global_info 
except ImportError: 
    sync_global_info = None

app = Flask(__name__)

# CONFIGURACIÓN
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "9193876123:AAHqmpdwNmpAvED2cdkZa9y9aspkNF3cgfE")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAESTRO_PATH = os.path.join(BASE_DIR, "diccionarios", "diccionario_maestro_gs.json")
GOOGLE_SHEETS_API_URL = "https://script.google.com/macros/s/AKfycbzauS_CZCo8Leqa--MP5nzLL58S1Is8UHeXY0ZGDzYDyislU3-1TlnROR_ZLvV8eVE8zw/exec"

def cargar_datos_maestros(): 
    if os.path.exists(MAESTRO_PATH): 
        try: 
            with open(MAESTRO_PATH, "r", encoding="utf-8") as f: 
                return json.load(f) 
        except Exception: 
            return {} 
    return {}

datos_gs = cargar_datos_maestros()

@app.route("/", methods=["GET"]) 
def home(): 
    return "🤖 GSViewer Telegram Bot Server Activo y Listo!", 200

@app.route("/telegram-webhook", methods=["POST"]) 
def telegram_webhook(): 
    """Recibe los mensajes en tiempo real desde la API de Telegram""" 
    data = request.get_json() or {}
    
    if "message" in data:
        mensaje_obj = data["message"]
        chat_id = mensaje_obj.get("chat", {}).get("id")
        texto = mensaje_obj.get("text", "").strip()

        if chat_id and texto:
            respuesta = procesar_comando(texto)
            enviar_mensaje_telegram(chat_id, respuesta)

    return jsonify({"status": "ok"}), 200

def enviar_mensaje_telegram(chat_id, texto): 
    """Envía la respuesta a Telegram usando formato Markdown""" 
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" 
    payload = { 
        "chat_id": chat_id, 
        "text": texto, 
        "parse_mode": "Markdown", 
        "disable_web_page_preview": True 
    } 
    try: 
        requests.post(url, json=payload, timeout=5) 
    except Exception as e: 
        print(f"Error enviando mensaje a Telegram: {e}")

def procesar_comando(texto): 
    texto_lower = texto.lower().strip()
    
    # Si se usa en un grupo de Telegram, los comandos vienen como /unidad@GSViewer_bot
    if "@" in texto_lower:
        texto_lower = texto_lower.split("@")[0]

    # AYUDA / MENÚ
    if texto_lower in ["/start", "/help", "!ayuda", "hola", "menu"]:
        return (
            "⚔️ *BIENVENIDO AL AGENTE TÁCTICO GSVIEWER* ⚔️\n\n"
            "Puedes enviarme los siguientes comandos (en privado o en grupos):\n\n"
            "🔹 `/unidad [Nombre]` -> Info, Tier, Rol y Crestas de un Héroe.\n"
            "🔹 `/guia [Misión o Boss]` -> Guías comunitarias verificadas.\n"
            "🔹 `/sync` -> Sincronizar con la Wiki oficial de GS.\n\n"
            "💡 *Ejemplo*: `/unidad Shirou` o `/guia Dungeon 26`"
        )

    # BUSCAR UNIDAD
    if texto_lower.startswith("/unidad ") or texto_lower.startswith("!unidad "):
        nombre = texto[8:].strip()
        return buscar_unidad_info(nombre)

    # BUSCAR GUÍA DE MISIÓN
    if texto_lower.startswith("/guia ") or texto_lower.startswith("!guia "):
        query = texto[6:].strip()
        return buscar_guia_mision(query)

    # SINCRONIZACIÓN AUTOMÁTICA
    if texto_lower in ["/sync", "!sync"]:
        if sync_global_info:
            try:
                sync_global_info.ejecutar_sincronizacion_completa()
                global datos_gs
                datos_gs = cargar_datos_maestros()
                return "✅ *Sincronización Completa*: Base de datos actualizada con la Wiki oficial."
            except Exception as e:
                return f"❌ Error en sincronización: {str(e)}"
        return "⚠️ Módulo de sincronización no disponible."

    return "🤖 Comando no reconocido. Envía `/help` para ver la lista de comandos disponibles."

def buscar_unidad_info(nombre): 
    unidades = datos_gs.get("personajes", []) if isinstance(datos_gs, dict) else (datos_gs if isinstance(datos_gs, list) else [])
    nombre_norm = nombre.lower()
    coincidencia = None
    
    for u in unidades:
        if not isinstance(u, dict): continue
        if nombre_norm in u.get("nombre", "").lower() or nombre_norm in u.get("nombreOriginal", "").lower():
            coincidencia = u
            break

    if not coincidencia:
        return f"🔍 No encontré a la unidad *'{nombre}'*. Verifica el nombre e intenta de nuevo."

    return (
        f"⚔️ *{coincidencia.get('nombre', 'Héroe').upper()}*\n"
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

        g = filtradas[0]
        equipo_txt = []
        for idx, member in enumerate(g.get("equipo", [])):
            u_id = member.get("idUnidad", "Héroe")
            equipo_txt.append(f"  • Posición {idx+1}: {u_id}")

        return (
            f"⚔️ *GUÍA DE MISIÓN: {g.get('nombreMision')}*\n"
            f"👹 *Boss Target*: {g.get('jefe', 'N/A')}\n"
            f"👍 *Likes*: {g.get('likes', 0)} | 👎 *Dislikes*: {g.get('dislikes', 0)}\n\n"
            f"🛡️ *Formación*:\n" + "\n".join(equipo_txt) + "\n\n"
            f"📝 *Estrategia*:\n{g.get('estrategiaTexto', 'Sin estrategia escrita.')}\n\n"
            f"📱 *Abre GSViewer para ver la mesa táctica en HD.*"
        )
    except Exception as e:
        return f"❌ Error consultando guías: {str(e)}"

if __name__ == "__main__": 
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host="0.0.0.0", port=port)
