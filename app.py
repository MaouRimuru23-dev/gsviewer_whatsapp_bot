import os 
import json 
import re
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

# Diccionario de Traducción de Términos Frecuentes
DICCIONARIO_TRADUCCION = {
    "Increase own Arts by": "Aumenta sus propias Artes en",
    "Increase all Allies' Arts by": "Aumenta las Artes de todos los Aliados en",
    "Increase allies' Arts by": "Aumenta las Artes de los aliados en",
    "DMG barrier that negates": "Barrera de daño que anula",
    "Reduce Enemies' PHY RES by": "Reduce la Res. Física de los enemigos en",
    "Reduce Enemies' MAG RES by": "Reduce la Res. Mágica de los enemigos en",
    "Increase own ATK & DMG Up by": "Aumenta el ATK y Daño propio en",
    "Increase own ATK by": "Aumenta el ATK propio en",
    "Increase allies' DMG Up by": "Aumenta el Daño de los aliados en",
    "PHY RES by": "Res. Física en",
    "MAG RES by": "Res. Mágica en",
    "During Unlimited Blade Works:": "Durante Unlimited Blade Works:",
    "For 10s,": "Durante 10s,",
    "For 12s,": "Durante 12s,",
    "For 15s,": "Durante 15s,",
    "For 20s,": "Durante 20s,",
    "For 25s,": "Durante 25s,",
    "For 30s,": "Durante 30s,",
    "For 35s,": "Durante 35s,",
    "For 180s, Enter Unlimited Blade Works": "Durante 180s, Entra en Unlimited Blade Works",
    "Water DMG (PHY)": "Daño de Agua (Físico)",
    "Fire DMG (PHY)": "Daño de Fuego (Físico)",
    "Earth DMG (PHY)": "Daño de Tierra (Físico)",
    "Light DMG (PHY)": "Daño de Luz (Físico)",
    "Dark DMG (PHY)": "Daño de Oscuridad (Físico)",
    "Water DMG (MAG)": "Daño de Agua (Mágico)",
    "Fire DMG (MAG)": "Daño de Fuego (Mágico)",
    "Earth DMG (MAG)": "Daño de Tierra (Mágico)",
    "Light DMG (MAG)": "Daño de Luz (Mágico)",
    "Dark DMG (MAG)": "Daño de Oscuridad (Mágico)"
}

def traducir_habilidad(texto):
    if not texto: return "Sin descripción disponible."
    txt = str(texto)
    for en, es in DICCIONARIO_TRADUCCION.items():
        txt = txt.replace(en, es)
    return txt

@app.route("/", methods=["GET"]) 
def home(): 
    return "🤖 GSViewer Telegram Bot Server Activo y Listo!", 200

@app.route("/telegram-webhook", methods=["POST"]) 
def telegram_webhook(): 
    """Recibe los mensajes y clics en botones de la API de Telegram""" 
    data = request.get_json() or {}
    
    # 1. Manejar Botones Interactivos (Callback Query)
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        cb_data = cb.get("data", "")
        cb_id = cb.get("id")

        if chat_id and cb_data:
            procesar_callback_query(chat_id, cb_data, cb_id)
        return jsonify({"status": "ok"}), 200

    # 2. Manejar Mensajes de Texto
    msg_obj = data.get("message") or data.get("edited_message")
    if msg_obj:
        chat_id = msg_obj.get("chat", {}).get("id")
        texto = msg_obj.get("text", "").strip()

        if chat_id and texto:
            procesar_comando(chat_id, texto)

    return jsonify({"status": "ok"}), 200


def enviar_mensaje_telegram(chat_id, texto, reply_markup=None): 
    """Envía un mensaje de texto con opción a botones interactivos""" 
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" 
    payload = { 
        "chat_id": chat_id, 
        "text": texto, 
        "parse_mode": "Markdown", 
        "disable_web_page_preview": True 
    } 
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try: 
        requests.post(url, json=payload, timeout=5) 
    except Exception as e: 
        print(f"Error enviando mensaje a Telegram: {e}")


