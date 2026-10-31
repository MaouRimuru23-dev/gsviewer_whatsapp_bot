import os 
import json 
import re
import time
from datetime import datetime, timezone, timedelta
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

# Cache en Memoria para Sesiones de TeamBuilder (Garantiza callback_data < 64 bytes)
TEAMBUILDER_SESSIONS = {}

def registrar_comandos_telegram():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    commands = [
        {"command": "unidad", "description": "Info, Tier, Rol, Slots y Habilidades (Dream/SA)"},
        {"command": "equipo", "description": "Stats y habilidad traducida de un Equipamiento"},
        {"command": "guia", "description": "Guías comunitarias de misiones y jefes"},
        {"command": "foreversummons", "description": "Pool Oficial y Héroes para Forever Summons"},
        {"command": "foreversummons_equip", "description": "Pool Oficial y Objetos para Forever Summons"},
        {"command": "artsgen", "description": "Grupos completos de Arts Gen (Type A-F, EX)"},
        {"command": "crest", "description": "Crestas recomendadas para un Héroe"},
        {"command": "crestrun", "description": "Palacios de Crestas & Summoner's Road Activos Hoy"},
        {"command": "teambuilder", "description": "Analizador de compatibilidad de 4 héroes"},
        {"command": "sync", "description": "Sincronizar con la Wiki oficial de GS"},
        {"command": "help", "description": "Menú principal de ayuda y comandos"}
    ]
    try:
        requests.post(url, json={"commands": commands}, timeout=5)
    except Exception as e:
        print(f"Error registrando comandos de Telegram: {e}")

registrar_comandos_telegram()

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

