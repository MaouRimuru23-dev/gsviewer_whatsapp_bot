import os 
import json 
from flask import Flask, request, jsonify 
import requests

# Importar módulos de sincronización
try: 
    import sync_global_info 
except ImportError: 
    sync_global_info = None

app = Flask(__name__)

# CONFIGURACIÓN
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "9193876123:AAHqmpdwNmpAvED2cdkZa9y9aspkNF3cgfE")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICCIONARIOS_DIR = os.path.join(BASE_DIR, "diccionarios")
PERSONAJES_PATH = os.path.join(DICCIONARIOS_DIR, "lista_personajes_global.json")
OBJETOS_PATH = os.path.join(DICCIONARIOS_DIR, "lista_objetos_global.json")
GOOGLE_SHEETS_API_URL = "https://script.google.com/macros/s/AKfycbzauS_CZCo8Leqa--MP5nzLL58S1Is8UHeXY0ZGDzYDyislU3-1TlnROR_ZLvV8eVE8zw/exec"

def cargar_personajes(): 
    if os.path.exists(PERSONAJES_PATH): 
        try: 
            with open(PERSONAJES_PATH, "r", encoding="utf-8") as f: 
                return json.load(f) 
        except Exception: 
            return [] 
    return []

def cargar_objetos(): 
    if os.path.exists(OBJETOS_PATH): 
        try: 
            with open(OBJETOS_PATH, "r", encoding="utf-8") as f: 
                return json.load(f) 
        except Exception: 
            return [] 
    return []

@app.route("/", methods=["GET"]) 
def home(): 
    return "🤖 GSViewer Telegram Bot Server Activo y Listo!", 200

@app.route("/telegram-webhook", methods=["POST"]) 
def telegram_webhook(): 
    """Recibe los mensajes en tiempo real desde la API de Telegram""" 
    data = request.get_json() or {}
    
    msg_obj = data.get("message") or data.get("edited_message")
    if msg_obj:
        chat_id = msg_obj.get("chat", {}).get("id")
        texto = msg_obj.get("text", "").strip()

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
    
    # Manejar menciones en grupos (/unidad@GSViewer_bot Chloe -> /unidad Chloe)
    if "@" in texto_lower:
        partes = texto_lower.split()
        if partes:
            cmd = partes[0].split("@")[0]
            texto_lower = " ".join([cmd] + partes[1:])

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
    if texto_lower.startswith("/unidad") or texto_lower.startswith("!unidad"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            return buscar_unidad_info(partes[1].strip())
        return "⚠️ Uso del comando: `/unidad [Nombre de Héroe]` (Ejemplo: `/unidad Shirou`)"

    # BUSCAR GUÍA DE MISIÓN
    if texto_lower.startswith("/guia") or texto_lower.startswith("!guia"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            return buscar_guia_mision(partes[1].strip())
        return "⚠️ Uso del comando: `/guia [Nombre de Misión o Boss]` (Ejemplo: `/guia Dungeon 26`)"

    # SINCRONIZACIÓN AUTOMÁTICA CON LA WIKI
    if texto_lower in ["/sync", "!sync"]:
        if sync_global_info:
            try:
                ok = sync_global_info.sync_from_global_db(DICCIONARIOS_DIR)
                if ok:
                    p_count = len(cargar_personajes())
                    return f"✅ *Sincronización Exitosa*: {p_count} héroes sincronizados con la Wiki oficial."
                return "⚠️ No se encontraron actualizaciones nuevas en la Wiki."
            except Exception as e:
                return f"❌ Error en sincronización: {str(e)}"
        return "⚠️ Módulo de sincronización no disponible."

    return "🤖 Comando no reconocido. Envía `/help` para ver la lista de comandos disponibles."

def buscar_unidad_info(nombre): 
    unidades = cargar_personajes()
    nombre_norm = nombre.lower()
    coincidencia = None
    
    for u in unidades:
        if not isinstance(u, dict): continue
        nom = u.get("nombre", "").lower()
        nom_orig = u.get("nombre_original", "").lower()
        if nombre_norm in nom or nombre_norm in nom_orig:
            coincidencia = u
            break

    if not coincidencia:
        return f"🔍 No encontré a la unidad *'{nombre}'*. Verifica el nombre e intenta de nuevo."

    is_sa = coincidencia.get("is_sa", False) or coincidencia.get("isSA", False) or "Ascended" in coincidencia.get("tags", [])
    raza = coincidencia.get("raza", "N/A")
    if not raza or raza == "N/A":
        raza = coincidencia.get("race", "Humano")

    slots_list = coincidencia.get("slots", [])
    slots_txt = [f"  • {s.get('valor', '')} {s.get('tipo', '')}" for s in slots_list if isinstance(s, dict)]
    slots_str = "\n".join(slots_txt) if slots_txt else "  • No disponible"

    sk = coincidencia.get("skillset", {}) or {}
    skill_txt = sk.get("skill", "")
    arts_txt = sk.get("arts", "")
    ta_txt = sk.get("truearts", "")
    sa_txt = sk.get("superarts", "")

    resp = [
        f"⚔️ *{coincidencia.get('nombre', 'Héroe').upper()}*",
        f"🌟 *Rareza*: {coincidencia.get('rareza', '★5')} | *Tier*: {coincidencia.get('tier', 'N/A')}",
        f"🔥 *Elemento*: {coincidencia.get('elemento', 'N/A')} | *Raza*: {raza}",
        f"🛡️ *Rol*: {coincidencia.get('rol', 'N/A')}",
        f"✨ *SuperAwakening (SA)*: {'Sí (★6 SA)' if is_sa else 'No (★5)'}",
        "",
        f"🎒 *Slots de Equipamiento*:\n{slots_str}",
        "",
        f"🔮 *Crestas Recomendadas*: {coincidencia.get('crestRecom', 'ATK UP, Equip CT Speed')}"
    ]

    if skill_txt:
        resp.append(f"\n🗡️ *Skill*: {skill_txt.strip()}")
    if arts_txt:
        resp.append(f"\n🔮 *Arts*: {arts_txt.strip()}")
    if ta_txt:
        resp.append(f"\n⚔️ *True Arts*: {ta_txt.strip()}")
    if sa_txt:
        resp.append(f"\n⚡ *Super Arts*: {sa_txt.strip()}")

    return "\n".join(resp)

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
