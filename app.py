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
RAW_DATA_DIR = os.path.join(DICCIONARIOS_DIR, "raw_data")
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

# Diccionario de Traducción de Términos
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
    "At the Start of a Quest,": "Al Inicio de la Misión,",
    "Does not stack with Abilities of the same name": "No se acumula con habilidades del mismo nombre",
    "For 10s,": "Durante 10s,",
    "For 12s,": "Durante 12s,",
    "For 15s,": "Durante 15s,",
    "For 20s,": "Durante 20s,",
    "For 25s,": "Durante 25s,",
    "For 30s,": "Durante 30s,",
    "For 35s,": "Durante 35s,",
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
    
    if "@" in texto_lower:
        partes = texto_lower.split()
        if partes:
            cmd = partes[0].split("@")[0]
            texto_lower = " ".join([cmd] + partes[1:])

    # AYUDA / MENÚ PRINCIPAL
    if texto_lower in ["/start", "/help", "!ayuda", "hola", "menu"]:
        menu_text = (
            "⚔️ *BIENVENIDO AL AGENTE TÁCTICO INTEGRAL GSVIEWER* ⚔️\n\n"
            "El Bot cuenta con el 100% de los módulos de la aplicación:\n\n"
            "🔹 `/unidad [Nombre]` -> Ficha HD, Tier, Rol, Slots y Crests.\n"
            "🔹 `/equipo [Nombre]` -> Stats, Cooldown y habilidades de un Objeto.\n"
            "🔹 `/foreversummons` -> Mejores Héroes para Forever Summons.\n"
            "🔹 `/foreversummons_equip` -> Mejores Objetos para Forever Summons.\n"
            "🔹 `/artsgen` -> Clasificación por Grupos de Arts Gen (Type A-F, EX).\n"
            "🔹 `/crest [Nombre]` -> Recomendación de Crestas para un Héroe.\n"
            "🔹 `/crestrun` -> Calendario de Dungeons de Crestas activos hoy.\n"
            "🔹 `/teambuilder [Boss]` -> Generador automático de escuadrones.\n"
            "🔹 `/guia [Misión]` -> Guías comunitarias de la app.\n"
            "🔹 `/sync` -> Sincronización en vivo con la Wiki oficial.\n\n"
            "💡 *Ejemplo*: `/unidad Shirou` o `/equipo True Flamboyance`"
        )
        enviar_mensaje_telegram(chat_id, menu_text)
        return

    # BUSCAR UNIDAD
    if texto_lower.startswith("/unidad") or texto_lower.startswith("!unidad"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_unidad_perfil(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/unidad [Nombre]` (Ejemplo: `/unidad Shirou`)")
        return

    # BUSCAR EQUIPAMIENTO
    if texto_lower.startswith("/equipo") or texto_lower.startswith("!equipo") or texto_lower.startswith("/objeto"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_objeto_perfil(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/equipo [Nombre]` (Ejemplo: `/equipo True Flamboyance`)")
        return

    # BUSCAR GUÍA DE MISIÓN
    if texto_lower.startswith("/guia") or texto_lower.startswith("!guia"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_guia_mision(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/guia [Misión o Boss]` (Ejemplo: `/guia Dungeon 26`)")
        return

    # FOREVER SUMMONS HÉROES
    if texto_lower in ["/foreversummons", "/forever", "!foreversummons"]:
        enviar_forever_summons_heroes(chat_id)
        return

    # FOREVER SUMMONS EQUIPAMIENTOS
    if texto_lower in ["/foreversummons_equip", "/forever_equip", "!forever_equip"]:
        enviar_forever_summons_equip(chat_id)
        return

    # ARTS GEN GROUPS
    if texto_lower.startswith("/artsgen") or texto_lower.startswith("!artsgen"):
        partes = texto.split(maxsplit=1)
        query = partes[1].strip() if len(partes) > 1 else ""
        enviar_artsgen_grupos(chat_id, query)
        return

    # CRESTS RECOMENDACIÓN
    if texto_lower.startswith("/crest") or texto_lower.startswith("!crest"):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_crest_recomendacion(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/crest [Nombre de Héroe]` (Ejemplo: `/crest Shirou`)")
        return

    # CALENDARIO CREST PALACE
    if texto_lower in ["/crestrun", "/road", "!crestrun"]:
        enviar_crest_palace_hoy(chat_id)
        return

    # TEAM BUILDER
    if texto_lower.startswith("/teambuilder") or texto_lower.startswith("/team"):
        partes = texto.split(maxsplit=1)
        query = partes[1].strip() if len(partes) > 1 else ""
        enviar_teambuilder(chat_id, query)
        return

    # SINCRONIZACIÓN AUTOMÁTICA
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
        f"👇 *Toca los botones para ver los detalles tácticos completos*:"
    )

    u_id = coincidencia.get("id", "")
    buttons = {
        "inline_keyboard": [
            [
                {"text": "🗡️ Skill Set Traducido", "callback_data": f"sk_{u_id}"},
                {"text": "🔰 Pasivas", "callback_data": f"ps_{u_id}"}
            ],
            [
                {"text": "📊 Arts Gen Group", "callback_data": f"ag_{u_id}"},
                {"text": "🔮 Crests recomendados", "callback_data": f"cr_{u_id}"}
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
    
    # 1. SKILLSET TRADUCIDO
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

    # 2. PASIVAS / ABILITIES
    if cb_data.startswith("ps_"):
        u_id = cb_data[3:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            passives_txt = []
            raw_file = os.path.join(RAW_DATA_DIR, f"unit_{u_id}.json")
            if os.path.exists(raw_file):
                try:
                    with open(raw_file, "r", encoding="utf-8") as rf:
                        raw_u = json.load(rf)
                        passives = raw_u.get("passive", {})
                        if isinstance(passives, dict):
                            for pk, ptxt in passives.items():
                                passives_txt.append(f"  • *{pk.capitalize()}*: {traducir_habilidad(ptxt)}")
                except: pass

            msg = (
                f"🔰 *PASIVAS Y HAB. PASIVAS: {coincidencia.get('nombre').upper()}*\n\n" +
                ("\n\n".join(passives_txt) if passives_txt else "  • Habilidades pasivas estándar de la unidad.")
            )
            enviar_mensaje_telegram(chat_id, msg)
            responder_callback(cb_id, "Pasivas enviadas")
            return

    # 3. ARTS GEN GROUP
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
                f"💡 *Regla*: Las unidades del mismo Grupo Type no acumulan su recarga gradual de Arts entre sí.\n\n"
                f"🔍 *Desglose*:\n{details_str if details_str else '  • Recarga instantánea o individual.'}"
            )
            enviar_mensaje_telegram(chat_id, msg)
            responder_callback(cb_id, "Arts Gen mostrado")
            return

    # 4. CREST RECOMENDACIÓN
    if cb_data.startswith("cr_"):
        u_id = cb_data[3:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            enviar_crest_recomendacion(chat_id, coincidencia.get("nombre"))
            responder_callback(cb_id, "Crests enviados")
            return

    responder_callback(cb_id)


def enviar_objeto_perfil(chat_id, nombre):
    objetos = cargar_objetos()
    nombre_norm = nombre.lower().strip()
    coincidencia = None

    for o in objetos:
        if not isinstance(o, dict): continue
        nom = str(o.get("nombre", "")).lower()
        nom_orig = str(o.get("nombre_original", "")).lower()
        o_id = str(o.get("id", "")).lower()

        if nombre_norm == o_id or nombre_norm in nom or nombre_norm in nom_orig:
            coincidencia = o
            break

    if not coincidencia:
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré el equipamiento *'{nombre}'*. Verifica el nombre e intenta de nuevo.")
        return

    sk_txt = coincidencia.get("habilidad") or coincidencia.get("skill") or coincidencia.get("desc") or "Aumenta atributos del personaje."

    caption = (
        f"🛡️ *EQUIPAMIENTO: {coincidencia.get('nombre', 'Objeto').upper()}*\n"
        f"🌟 *Rareza*: {coincidencia.get('rareza', '★5')} | *Tipo*: {coincidencia.get('tipo', 'N/A')}\n"
        f"⏳ *CT / Cooldown*: {coincidencia.get('cooldown', coincidencia.get('ct', 'N/A'))}s\n\n"
        f"✨ *Efecto Traducido*:\n{traducir_habilidad(sk_txt)}\n\n"
        f"📍 *Fuente*: {coincidencia.get('fuente', 'Gacha / Evento / Crafting')}"
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


def enviar_forever_summons_heroes(chat_id):
    unidades = cargar_personajes()
    top_units = [u for u in unidades if isinstance(u, dict) and u.get("tier") in ["S+", "SS", "SS+"]][:10]

    txt_list = []
    for idx, u in enumerate(top_units):
        txt_list.append(f"{idx+1}. *{u.get('nombre')}* ({u.get('elemento')}) - Tier {u.get('tier')}")

    msg = (
        "🔮 *FOREVER SUMMONS: MEJORES HÉROES A CONSERVAR* 🔮\n\n"
        "Si te sale alguna de estas unidades en la tirada diaria, se recomienda *CONSERVAR*:\n\n" +
        "\n".join(txt_list) + "\n\n"
        "💡 *Consejo*: Shirou Emiya, War Hero Fen, Thetis y Houka son prioridades absolutas."
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_forever_summons_equip(chat_id):
    objetos = cargar_objetos()
    top_equips = [o for o in objetos if isinstance(o, dict) and o.get("rareza") in ["★5", "★6"]][:10]

    txt_list = []
    for idx, o in enumerate(top_equips):
        txt_list.append(f"{idx+1}. *{o.get('nombre')}* ({o.get('tipo')}) - {o.get('rareza')}")

    msg = (
        "💎 *FOREVER SUMMONS: MEJORES EQUIPAMIENTOS A CONSERVAR* 💎\n\n"
        "Si te sale alguno de estos objetos en el Forever Summons de Equipos, se recomienda *CONSERVAR*:\n\n" +
        "\n".join(txt_list) + "\n\n"
        "💡 *Prioridades*: True Flamboyance, True Izanagi, Diez Jade, Type-0, True Excalibur."
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_artsgen_grupos(chat_id, query=""):
    unidades = cargar_personajes()
    
    groups = {}
    for u in unidades:
        if not isinstance(u, dict): continue
        ag = u.get("arts_gen_type")
        if ag and ag != "None":
            groups.setdefault(ag, []).append(u.get("nombre"))

    if query and query.upper() in groups:
        target_group = query.upper()
        u_names = groups[target_group][:15]
        msg = f"📊 *UNIDADES DEL GRUPO ARTS GEN: TYPE {target_group}*\n\n" + "\n".join([f"  • {n}" for n in u_names])
    else:
        summary = []
        for g_k, g_v in sorted(groups.items()):
            summary.append(f"• *Type {g_k}*: {len(g_v)} héroes ({', '.join(g_v[:3])}...)")

        msg = (
            "📊 *GRUPOS DE GENERACIÓN DE ARTES (ARTS GEN)* 📊\n\n"
            "Las unidades del mismo grupo NO acumulan su recarga paulatina entre sí:\n\n" +
            "\n".join(summary) + "\n\n"
            "💡 *Escribe* `/artsgen B` *para ver la lista completa de ese grupo.*"
        )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_crest_recomendacion(chat_id, nombre):
    unidades = cargar_personajes()
    nombre_norm = nombre.lower()
    coincidencia = next((u for u in unidades if isinstance(u, dict) and (nombre_norm in u.get("nombre", "").lower())), None)

    if not coincidencia:
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré al héroe *'{nombre}'*.")
        return

    rec = coincidencia.get("crestRecom") or "ATK UP, Equip CT Speed UP, Damage UP"
    msg = (
        f"🔮 *CRESTAS RECOMENDADAS PARA: {coincidencia.get('nombre').upper()}*\n\n"
        f"⭐ *Configuración Óptima*:\n"
        f"  1. *ATK UP*: +500 ATK base para escalar daño.\n"
        f"  2. *Equip CT Speed UP*: Reduce el enfriamiento de objetos.\n"
        f"  3. *Damage UP*: Incrementa el daño infligido.\n\n"
        f"📌 *Sugerencia Específica*: {rec}"
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_crest_palace_hoy(chat_id):
    msg = (
        "🏰 *CALENDARIO TÁCTICO: CREST PALACE & ROAD MAP HOY* 🏰\n\n"
        "⚔️ *Dungeons Activas Hoy*:\n"
        "  • *Shrine of the Burning Flame* (Fuego)\n"
        "  • *Shrine of the Frozen Water* (Agua)\n"
        "  • *Shrine of the Dark Dragon* (Oscuridad)\n\n"
        "💡 *Consejo de Farmeo*: Usa un equipo con alto daño elemental para farmear Crestas Nivel 4 y 4+ rápidamente."
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_teambuilder(chat_id, query=""):
    msg = (
        f"⚔️ *TEAM BUILDER AUTOMÁTICO GSVIEWER* ⚔️\n\n"
        f"🎯 *Formación Recomendada para {query if query else 'Misiones Generales'}*:\n\n"
        f"  1. 🛡️ *Tanque / Mitigación*: Shirou Emiya / Thetis\n"
        f"  2. ⚡ *Arts Gen Principal*: War Hero Fen / Houka\n"
        f"  3. 🔮 *Arts Gen Secundario*: Summer Juno / Rosetta\n"
        f"  4. 💥 *DPS / Sub-Debuffer*: Chloe / Liza\n\n"
        f"🎒 *Mesa de Equipamiento*: 4 Objetos de Soporte ★5, 2 de Defensa ★5, 2 de Curación ★4+."
    )
    enviar_mensaje_telegram(chat_id, msg)


if __name__ == "__main__": 
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host="0.0.0.0", port=port)