# Diccionario de Traducción
DICCIONARIO_TRADUCCION = {
    "When Equipped by": "Cuando lo equipa",
    "increases own DMG by": "aumenta el Daño propio en",
    "increases HP by": "aumenta la Vida (HP) en",
    "and negates Paralyze, Freeze, and Seal": "e inmuniza contra Parálisis, Congelación y Sellado",
    "Increases DEF by": "Aumenta la DEF en",
    "when unit is negating DMG": "mientras la unidad niega daño",
    "Increase own Arts by": "Aumenta sus propias Artes en",
    "Increase all Allies' Arts by": "Aumenta las Artes de todos los Aliados en",
    "Increase allies' Arts by": "Aumenta las Artes de los aliados en",
    "DMG barrier that negates": "Barrera de daño que anula",
    "Reduce Enemies' PHY RES by": "Reduce la Res. Física de los enemigos en",
    "Reduce Enemies' MAG RES by": "Reduce la Res. Mágica de los enemigos en",
    "Increase own ATK & DMG Up by": "Aumenta el ATK y Daño propio en",
    "Increase own ATK by": "Aumenta el ATK propio en",
    "Increase allies' DMG Up by": "Aumenta el Daño de los aliados en",
    "Increase own CRI rate by": "Aumenta la Tasa Crítica propia en",
    "Increase own DMG against Earth enemies by": "Aumenta el Daño propio contra enemigos de Tierra en",
    "when HP is 80% or above": "cuando la HP es 80% o superior",
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

# CALENDARIO COMPLETO Y EXACTO DE CREST PALACES Y SUMMONER'S ROAD DE LA APP (MissionsRepository.kt)
CALENDARIO_COMPLETO_PALACES = {
    0: { # Lunes
        "dia": "Lunes",
        "palaces": [
            {"nombre": "Shrine of Oblivion", "boss": "Oldeus", "dif": "PRO", "mech": "Solo recibe daño en Break. Killer de Luz (400%). Inmune a Oscuridad.", "mvp": "Est, Duke, Platina Asc."},
            {"nombre": "Shrine of Perdition", "boss": "Valzandeth", "dif": "PRO", "mech": "Grangarrod (Veneno) y Cyclops (Ceguera). Inmune a Reflejo.", "mvp": "Taunt Tank, Limpieza de Estados."}
        ],
        "road": "SR Oscuridad (Sinflow Cavern)"
    },
    1: { # Martes
        "dia": "Martes",
        "palaces": [
            {"nombre": "Shrine of the Crimson Sea", "boss": "Ignis", "dif": "EXTREME", "mech": "Stance de fuego. Nuke masivo en cada barra de HP.", "mvp": "Duran + Goblin Dagger, Thetis, Kirisame"},
            {"nombre": "Shrine of Burning Chains", "boss": "Ifrit", "dif": "PRO", "mech": "Nuke inicial (reduce HP a 15%). Quemadura pesada.", "mvp": "Cura Quemadura, Congelación"},
            {"nombre": "Shrine of Cinderplume (Nova)", "boss": "Flogassa", "dif": "NOVA", "mech": "Thresholds letales. Anti-Taunt y Anti-Curación.", "mvp": "Shirou, Sanstone, HK Roy"}
        ],
        "road": "SR Fuego (Flametail Mountain)"
    },
    2: { # Miércoles
        "dia": "Miércoles",
        "palaces": [
            {"nombre": "Shrine of Diamond Dust", "boss": "Freydal", "dif": "EXTREME", "mech": "Storm Mode (Alta Evasión). Reset de Skill CT.", "mvp": "Hajime Saito, Shion Santa, Saitama, Okarun"},
            {"nombre": "Shrine of Azul Knight", "boss": "Palamicia", "dif": "PRO", "mech": "Counter Stance. Killer de Humanos/Dioses.", "mvp": "Enfermedad, Arts/True Arts, No-Humano"},
            {"nombre": "Shrine of Frigidity (Nova)", "boss": "Aerugraxes", "dif": "NOVA", "mech": "Shield Killer. Congelación masiva y Evasión.", "mvp": "DR, Precisión Up, Shadow/Summer Chloe"}
        ],
        "road": "SR Agua (Frostsprite Tundra)"
    },
    3: { # Jueves
        "dia": "Jueves",
        "palaces": [
            {"nombre": "Shrine of Eternity", "boss": "Elpneumas", "dif": "EXTREME", "mech": "Se oculta bajo tierra. Negación de Agua y Magia.", "mvp": "Summer Miyu, Okarun, Konpaku Youmu"},
            {"nombre": "Shrine of Aberration", "boss": "Goldola", "dif": "PRO", "mech": "Veneno y Enfermedad pesados. Killer de Magia.", "mvp": "Limpieza de Estados, Físico, Fuego"}
        ],
        "road": "SR Tierra (Onyx Wood)"
    },
    4: { # Viernes
        "dia": "Viernes",
        "palaces": [
            {"nombre": "Shrine of Adamantine", "boss": "Fosradius", "dif": "PRO", "mech": "Inmune a Crítico (400% RES). Faintea y drena Artes.", "mvp": "Protección contra Parálisis + DPS Luz/Oscuridad"},
            {"nombre": "Shrine of Caliginosity (Nova)", "boss": "Dark Celia", "dif": "NOVA", "mech": "W3 Regulus, W4 Fina, Boss TA 'Endless' y Nuke Final.", "mvp": "Shirou, Chloe, Blessed Necklace"}
        ],
        "road": "SR Luz (Eternaglint Summit)"
    },
    5: { # Sábado
        "dia": "Sábado",
        "palaces": [
            {"nombre": "Shrine of the Cursed Claw", "boss": "Subject γ-2", "dif": "EXTREME", "mech": "Requiere múltiples Breaks. Congela al 50%/25% HP.", "mvp": "Chloe, Platina, Accelerator"},
            {"nombre": "Shrine of Whirlwind", "boss": "Belgiras", "dif": "PRO", "mech": "Daño capado a 1 si no está Envenenado.", "mvp": "Veneno Mandatorio, Fuego"}
        ],
        "road": "SR Celestial & Todos los Cursos Abiertos"
    },
    6: { # Domingo
        "dia": "Domingo",
        "palaces": [
            {"nombre": "Shrine of Discordia", "boss": "Subject B-3", "dif": "PRO", "mech": "Inmune a Magia (Daño 1). Grab / Faint a la unidad con más HP.", "mvp": "Okarun, War Hero Fen, Houka"},
            {"nombre": "Shrine of Tribulation", "boss": "Za'remnah", "dif": "PRO", "mech": "Phantasm Lock (Sella unidad hasta ser Breakeado).", "mvp": "Breaker, Ignorar DEF, Precisión Up"},
            {"nombre": "Shrine of Sagacity (Nova)", "boss": "Fongion", "dif": "NOVA", "mech": "Invulnerable a 50% HP hasta Break. Nuke masivo final.", "mvp": "Pencilgon, Chloe, Gamagori, Albedo"}
        ],
        "road": "SR Todos los Cursos Abiertos (Tierra, Fuego, Agua, Luz, Oscuridad)"
    }
}

@app.route("/", methods=["GET"]) 
def home(): 
    return "🤖 GSViewer Telegram Bot Server Activo y Listo!", 200

@app.route("/telegram-webhook", methods=["POST"]) 
def telegram_webhook(): 
    data = request.get_json() or {}
    
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        cb_data = cb.get("data", "")
        cb_id = cb.get("id")

        if chat_id and cb_data:
            procesar_callback_query(chat_id, cb_data, cb_id)
        return jsonify({"status": "ok"}), 200

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
    if texto_lower in ["/start", "/help", "!ayuda", "hola", "menu", "help", "ayuda"]:
        menu_text = (
            "⚔️ *BIENVENIDO AL AGENTE TÁCTICO INTEGRAL GSVIEWER* ⚔️\n\n"
            "Escribe la diagonal ( / ) para desplegar el menú autocompletado:\n\n"
            "🔹 `/unidad [Nombre]` -> Ficha HD, Tier, Rol, Slots y Habilidades (Dream/SA).\n"
            "🔹 `/equipo [Nombre]` -> Stats, Cooldown y habilidades traducidas.\n"
            "🔹 `/foreversummons` -> Pool Oficial de Héroes Forever Summons.\n"
            "🔹 `/foreversummons_equip` -> Pool Oficial de Objetos Forever Summons.\n"
            "🔹 `/artsgen [Grupo]` -> Lista COMPLETA por Grupos de Arts Gen (Type A-F).\n"
            "🔹 `/crest [Nombre]` -> Recomendación de Crestas para un Héroe.\n"
            "🔹 `/crestrun` -> Dungeons de Crestas & Summoner's Road Activos HOY.\n"
            "🔹 `/teambuilder [Héroe1, Héroe2, ...]` -> Analizador de Sinergia y Overlaps.\n"
            "🔹 `/guia [Misión]` -> Guías comunitarias de la app.\n"
            "🔹 `/sync` -> Sincronización en vivo con la Wiki oficial.\n\n"
            "💡 *Ejemplo*: `/teambuilder Shirou, WH Fen, Chloe, Thetis`"
        )
        enviar_mensaje_telegram(chat_id, menu_text)
        return

    # CALENDARIO CREST PALACE Y ROAD MAP HOY
    if texto_lower in ["/crestrun", "/road", "!crestrun", "crestrun"]:
        enviar_crest_palace_hoy(chat_id)
        return

    # BUSCAR UNIDAD
    if texto_lower.startswith("/unidad") or texto_lower.startswith("!unidad") or texto_lower.startswith("unidad "):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_unidad_perfil(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/unidad [Nombre]` (Ejemplo: `/unidad Fen` o `/unidad Shirou`)")
        return

    # BUSCAR EQUIPAMIENTO
    if texto_lower.startswith("/equipo") or texto_lower.startswith("!equipo") or texto_lower.startswith("/objeto") or texto_lower.startswith("equipo "):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_objeto_perfil(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/equipo [Nombre]` (Ejemplo: `/equipo True Flamboyance`)")
        return

    # BUSCAR GUÍA DE MISIÓN
    if texto_lower.startswith("/guia") or texto_lower.startswith("!guia") or texto_lower.startswith("guia "):
        partes = texto.split(maxsplit=1)
        if len(partes) > 1:
            enviar_guia_mision(chat_id, partes[1].strip())
            return
        enviar_mensaje_telegram(chat_id, "⚠️ Uso del comando: `/guia [Misión o Boss]` (Ejemplo: `/guia Dungeon 26`)")
        return

    # FOREVER SUMMONS HÉROES
    if texto_lower in ["/foreversummons", "/forever", "!foreversummons", "foreversummons"]:
        enviar_forever_summons_heroes(chat_id)
        return

    # FOREVER SUMMONS EQUIPAMIENTOS
    if texto_lower in ["/foreversummons_equip", "/forever_equip", "!forever_equip", "foreversummons_equip"]:
        enviar_forever_summons_equip(chat_id)
        return

    # ARTS GEN GROUPS
    if texto_lower.startswith("/artsgen") or texto_lower.startswith("!artsgen") or texto_lower.startswith("artsgen"):
        partes = texto.split(maxsplit=1)
        query = partes[1].strip() if len(partes) > 1 else ""
        enviar_artsgen_grupos(chat_id, query)
        return

    # CRESTS RECOMENDACIÓN
    if texto_lower.startswith("/crest") or texto_lower.startswith("!crest") or texto_lower.startswith("crest"):
        partes = texto.split(maxsplit=1)
        query = partes[1].strip() if len(partes) > 1 else ""
        enviar_crest_recomendacion(chat_id, query)
        return

    # TEAM BUILDER DE COMPATIBILIDAD
    if texto_lower.startswith("/teambuilder") or texto_lower.startswith("/team") or texto_lower.startswith("teambuilder"):
        partes = texto.split(maxsplit=1)
        query = partes[1].strip() if len(partes) > 1 else ""
        enviar_teambuilder_evaluador(chat_id, query)
        return

    # SINCRONIZACIÓN AUTOMÁTICA
    if texto_lower in ["/sync", "!sync", "sync"]:
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

    enviar_mensaje_telegram(chat_id, "🤖 Comando no reconocido. Escribe `/` para ver la lista de comandos disponibles.")


def enviar_unidad_perfil(chat_id, nombre): 
    unidades = cargar_personajes()
    nombre_norm = nombre.lower().strip()
    
    coincidencias = []
    for u in unidades:
        if not isinstance(u, dict): continue
        nom = u.get("nombre", "").lower()
        nom_orig = u.get("nombre_original", "").lower()
        if nombre_norm in nom or nombre_norm in nom_orig:
            coincidencias.append(u)

    if not coincidencias:
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré a la unidad *'{nombre}'*. Verifica el nombre e intenta de nuevo.")
        return

    # Manejo de Duplicados
    if len(coincidencias) > 1 and not any(nombre_norm == c.get("nombre", "").lower() for c in coincidencias):
        btn_rows = []
        txt_items = []
        for idx, c in enumerate(coincidencias[:6]):
            u_id = c.get("id", "")
            u_nom = c.get("nombre", "Héroe")
            txt_items.append(f"{idx+1}. *{u_nom}* ({c.get('elemento', '')}) - Tier {c.get('tier', 'N/A')}")
            btn_rows.append([{"text": f"⚔️ {u_nom}", "callback_data": f"selu_{u_id}"}])

        menu_txt = (
            f"🔍 *SE ENCONTRARON {len(coincidencias)} UNIDADES PARA '{nombre.upper()}':*\n\n" +
            "\n".join(txt_items) + "\n\n"
            "👇 *Toca el botón del héroe que deseas consultar*:"
        )
        enviar_mensaje_telegram(chat_id, menu_txt, {"inline_keyboard": btn_rows})
        return

    mostrar_detalle_unidad(chat_id, coincidencias[0])


def mostrar_detalle_unidad(chat_id, coincidencia):
    is_sa = coincidencia.get("is_sa", False) or coincidencia.get("isSA", False) or "Ascended" in coincidencia.get("tags", [])
    has_dream = coincidencia.get("has_dream", False) or "Dream Awakening" in coincidencia.get("tags", [])
    
    raza = coincidencia.get("raza", "N/A")
    if not raza or raza == "N/A":
        raza = coincidencia.get("race", "Humano")

    slots_list = coincidencia.get("slots", [])
    slots_txt = [f"  • {s.get('valor', '')} {s.get('tipo', '')}" for s in slots_list if isinstance(s, dict)]
    slots_str = "\n".join(slots_txt) if slots_txt else "  • No disponible"

    type_evo = "✨ SuperAwakening (★6 SA)" if is_sa else ("🌟 Dream Awakening (Evolución de Sueño)" if has_dream else "⭐ Awoken / ★5 Base")

    caption = (
        f"⚔️ *{coincidencia.get('nombre', 'Héroe').upper()}*\n"
        f"🌟 *Rareza*: {coincidencia.get('rareza', '★5')} | *Tier*: {coincidencia.get('tier', 'N/A')}\n"
        f"🔥 *Elemento*: {coincidencia.get('elemento', 'N/A')} | *Raza*: {raza}\n"
        f"🛡️ *Rol*: {coincidencia.get('rol', 'N/A')}\n"
        f"🔮 *Evolución*: {type_evo}\n\n"
        f"🎒 *Slots de Equipamiento*:\n{slots_str}\n\n"
        f"🔮 *Crestas Recomendadas*: {coincidencia.get('crestRecom', 'ATK UP, Equip CT Speed')}\n\n"
        f"👇 *Toca los botones para ver los kits traducidos completos*:"
    )

    u_id = coincidencia.get("id", "")
    buttons = {
        "inline_keyboard": [
            [
                {"text": "🗡️ Skill Set (Arts/SA/Cross)", "callback_data": f"sk_{u_id}"},
                {"text": "🔰 Pasivas & Dream", "callback_data": f"ps_{u_id}"}
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
    
    # REEMPLAZO INTERACTIVO EN TEAMBUILDER
    if cb_data.startswith("tbswap|"):
        parts = cb_data.split("|")
        if len(parts) >= 4:
            u_id = parts[1]
            orig_term = parts[2]
            session_id = parts[3]
            orig_query = TEAMBUILDER_SESSIONS.get(session_id, "")

            coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
            if coincidencia and orig_query:
                new_name = coincidencia.get("nombre")
                nombres_list = [n.strip() for n in orig_query.split(",")]
                for idx, item in enumerate(nombres_list):
                    if item.lower() == orig_term.lower():
                        nombres_list[idx] = new_name
                updated_query = ", ".join(nombres_list)
                enviar_teambuilder_evaluador(chat_id, updated_query)
                responder_callback(cb_id, f"Escuadra actualizada con {new_name}")
                return

    # SELECCIÓN DE UNIDAD DESDE MENÚ DE DUPLICADOS
    if cb_data.startswith("selu_"):
        u_id = cb_data[5:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            mostrar_detalle_unidad(chat_id, coincidencia)
            responder_callback(cb_id, "Unidad cargada")
            return

    # SELECCIÓN DE OBJETO DESDE MENÚ DE DUPLICADOS
    if cb_data.startswith("selo_"):
        o_id = cb_data[5:]
        objetos = cargar_objetos()
        coincidencia = next((o for o in objetos if str(o.get("id")) == o_id), None)
        if coincidencia:
            mostrar_detalle_objeto(chat_id, coincidencia)
            responder_callback(cb_id, "Objeto cargado")
            return

    # SKILLSET TRADUCIDO COMPLETO
    if cb_data.startswith("sk_"):
        u_id = cb_data[3:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            sk = coincidencia.get("skillset", {}) or {}
            
            raw_file = os.path.join(RAW_DATA_DIR, f"unit_{u_id}.json")
            if os.path.exists(raw_file):
                try:
                    with open(raw_file, "r", encoding="utf-8") as rf:
                        raw_u = json.load(rf)
                        sk = raw_u.get("skillset", sk)
                except: pass

            skill_txt = traducir_habilidad(sk.get("skill", ""))
            arts_txt = traducir_habilidad(sk.get("arts", ""))
            ta_txt = traducir_habilidad(sk.get("truearts", ""))
            sa_txt = traducir_habilidad(sk.get("superarts", ""))
            cross_txt = traducir_habilidad(sk.get("crossarts", ""))
            pb_txt = traducir_habilidad(sk.get("phantombullet", ""))
            prot_txt = traducir_habilidad(sk.get("protagonize", ""))

            skills_formatted = [
                f"⚔️ *KIT DE HABILIDADES TRADUCIDO: {coincidencia.get('nombre').upper()}*\n",
                f"🗡️ *Skill (CT)*:\n{skill_txt}\n",
                f"🔮 *Arts*:\n{arts_txt}\n",
                f"⚔️ *True Arts*:\n{ta_txt}\n"
            ]
            if sa_txt:
                skills_formatted.append(f"⚡ *Super Arts (SA)*:\n{sa_txt}\n")
            if cross_txt:
                skills_formatted.append(f"❌ *Cross Arts*:\n{cross_txt}\n")
            if pb_txt:
                skills_formatted.append(f"💥 *Phantom Bullet*:\n{pb_txt}\n")
            if prot_txt:
                skills_formatted.append(f"🌟 *Protagonize Skill*:\n{prot_txt}\n")

            enviar_mensaje_telegram(chat_id, "\n".join(skills_formatted))
            responder_callback(cb_id, "Kit completo enviado")
            return

    # PASIVAS Y DREAM AWAKENING
    if cb_data.startswith("ps_"):
        u_id = cb_data[3:]
        coincidencia = next((u for u in unidades if str(u.get("id")) == u_id), None)
        if coincidencia:
            passives_txt = []
            dream_txt = []
            
            raw_file = os.path.join(RAW_DATA_DIR, f"unit_{u_id}.json")
            if os.path.exists(raw_file):
                try:
                    with open(raw_file, "r", encoding="utf-8") as rf:
                        raw_u = json.load(rf)
                        passives = raw_u.get("passive", {})
                        if isinstance(passives, dict):
                            for pk, ptxt in passives.items():
                                if ptxt: passives_txt.append(f"  • *{pk.capitalize()}*: {traducir_habilidad(ptxt)}")

                        dream_data = raw_u.get("dream") or raw_u.get("dreamGL") or raw_u.get("dreamJP")
                        if isinstance(dream_data, dict):
                            for d_path, d_info in dream_data.items():
                                if isinstance(d_info, dict):
                                    d_pass = d_info.get("passive", {})
                                    for dpk, dptxt in d_pass.items():
                                        if dptxt: dream_txt.append(f"  • *Evolución de Sueño ({d_path.capitalize()})*: {traducir_habilidad(dptxt)}")
                except: pass

            msg = [f"🔰 *PASIVAS Y DREAM AWAKENING: {coincidencia.get('nombre').upper()}*\n"]
            if passives_txt:
                msg.append("*Habilidades Pasivas*:\n" + "\n".join(passives_txt) + "\n")
            if dream_txt:
                msg.append("🌟 *Ramas de Dream Awakening (Evolución de Sueño)*:\n" + "\n".join(dream_txt) + "\n")
            if not passives_txt and not dream_txt:
                msg.append("  • Habilidades pasivas estándar de la unidad.")

            enviar_mensaje_telegram(chat_id, "\n".join(msg))
            responder_callback(cb_id, "Pasivas y Dream enviadas")
            return

    # ARTS GEN GROUP
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
                f"💡 *Regla*: Las unidades del mismo Grupo Type no acumulan su recarga paulatina entre sí.\n\n"
                f"🔍 *Desglose*:\n{details_str if details_str else '  • Recarga instantánea o individual.'}"
            )
            enviar_mensaje_telegram(chat_id, msg)
            responder_callback(cb_id, "Arts Gen mostrado")
            return

    # CREST RECOMENDACIÓN
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
    
    coincidencias = []
    for o in objetos:
        if not isinstance(o, dict): continue
        nom = str(o.get("nombre", "")).lower()
        nom_orig = str(o.get("nombre_original", "")).lower()
        o_id = str(o.get("id", "")).lower()

        if nombre_norm == o_id or nombre_norm in nom or nombre_norm in nom_orig:
            coincidencias.append(o)

    if not coincidencias:
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré el equipamiento *'{nombre}'*. Verifica el nombre e intenta de nuevo.")
        return

    # Si hay múltiples objetos coincidentes
    if len(coincidencias) > 1 and not any(nombre_norm == c.get("nombre", "").lower() for c in coincidencias):
        btn_rows = []
        txt_items = []
        for idx, c in enumerate(coincidencias[:6]):
            o_id = c.get("id", "")
            o_nom = c.get("nombre", "Objeto")
            txt_items.append(f"{idx+1}. *{o_nom}* ({c.get('tipo', 'Equip')} - {c.get('rareza', '★5')})")
            btn_rows.append([{"text": f"🛡️ {o_nom}", "callback_data": f"selo_{o_id}"}])

        menu_txt = (
            f"🔍 *SE ENCONTRARON {len(coincidencias)} EQUIPAMIENTOS PARA '{nombre.upper()}':*\n\n" +
            "\n".join(txt_items) + "\n\n"
            "👇 *Toca el botón del objeto que deseas consultar*:"
        )
        enviar_mensaje_telegram(chat_id, menu_txt, {"inline_keyboard": btn_rows})
        return

    mostrar_detalle_objeto(chat_id, coincidencias[0])


def mostrar_detalle_objeto(chat_id, coincidencia):
    o_id = str(coincidencia.get("id", ""))
    raw_f = os.path.join(RAW_DATA_DIR, f"equip_{o_id}.json")
    
    skill_txt = ""
    ct_val = "N/A"
    passives_txt = []
    stats_txt = ""

    if os.path.exists(raw_f):
        try:
            with open(raw_f, "r", encoding="utf-8") as rf:
                raw_eq = json.load(rf)
                
                # Skillset
                sk = raw_eq.get("skillset", {}) or {}
                if isinstance(sk, dict):
                    skill_txt = sk.get("skill", "")
                    ct_val = str(sk.get("ct", "N/A"))
                
                # Passives
                passives = raw_eq.get("passive", {}) or {}
                if isinstance(passives, dict):
                    for pk, ptxt in passives.items():
                        passives_txt.append(f"  • *{pk.capitalize()}*: {traducir_habilidad(ptxt)}")
                
                # Stats
                st = raw_eq.get("stats", {}) or {}
                if isinstance(st, dict):
                    stats_txt = f"HP: +{st.get('hp', 0)} | ATK: +{st.get('atk', 0)} | DEF: +{st.get('def', 0)}"
        except: pass

    if not skill_txt:
        skill_txt = coincidencia.get("habilidad") or coincidencia.get("skill") or "Aumenta atributos del personaje."

    caption = (
        f"🛡️ *EQUIPAMIENTO: {coincidencia.get('nombre', 'Objeto').upper()}*\n"
        f"🌟 *Rareza*: {coincidencia.get('rareza', '★5')} | *Tipo*: {coincidencia.get('tipo', 'N/A')}\n"
        f"⏳ *CT / Cooldown*: {ct_val}s | *Stats*: {stats_txt if stats_txt else 'N/A'}\n\n"
        f"✨ *Efecto Traducido*:\n{traducir_habilidad(skill_txt)}\n\n" +
        (f"🔰 *Pasivas del Objeto*:\n" + "\n".join(passives_txt) + "\n\n" if passives_txt else "") +
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
            msg_fallback = (
                f"📜 *No se encontraron guías registradas para '{query}'.*\n\n"
                f"💡 *¡Aporta tu granito de arena a la comunidad y sube tu guía en la app de GSViewer!*"
            )
            enviar_mensaje_telegram(chat_id, msg_fallback)
            return

        g = filtradas[0]
        unidades_db = cargar_personajes()
        objetos_db = cargar_objetos()
        equipo_txt = []

        for idx, member in enumerate(g.get("equipo", [])):
            u_id = str(member.get("idUnidad", "Héroe"))
            u_match = next((u for u in unidades_db if str(u.get("id")) == u_id or str(u.get("nombre")).lower() == u_id.lower()), None)
            u_nombre = u_match.get("nombre") if u_match else f"Héroe #{u_id}"

            eq_names = []
            for eq_id in member.get("equipos", []):
                if not eq_id: continue
                eq_str = str(eq_id)
                eq_m = next((o.get("nombre") for o in objetos_db if str(o.get("id")) == eq_str or str(o.get("nombre")).lower() == eq_str.lower()), eq_str)
                if eq_m: eq_names.append(eq_m)

            eq_suffix = f" [{', '.join(eq_names)}]" if eq_names else ""
            equipo_txt.append(f"  • Posición {idx+1}: *{u_nombre}*{eq_suffix}")

        msg = (
            f"⚔️ *GUÍA DE MISIÓN: {g.get('nombreMision')}*\n"
            f"👹 *Boss Target*: {g.get('jefe', 'N/A')}\n"
            f"👍 *Likes*: {g.get('likes', 0)} | 👎 *Dislikes*: {g.get('dislikes', 0)}\n\n"
            f"🛡️ *Formación Táctica*:\n" + "\n".join(equipo_txt) + "\n\n"
            f"📝 *Estrategia Táctica*:\n{g.get('estrategiaTexto', 'Sin estrategia escrita.')}\n\n"
            f"📱 *Abre GSViewer para ver la mesa táctica en HD.*"
        )
        enviar_mensaje_telegram(chat_id, msg)
    except Exception as e:
        enviar_mensaje_telegram(chat_id, f"❌ Error consultando guías: {str(e)}")


def enviar_forever_summons_heroes(chat_id):
    tier1_IDs = {"265", "360", "361", "286", "190", "279", "364"}
    tier2_IDs = {"282", "291", "269", "237", "191", "207", "280", "274", "278", "261", "239", "283", "267"}
    tier3_IDs = {"363", "284", "275", "285", "292", "119", "289", "249", "214", "268", "266", "156", "243", "192"}

    unidades = cargar_personajes()
    fs_pool = []
    
    for u in unidades:
        if not isinstance(u, dict): continue
        href = str(u.get("href", "")).rstrip("/")
        aid = href.split("/")[-1] if href else ""
        if aid in tier1_IDs or aid in tier2_IDs or aid in tier3_IDs or "FOREVER_POOL" in u.get("tags", []):
            fs_pool.append(u)

    if not fs_pool:
        fs_pool = [u for u in unidades if isinstance(u, dict) and u.get("tier") in ["S+", "SS", "SS+"]]

    top_units = fs_pool[:12]
    txt_list = []
    for idx, u in enumerate(top_units):
        txt_list.append(f"{idx+1}. *{u.get('nombre')}* ({u.get('elemento')}) - Tier {u.get('tier')}")

    msg = (
        "🔮 *FOREVER SUMMONS: POOL OFICIAL DEFINIDO EN LA APP* 🔮\n\n"
        "Esta es la lista oficial del Forever Summons de GSViewer. Si te sale alguna, se recomienda *CONSERVAR*:\n\n" +
        "\n".join(txt_list) + "\n\n"
        "💡 *TOP PRIORIDADES*:\n"
        "  • #1 *Hart*: Soporte definitivo, curador y acumulador de energía.\n"
        "  • #2 *War Hero Fen*: Batería masiva de Arts y sub-DPS.\n"
        "  • #3 *Kirisame*: Tanque supremo para sobrevivir al meta actual.\n"
        "  • #4 *Thetis*, *Shirou Emiya*, *Mizuki XII*, *Emperor*, *Hazuki*."
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_forever_summons_equip(chat_id):
    pool_nombres = [
        "Iris' Rolly-Frill Bikini", "Red-Nosed Roy Doll", "Little-Red-Riding Mira?!", "Ces' Wavy Frill", "Rayas' Sunny Aloha Shirt",
        "Fen's Aloha Shorts", "Santa Fen Doll", "Santa Liza (Seeking Wisdom)", "Liza's Pearly One-Piece", "Liza's Smart Skirt",
        "Feena's Devil Wings", "Charlotte's Pure Ruffles", "The Legend of Ganan", "Loving Snow Princess", "Ces' Sandy Blossom",
        "Emi's Smooth Streamline", "Rishley's Sunset Bikini", "Celia's Seashore Pareo",
        "True Flamboyance", "True Izanagi", "Diez Jade", "Type-0", "True Excalibur", "True Centurion", "True Raaz"
    ]

    objetos = cargar_objetos()
    top_equips = []
    for n in pool_nombres:
        matched = next((o for o in objetos if isinstance(o, dict) and (n.lower() in o.get("nombre", "").lower() or n.lower() in o.get("nombre_original", "").lower())), None)
        if matched and matched not in top_equips:
            top_equips.append(matched)

    if not top_equips:
        top_equips = [o for o in objetos if isinstance(o, dict) and o.get("rareza") in ["★5", "★6"]][:12]

    txt_list = []
    for idx, o in enumerate(top_equips[:12]):
        txt_list.append(f"{idx+1}. *{o.get('nombre')}* ({o.get('tipo', 'Equip')}) - {o.get('rareza', '★5')}")

    msg = (
        "💎 *FOREVER SUMMONS EQUIPAMIENTOS: POOL DEFINIDO EN LA APP* 💎\n\n"
        "Si te sale alguno de estos objetos en el Forever Summons de Equipos, se recomienda *CONSERVAR*:\n\n" +
        "\n".join(txt_list) + "\n\n"
        "💡 *Top Prioridades*: True Flamboyance, True Izanagi, Diez Jade, Type-0, True Excalibur, True Centurion."
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

    if query:
        target = query.upper()
        if target in groups:
            u_names = groups[target]
            msg = f"📊 *LISTA COMPLETA DE HÉROES EN GRUPO ARTS GEN: TYPE {target} ({len(u_names)} Unidades)*:\n\n" + "\n".join([f"  • {n}" for n in u_names])
            enviar_mensaje_telegram(chat_id, msg)
            return
        else:
            enviar_mensaje_telegram(chat_id, f"🔍 No se encontró el grupo Arts Gen *Type {target}*. Grupos disponibles: {', '.join(sorted(groups.keys()))}")
            return

    summary = []
    for g_k, g_v in sorted(groups.items()):
        summary.append(f"• *Type {g_k}* ({len(g_v)} héroes): Escribe `/artsgen {g_k}` para ver la lista completa.")

    msg = (
        "📊 *GRUPOS DE GENERACIÓN DE ARTES (ARTS GEN)* 📊\n\n"
        "Las unidades del mismo grupo NO acumulan su recarga paulatina entre sí:\n\n" +
        "\n".join(summary) + "\n\n"
        "💡 *Escribe* `/artsgen B` *para ver todos los personajes de ese grupo.*"
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_crest_recomendacion(chat_id, nombre=""):
    if not nombre:
        msg = (
            "🔮 *MÓDULO DE CRESTAS Y PALACIO DE CRESTAS* 🔮\n\n"
            "Usa el comando `/crest [Nombre]` para ver las crestas óptimas de un personaje.\n"
            "💡 *Ejemplo*: `/crest Shirou` o `/crest Fen`\n\n"
            "Escribe `/crestrun` para ver el Calendario Completo de Crest Palace."
        )
        enviar_mensaje_telegram(chat_id, msg)
        return

    unidades = cargar_personajes()
    nombre_norm = nombre.lower().strip()
    coincidencias = [u for u in unidades if isinstance(u, dict) and (nombre_norm in u.get("nombre", "").lower())]

    if not coincidencias:
        enviar_mensaje_telegram(chat_id, f"🔍 No encontré al héroe *'{nombre}'*.")
        return

    if len(coincidencias) > 1 and not any(nombre_norm == c.get("nombre", "").lower() for c in coincidencias):
        btn_rows = []
        txt_items = []
        for idx, c in enumerate(coincidencias[:6]):
            u_id = c.get("id", "")
            u_nom = c.get("nombre", "Héroe")
            txt_items.append(f"{idx+1}. *{u_nom}* ({c.get('elemento', '')})")
            btn_rows.append([{"text": f"🔮 {u_nom}", "callback_data": f"cr_{u_id}"}])

        menu_txt = (
            f"🔍 *SE ENCONTRARON {len(coincidencias)} HÉROES PARA '{nombre.upper()}':*\n\n" +
            "\n".join(txt_items) + "\n\n"
            "👇 *Toca el botón para ver sus Crestas Recomendadas*:"
        )
        enviar_mensaje_telegram(chat_id, menu_txt, {"inline_keyboard": btn_rows})
        return

    coincidencia = coincidencias[0]
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
    tz_latam = timezone(timedelta(hours=-6))
    weekday_today = datetime.now(tz_latam).weekday()
    
    info_today = CALENDARIO_COMPLETO_PALACES.get(weekday_today, CALENDARIO_COMPLETO_PALACES[0])

    palaces_list_txt = []
    for p in info_today["palaces"]:
        palaces_list_txt.append(
            f"📍 *Palacio*: {p['nombre']} [{p['dif']}]\n"
            f"👹 *Boss*: {p['boss']}\n"
            f"📝 *Mecánica*: {p['mech']}\n"
            f"🌟 *MVP*: {p['mvp']}\n"
        )

    msg = (
        f"🏰 *PALACIOS DE CRESTAS & SUMMONER'S ROAD ACTIVOS HOY ({info_today['dia'].upper()})* 🏰\n\n"
        f"⚔️ *PALACIOS DE CRESTAS ACTIVOS HOY*:\n" +
        "\n".join(palaces_list_txt) + "\n"
        f"🛤️ *SUMMONER'S ROAD ACTIVO HOY*:\n"
        f"  • *{info_today['road']}*\n\n"
        f"💡 *Regla del Líder*: La unidad en la posición 1 (Líder) es quien recibe el drop de la Cresta al ganar."
    )
    enviar_mensaje_telegram(chat_id, msg)


def enviar_teambuilder_evaluador(chat_id, query_unidades=""):
    if not query_unidades:
        msg = (
            "⚔️ *TEAM BUILDER: ANALIZADOR DE COMPATIBILIDAD (GSVIEWER)* ⚔️\n\n"
            "Ingresa los nombres de **2 a 4 héroes** (separados por coma) para evaluar su compatibilidad:\n"
            "💡 *Ejemplo*: `/teambuilder Shirou, WH Fen, Thetis, Chloe`\n\n"
            "El analizador verificará:\n"
            "  • ⚡ *Overlaps de Arts Gen* (Grupos Type A-F que no apilan).\n"
            "  • 🛡️ *Estructura de Roles* (Tanque, Batería, Buffer, DPS/Breaker).\n"
            "  • 🔥 *Sinergias de Elemento y Raza*.\n"
            "  • 📊 *Veredicto Táctico*: Qué funciona y qué NO funciona."
        )
        enviar_mensaje_telegram(chat_id, msg)
        return

    if "," in query_unidades:
        nombres = [n.strip() for n in query_unidades.split(",") if n.strip()]
    else:
        nombres = [n.strip() for n in query_unidades.split() if n.strip()]

    unidades_db = cargar_personajes()
    equipo_encontrado = []
    no_encontrados = []
    ambiguos = []

    for nom_input in nombres:
        nom_norm = nom_input.lower()
        matches = [u for u in unidades_db if isinstance(u, dict) and (nom_norm in u.get("nombre", "").lower() or nom_norm in u.get("nombre_original", "").lower())]
        
        if len(matches) == 1:
            if matches[0] not in equipo_encontrado:
                equipo_encontrado.append(matches[0])
        elif len(matches) > 1:
            exact = next((m for m in matches if nom_norm == m.get("nombre", "").lower()), None)
            if exact:
                if exact not in equipo_encontrado: equipo_encontrado.append(exact)
            else:
                ambiguos.append((nom_input, matches))
                equipo_encontrado.append(matches[0])
        else:
            no_encontrados.append(nom_input)

    # Crear Sesión Corta en Memoria para callback_data
    session_id = f"{chat_id}_{int(time.time())}"
    TEAMBUILDER_SESSIONS[session_id] = query_unidades

    # Si hay nombres ambiguos, generar botones para re-evaluar la escuadra
    btn_rows = []
    if ambiguos:
        for name_term, match_list in ambiguos[:2]:
            for m in match_list[:3]:
                u_id = str(m.get("id", ""))
                u_nom = m.get("nombre", "Héroe")
                cb_str = f"tbswap|{u_id}|{name_term}|{session_id}"
                btn_rows.append([{"text": f"⚔️ Cambiar a: {u_nom}", "callback_data": cb_str}])

    que_funciona = []
    que_no_funciona = []
    grupos_arts = {}

    # 1. Chequeo de Arts Gen Overlap
    for u in equipo_encontrado:
        ag = u.get("arts_gen_type", "None")
        if ag and ag != "None":
            grupos_arts.setdefault(ag, []).append(u.get("nombre"))

    for g_type, members in grupos_arts.items():
        if len(members) > 1:
            que_no_funciona.append(f"⚠️ *CONFLICTO DE ARTS GEN (Type {g_type})*: {', '.join(members)} pertenecen al mismo grupo y **NO acumulan su recarga constante de Arts entre sí**.")
        else:
            que_funciona.append(f"⚡ *Arts Gen Type {g_type}*: {members[0]} otorga energía constante sin conflictos.")

    # 2. Chequeo de Roles
    tanques = []
    baterias = []
    dps_breakers = []

    for u in equipo_encontrado:
        r = str(u.get("rol", "")).lower()
        t = str(u.get("tags", [])).lower()
        n = u.get("nombre")

        if "defensa" in r or "tanque" in r or "taunt" in t:
            tanques.append(n)
        if "soporte" in r or "batería" in t or u.get("arts_gen_type") != "None":
            baterias.append(n)
        if "ataque" in r or "dps" in r or "breaker" in r or "break" in t:
            dps_breakers.append(n)

    if tanques:
        que_funciona.append(f"🛡️ *Protección Defensiva*: {', '.join(tanques)} brinda mitigación/barreras para supervivencia.")
    else:
        que_no_funciona.append("⚠️ *Falta Tanque / Mitigación*: El equipo no cuenta con un tanque dedicado (Shirou/Kirisame/Thetis) para misiones de alto daño.")

    if baterias:
        que_funciona.append(f"🔋 *Generación de Artes*: {', '.join(baterias)} garantiza flujo constante de energía.")
    else:
        que_no_funciona.append("⚠️ *Falta Batería de Arts*: El equipo carece de un generador masivo de Arts (WH Fen/Hart/Houka/Liza).")

    if dps_breakers:
        que_funciona.append(f"💥 *Daño y Break*: {', '.join(dps_breakers)} aporta la potencia ofensiva del grupo.")

    elementos = [u.get("elemento") for u in equipo_encontrado if u.get("elemento")]
    if len(set(elementos)) == 1 and len(equipo_encontrado) >= 3:
        que_funciona.append(f"🔥 *Mono-Elemento ({elementos[0]})*: Gran sinergia para aprovechar buffers elementales del mismo elemento.")

    equipo_nombres_str = "\n".join([f"  • Posición {idx+1}: *{u.get('nombre')}* ({u.get('elemento')}) - Tier {u.get('tier', 'N/A')}" for idx, u in enumerate(equipo_encontrado)])

    msg = [
        f"⚔️ *ANALIZADOR DE ESQUADRÓN TEAM BUILDER ({len(equipo_encontrado)} Héroes)* ⚔️\n",
        f"🛡️ *Composición Evaluada*:\n{equipo_nombres_str}\n"
    ]

    if no_encontrados:
        msg.append(f"❓ *No encontrados*: {', '.join(no_encontrados)}\n")

    msg.append("✅ *LO QUE SÍ FUNCIONA (PUNTOS FUERTES)*:")
    if que_funciona:
        msg.append("\n".join([f"  • {f}" for f in que_funciona]))
    else:
        msg.append("  • Formación básica sin sinergias destacadas.")

    msg.append("\n⚠️ *LO QUE NO FUNCIONA (CONFLICTOS Y DÉFICITS)*:")
    if que_no_funciona:
        msg.append("\n".join([f"  • {nf}" for nf in que_no_funciona]))
    else:
        msg.append("  • ¡Excelente! No se detectaron conflictos de Arts Gen ni faltas de roles principales.")

    reply_markup = {"inline_keyboard": btn_rows} if btn_rows else None
    enviar_mensaje_telegram(chat_id, "\n".join(msg), reply_markup)


if __name__ == "__main__": 
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host="0.0.0.0", port=port)