def enviar_foto_telegram(chat_id, photo_url, caption, reply_markup=None):
    """Envía la imagen HD del personaje o objeto junto con el texto y botones"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=8).json()
        if not res.get("ok"):
            # Fallback a texto simple si la URL de la imagen falla
            enviar_mensaje_telegram(chat_id, caption, reply_markup)
    except Exception as e:
        enviar_mensaje_telegram(chat_id, caption, reply_markup)


def responder_callback(cb_id, text=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": cb_id, "text": text}, timeout=3)
    except: pass


def procesar_comando(chat_id, texto): 
    texto_lower = texto.lower().strip()
    
    # Manejar menciones en grupos (/unidad@GSViewer_bot Chloe -> /unidad Chloe)
    if "@" in texto_lower:
        partes = texto_lower.split()
        if partes:
            cmd = partes[0].split("@")[0]
            texto_lower = " ".join([cmd] + partes[1:])

    # AYUDA / MENÚ
    if texto_lower in ["/start", "/help", "!ayuda", "hola", "menu"]:
        menu_text = (
            "⚔️ *BIENVENIDO AL AGENTE TÁCTICO INTELIGENTE GSVIEWER* ⚔️\n\n"
            "El Bot cuenta con acceso completo a las imágenes HD, habilidades traducidas, crestas y guías de la app:\n\n"
            "🔹 `/unidad [Nombre]` -> Ficha HD, Tier, Rol, Slots y Habilidades.\n"
            "🔹 `/equipo [Nombre]` -> Stats y habilidades de un Objeto/Equipamiento.\n"
            "🔹 `/guia [Misión]` -> Desglose de guías comunitarias de la app.\n"
            "🔹 `/foreversummons` -> Mejores unidades recomendadas para Forever Summons.\n"
            "🔹 `/sync` -> Sincronizar con la Wiki oficial de GS.\n\n"
            "💡 *Ejemplo*: `/unidad Shirou` o `/guia Dungeon 26`"
        )
        enviar_mensaje_telegram(chat_id, menu_text)
        return

    # BUSCAR UNIDAD
    if texto_lower.startswith("/unidad") or texto_lower.startswith("!unidad"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_unidad_perfil(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/unidad [Nombre de Héroe]` (Ejemplo: `/unidad Shirou`)")
        return

    # BUSCAR EQUIPAMIENTO
    if texto_lower.startswith("/equipo") or texto_lower.startswith("!equipo") or texto_lower.startswith("/objeto"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_objeto_perfil(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/equipo [Nombre de Objeto]` (Ejemplo: `/equipo True Flamboyance`)")
        return

    # BUSCAR GUÍA DE MISIÓN
    if texto_lower.startswith("/guia") or texto_lower.startswith("!guia"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_guia_mision(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/guia [Nombre de Misión o Boss]` (Ejemplo: `/guia Dungeon 26`)")
        return

    # FOREVER SUMMONS
    if texto_lower in ["/foreversummons", "/forever", "!foreversummons"]:
        enviar_forever_summons_rec(chat_id)
        return

    # SINCRONIZACIÓN AUTOMÁTICA CON LA WIKI
    if texto_lower in ["/sync", "!sync"]:
        if sync_global_info:
            try:
                ok = sync_global_info.sync_from_global_db(DICCIONARIOS_DIR)
                if ok:
                    p_count = len(cargar_personajes())
                    enviar_mensaje_telegram(chat_id, f"✅ *Sincronización Exitosa*: {p_count} héroes sincronizados con la Wiki oficial.")
                    return
                enviar_mensaje_telegram(chat_id, "⚠️ No se encontraron actualizaciones nuevas en la Wiki.")
                return
            except Exception as e:
                enviar_mensaje_telegram(chat_id, f"❌ Error en sincronización: {str(e)}")
                return
        enviar_mensaje_telegram(chat_id, "⚠️ Módulo de sincronización no disponible.")
        return

    enviar_mensaje_telegram(chat_id, "🤖 Comando no reconocido. Envía `/help` para ver la lista de comandos disponibles.")


def enviar_unidad_perfil(chat_id, nombre): 
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
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré a la unidad *'{nombre}'*. Verifica el nombre e intenta de nuevo.")
        return

    is_sa = coincidencia.get("is_sa", False) or coincidencia.get("isSA", False) or "Ascended" in coincidencia.get("tags", [])
    raza = coincidencia.get("raza", "N/A")
    if not raza or raza == "N/A":
        raza = coincidencia.get("race", "Humano")

    slots_list = coincidencia.get("slots", [])
    slots_txt = [f"  • {s.get('valor', '')} {s.get('tipo', '')}" for s in slots_list if isinstance(s, dict)]
    slots_str = "\n".join(slots_txt) if slots_txt else "  • No disponible"

    caption = (
        f"⚔️ *{coincidencia.get('nombre', 'Héroe').upper()}*\n"
        f"🌟 *Rareza*: {coincidencia.get('rareza', '★5')} | *Tier*: {coincidencia.get('tier', 'N/A')}\n"
        f"💧 *Elemento*: {coincidencia.get('elemento', 'N/A')} | *Raza*: {raza}\n"
        f"🛡️ *Rol*: {coincidencia.get('rol', 'N/A')}\n"
        f"✨ *SuperAwakening (SA)*: {'Sí (★6 SA)' if is_sa else 'No (★5)'}\n\n"
        f"🎒 *Slots de Equipamiento*:\n{slots_str}\n\n"
        f"🔮 *Crestas Recomendadas*: {coincidencia.get('crestRecom', 'ATK UP, Equip CT Speed')}\n\n"
        f"👇 *Toca los botones para ver las habilidades traducidas*:"
    )

    # Botones Interactivos
    u_id = coincidencia.get("id", "")
    buttons = {
        "inline_keyboard": [
            [
                {"text": "🗡️ Skill Set Traducido", "callback_data": f"sk_{u_id}"},
                {"text": "📊 Arts Gen Group", "callback_data": f"ag_{u_id}"}
            ]
        ]
    }

    img_photo = coincidencia.get("imagen_full") or coincidencia.get("imagen_url")
    if img_photo:
        enviar_foto_telegram(chat_id, img_photo, caption, buttons)
    else:
        enviar_mensaje_telegram(chat_id, caption, buttons)


def procesar_callback_query(chat_id, cb_data, cb_id):
    unidades = cargar_personajes()
    
    if cb_data.startswith("sk_"):
        u_id = cb_data[3:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            sk = coincidencia.get("skillset", {}) or {}
            skill_txt = traducir_habilidad(sk.get("skill", ""))
            arts_txt = traducir_habilidad(sk.get("arts", ""))
            ta_txt = traducir_habilidad(sk.get("truearts", ""))
            sa_txt = traducir_habilidad(sk.get("superarts", ""))

            skills_formatted = [
                f"⚔️ *HABILIDADES TRADUCIDAS: {coincidencia.get('nombre').upper()}*\n",
                f"🗡️ *Skill (CT)*:\n{skill_txt}\n",
                f"🔮 *Arts*:\n{arts_txt}\n",
                f"⚔️ *True Arts*:\n{ta_txt}\n"
            ]
            if sa_txt:
                skills_formatted.append(f"⚡ *Super Arts*:\n{sa_txt}\n")

            enviar_mensaje_telegram(chat_id, "\n".join(skills_formatted))
            responder_callback(cb_id, "Habilidades enviadas")
            return

    if cb_data.startswith("ag_"):
        u_id = cb_data[3:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            ag_type = coincidencia.get("arts_gen_type", "Ninguno / Desconocido")
            details = coincidencia.get("arts_gen_details", [])
            details_str = "\n".join([f"  • {d.get('source', 'Skill')}: {d.get('type', 'N/A')}" for d in details if isinstance(d, dict)])

            msg = (
                f"📊 *GRUPO DE ARTS GEN: {coincidencia.get('nombre').upper()}*\n\n"
                f"🏷️ *Grupo Principal*: Type {ag_type}\n"
                f"💡 *Compatibilidad*: Las unidades del mismo Grupo Type no apilan su recarga constante de Arts entre sí.\n\n"
                f"🔍 *Desglose*:\n{details_str if details_str else '  • Recarga instantánea o individual.'}"
            )
            enviar_mensaje_telegram(chat_id, msg)
            responder_callback(cb_id, "Arts Gen mostrado")
            return

    responder_callback(cb_id)


def enviar_objeto_perfil(chat_id, nombre):
    objetos = cargar_objetos()
    nombre_norm = nombre.lower()
    coincidencia = None

    for o in objetos:
        if not isinstance(o, dict): continue
        nom = o.get("nombre", "").lower()
        if nombre_norm in nom:
            coincidencia = o
            break

    if not coincidencia:
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré el equipamiento *'{nombre}'*.")
        return

    caption = (
        f"🛡️ *EQUIPAMIENTO: {coincidencia.get('nombre', 'Objeto').upper()}*\n"
        f"🌟 *Rareza*: {coincidencia.get('rareza', '★5')} | *Tipo*: {coincidencia.get('tipo', 'N/A')}\n"
        f"⏳ *CT / Cooldown*: {coincidencia.get('cooldown', 'N/A')}s\n\n"
        f"✨ *Efecto Traducido*:\n{traducir_habilidad(coincidencia.get('habilidad', 'Sin habilidad'))}\n\n"
        f"📍 *Fuente / Dónde Farmear*: {coincidencia.get('fuente', 'Gacha / Evento')}"
    )

    img = coincidencia.get("imagen_url")
    if img:
        enviar_foto_telegram(chat_id, img, caption)
    else:
        enviar_mensaje_telegram(chat_id, caption)


def enviar_guia_mision(chat_id, query):
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
            enviar_mensaje_telegram(chat_id, f"📜 No encontré guías comunitarias para *'{query}'*.")
            return

        g = filtradas[0]
        equipo_txt = []
        for idx, member in enumerate(g.get("equipo", [])):
            u_id = member.get("idUnidad", "Héroe")
            equipo_txt.append(f"  • Posición {idx+1}: {u_id}")

        msg = (
            f"⚔️ *GUÍA DE MISIÓN: {g.get('nombreMision')}*\n"
            f"👹 *Boss Target*: {g.get('jefe', 'N/A')}\n"
            f"👍 *Likes*: {g.get('likes', 0)} | 👎 *Dislikes*: {g.get('dislikes', 0)}\n\n"
            f"🛡️ *Formación*:\n" + "\n".join(equipo_txt) + "\n\n"
            f"📝 *Estrategia*:\n{g.get('estrategiaTexto', 'Sin estrategia escrita.')}\n\n"
            f"📱 *Abre GSViewer para ver la mesa táctica en HD.*"
        )
        enviar_mensaje_telegram(chat_id, msg)
    except Exception as e:
        enviar_mensaje_telegram(chat_id, f"❌ Error consultando guías: {str(e)}")


def enviar_forever_summons_rec(chat_id):
    unidades = cargar_personajes()
    top_units = [u for u in unidades if isinstance(u, dict) and u.get("tier") in ["S+", "SS", "SS+"]][:10]

    txt_list = []
    for idx, u in enumerate(top_units):
        txt_list.append(f"{idx+1}. *{u.get('nombre')}* ({u.get('elemento')}) - Tier {u.get('tier')}")

    msg = (
        "🔮 *MEJORES UNIDADES RECOMENDADAS PARA FOREVER SUMMONS* 🔮\n\n"
        "Si te sale alguna de estas unidades en Forever Summons, se recomienda encarecidamente *CONSERVAR*:\n\n" +
        "\n".join(txt_list) + "\n\n"
        "💡 *Consejo*: Mantenlas si no tienes un tanque de alto nivel o un generador de Arts principal."
    )
    enviar_mensaje_telegram(chat_id, msg)


if __name__ == "__main__": 
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host="0.0.0.0", port=port)
