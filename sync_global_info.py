import requests
import json
import re
import os

def extract_global_tiers():
    url_js = "https://www.grandsummoners.info/static/js/main.5176f2c1.js"
    try:
        r = requests.get(url_js, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if r.status_code == 200:
            rank_map = {"1": "SSS", "2": "SS", "3": "S+", "4": "S", "5": "A+", "6": "A", "7": "B+", "8": "B", "9": "C+", "10": "C", "11": "D+", "12": "D", "13": "F"}
            matches = re.findall(r'id:(\d+),name:\"[^\"]+\",tags:\[[\d,]*\],tier:\{rank:(\d+)', r.text)
            res = {}
            for uid, rid in matches: res[str(uid)] = rank_map.get(str(rid), "N/A")
            return res
    except: pass
    return {}

def map_equip_type(type_path):
    if not type_path: return "Otros"
    tp = str(type_path).lower()
    if "heal" in tp: return "Curación"
    if "phys" in tp: return "Ataque Físico"
    if "mag" in tp: return "Ataque Mágico"
    if "def" in tp: return "Defensa"
    if "supp" in tp: return "Soporte"
    return "Otros"

def get_forever_summons_pool():
    """Pool oficial de Septiembre 2026."""
    tier1 = ["361", "360", "265", "286", "190", "279", "364"]
    tier2 = ["282", "291", "269", "237", "191", "207", "280", "274", "278", "261", "239", "283", "267"]
    tier3 = ["363", "284", "275", "285", "292", "119", "289", "249", "214", "268", "266", "156", "243", "192"]
    return tier1 + tier2 + tier3

def scan_unit_tags(unit_json, altema_tags=None):
    """Escanea descripciones en inglés buscando oraciones y frases reales de Grand Summoners DB."""
    tags = set()
    text_to_scan = json.dumps(unit_json.get('skillset', {})) + ' ' + json.dumps(unit_json.get('passive', {}))
    text_lower = text_to_scan.lower()

    if skillset := unit_json.get('skillset'):
        if 'superarts' in skillset or 'phantombullet' in skillset or 'crossarts' in skillset:
            tags.add('Ascended')
        else:
            tags.add('Awoken')

    # 1. ARTS GEN TYPES OFICIALES (Type A-I & Type EX1-EX3)
    if "arts gen is type" in text_lower:
        type_matches = re.findall(r"type\s+(ex[1-3]|[a-i])\b", text_lower, re.I)
        for tm in type_matches:
            tags.add(f"Type {tm.upper()}")

    # 2. PHYSICAL / MAGIC / DAMAGE INFLICTING UP
    if re.search(r"\bphy(?:sical)?\b.*\bdmg\b|\bdmg\b.*\bphy(?:sical)?\b", text_lower):
        tags.add("Physical DMG UP")
    if re.search(r"\bmag(?:ic)?\b.*\bdmg\b|\bdmg\b.*\bmag(?:ic)?\b", text_lower):
        tags.add("Magic DMG UP")
    if re.search(r"\bdmg\s*(?:up|by|\+|\d)", text_lower):
        tags.add("DMG Inflicting UP")

    # 3. CRÍTICOS (SUPER CRITICAL & CRITICAL RATE & DAMAGE & CRI RES)
    if re.search(r"\bsuper\s*cri(?:tical)?\s*rate\b", text_lower):
        tags.add("Super CRI Rate UP")
    if re.search(r"\bcri(?:tical)?\s*rate\b|100%\s*crit", text_lower):
        tags.add("CRI Rate UP")
    if re.search(r"\bcri(?:tical)?\s*dmg\b", text_lower):
        tags.add("CRI DMG UP")
    if re.search(r"\bcri(?:tical)?\s*res\s*(?:up|by|\+|\d)", text_lower):
        tags.add("CRI RES UP")

    # 4. DEFENSIVO: BARRIER / NEGATES DMG / DMG TAKEN DOWN / TAUNT / DMG DOWN
    if re.search(r"\bnegate[s]?\b.*\bdmg\b|\bbarrier\b|\bshield\b", text_lower):
        tags.add("Negates DMG")
    if re.search(r"\bdmg\s*res\b|\bdmg\s*taken\s*down\b|reduce.*\bdmg\s*taken\b", text_lower):
        tags.add("DMG Taken DOWN")
    if re.search(r"\bphy(?:sical)?\s*dmg\s*down\b|reduce.*\bphy(?:sical)?\s*dmg\b", text_lower):
        tags.add("Physical DMG DOWN")
    if re.search(r"\bmag(?:ic)?\s*dmg\s*down\b|reduce.*\bmag(?:ic)?\s*dmg\b", text_lower):
        tags.add("Magic DMG DOWN")
    if re.search(r"\btaunt\b|\bredirect\b", text_lower):
        tags.add("Taunting")

    # 5. RESISTENCIAS ELEMENTALES Y A ESTADOS (RES UP & RES DOWN EXHAUSTIVO + FRASES COMPUESTAS CON "AND", "&", "Y", ",")
    res_map = [
        # Element Resistance UP
        (r"increase.*fire\s*(?:elemental)?\s*resist|fire\s*(?:elemental)?\s*resist.*up|fire\s*(?:elemental)?\s*resist.*by", "Fire RES UP"),
        (r"increase.*water\s*(?:elemental)?\s*resist|water\s*(?:elemental)?\s*resist.*up|water\s*(?:elemental)?\s*resist.*by", "Water RES UP"),
        (r"increase.*earth\s*(?:elemental)?\s*resist|earth\s*(?:elemental)?\s*resist.*up|earth\s*(?:elemental)?\s*resist.*by", "Earth RES UP"),
        (r"increase.*light\s*(?:elemental)?\s*resist|light\s*(?:elemental)?\s*resist.*up|light\s*(?:elemental)?\s*resist.*by", "Light RES UP"),
        (r"increase.*dark\s*(?:elemental)?\s*resist|dark\s*(?:elemental)?\s*resist.*up|dark\s*(?:elemental)?\s*resist.*by", "Dark RES UP"),
        (r"increase.*status\s*(?:ailment)?\s*resist|status\s*(?:ailment)?\s*resist.*up|evade.*status\s*ailment", "Status RES UP"),

        # Status Ailment RES UP
        (r"burn\s*resist", "Burn RES UP"),
        (r"freeze\s*resist", "Freeze RES UP"),
        (r"paraly[sz]e?\s*resist", "Paralysis RES UP"),
        (r"poison\s*resist", "Poison RES UP"),
        (r"faint\s*resist", "Faint RES UP"),
        (r"blind\s*resist", "Blind RES UP"),
        (r"disease\s*resist", "Disease RES UP"),
        (r"seal\s*resist", "Seal RES UP"),

        # Element & Attack Resistance DOWN
        (r"reduce.*fire\s*(?:elemental)?\s*resist|fire\s*(?:elemental)?\s*resist.*down|lower.*fire\s*resist", "Fire RES DOWN"),
        (r"reduce.*water\s*(?:elemental)?\s*resist|water\s*(?:elemental)?\s*resist.*down|lower.*water\s*resist", "Water RES DOWN"),
        (r"reduce.*earth\s*(?:elemental)?\s*resist|earth\s*(?:elemental)?\s*resist.*down|lower.*earth\s*resist", "Earth RES DOWN"),
        (r"reduce.*light\s*(?:elemental)?\s*resist|light\s*(?:elemental)?\s*resist.*down|lower.*light\s*resist", "Light RES DOWN"),
        (r"reduce.*dark\s*(?:elemental)?\s*resist|dark\s*(?:elemental)?\s*resist.*down|lower.*dark\s*resist", "Dark RES DOWN"),
        (r"reduce.*phy(?:sical)?\s*resist|phy(?:sical)?\s*resist.*down", "Physical RES DOWN"),
        (r"reduce.*mag(?:ic)?\s*resist|mag(?:ic)?\s*resist.*down", "Magic RES DOWN"),
        (r"reduce.*dmg\s*resist|increase.*dmg\s*taken", "DMG Taken UP"),

        # Status Ailment Resistance DOWN
        (r"reduce.*status\s*(?:ailment)?\s*resist|status\s*(?:ailment)?\s*resist.*down", "Status RES DOWN"),
        (r"reduce.*burn\s*resist|burn\s*resist.*down", "Burn RES DOWN"),
        (r"reduce.*freeze\s*resist|freeze\s*resist.*down", "Freeze RES DOWN"),
        (r"reduce.*paraly[sz]e?\s*resist|paraly[sz]e?\s*resist.*down", "Paralysis RES DOWN"),
        (r"reduce.*poison\s*resist|poison\s*resist.*down", "Poison RES DOWN"),
        (r"reduce.*faint\s*resist|faint\s*resist.*down", "Faint RES DOWN"),
        (r"reduce.*blind\s*resist|blind\s*resist.*down", "Blind RES DOWN"),
        (r"reduce.*disease\s*resist|disease\s*resist.*down", "Disease RES DOWN"),
        (r"reduce.*seal\s*resist|seal\s*resist.*down", "Seal RES DOWN")
    ]
    for pattern, tag_name in res_map:
        if re.search(pattern, text_lower):
            tags.add(tag_name)

    # 5b. ESCANEO DE FRASES COMPUESTAS CON "AND", "&", "Y", "," (Ej: "Fire and Water Resistance UP")
    elems_comp = ['fire', 'water', 'earth', 'light', 'dark', 'physical', 'magic']
    statuses_comp = ['burn', 'freeze', 'paralysis', 'paralyze', 'poison', 'faint', 'blind', 'disease', 'seal', 'status']
    
    for match in re.finditer(r'(?:increase|reduce|lower|up|down|\b)\s*([a-z\s,&\-/]+?)\s*(?:elemental\s*)?res(?:ist(?:ance)?)?', text_lower):
        matched_str = match.group(1)
        full_match = match.group(0)
        is_down = 'reduce' in full_match or 'lower' in full_match or 'down' in full_match
        s_updown = 'DOWN' if is_down else 'UP'
        
        for e in elems_comp:
            if e in matched_str:
                e_label = 'Physical' if 'phy' in e else e.capitalize()
                tags.add(f'{e_label} RES {s_updown}')
        for s in statuses_comp:
            if s in matched_str:
                s_label = 'Paralysis' if 'paraly' in s else s.capitalize()
                tags.add(f'{s_label} RES {s_updown}')

    # 6. IGNORAR DEFENSA (IGNORE DEF) - 100% DE COBERTURA (59 UNIDADES OFICIALES)
    if re.search(r"\bignore[s]?\b.*\bdef\b", text_lower):
        tags.add("Ignore DEF")

    # 7. AUTO-FILLING ARTS GAUGE vs ARTS GAUGE UP (INSTANT)
    if re.search(r"arts\s*(?:gauge)?\s*by\s*\d+\s*/\s*s|arts\s*gauge\s*auto|gradually\s*fill", text_lower):
        tags.add("Auto-filling Arts Gauge")
    if re.search(r"increase.*arts\s*(?:gauge)?\s*by\s*\d+(?!\s*/\s*s)|arts\s*gauge\s*up", text_lower):
        tags.add("Arts Gauge UP")

    # 8. EQUIP CT SPEED BY SLOT (PHYSICAL, MAGIC, DEFENSE, SUPPORT, HEAL)
    if re.search(r"physical\s*equip\s*ct|phy\s*equip\s*ct", text_lower): tags.add("Physical Equip CT UP")
    if re.search(r"magic\s*equip\s*ct|mag\s*equip\s*ct", text_lower): tags.add("Magic Equip CT UP")
    if re.search(r"defense\s*equip\s*ct|def\s*equip\s*ct", text_lower): tags.add("Defense Equip CT UP")
    if re.search(r"support\s*equip\s*ct|supp?\s*equip\s*ct", text_lower): tags.add("Support Equip CT UP")
    if re.search(r"heal\s*equip\s*ct", text_lower): tags.add("Heal Equip CT UP")
    if re.search(r"equip\s*ct", text_lower): tags.add("Equip CT Speed UP")
    if re.search(r"skill\s*ct", text_lower): tags.add("Skill CT Speed UP")
    if re.search(r"shorten\s*ct|ct\s*speed", text_lower): tags.add("Shorten CT")

    # 9. RECOVERY / LIFESTEAL / REVIVE
    if re.search(r"hp\s*auto-recovery|recovery\s*by\s*\d+/s", text_lower): tags.add("HP Auto-Recovery")
    if re.search(r"lifesteal", text_lower): tags.add("Lifesteal")
    if re.search(r"revive", text_lower): tags.add("Revive Allies")
    if re.search(r"hp\s*recovery|heal", text_lower): tags.add("HP Recovery")

    # 10. SPECIES KILLERS
    killers = [
        (r"human\s*(?:enemies|killer)", "Human Killer"),
        (r"demon\s*(?:enemies|killer)", "Demon Killer"),
        (r"god\s*(?:enemies|killer)", "God Killer"),
        (r"dragon\s*(?:enemies|killer)", "Dragon Killer"),
        (r"beast\s*(?:enemies|killer)", "Beast Killer"),
        (r"machine\s*(?:enemies|killer)", "Machine Killer"),
        (r"spirit\s*(?:enemies|killer)", "Spirit Killer"),
        (r"giant\s*(?:boss(?:es)?|killer)", "Giant Killer")
    ]
    for pat, tag_name in killers:
        if re.search(pat, text_lower): tags.add(tag_name)

    # 11. ACCURACY & EVASION (UP & DOWN)
    if re.search(r"accuracy\s*up|increase.*accuracy", text_lower): tags.add("Accuracy UP")
    if re.search(r"accuracy\s*down|reduce.*accuracy|lower.*accuracy", text_lower): tags.add("Accuracy DOWN")
    if re.search(r"evasion\s*up|increase.*evasion", text_lower): tags.add("Evasion UP")
    if re.search(r"evasion\s*down|reduce.*evasion|lower.*evasion", text_lower): tags.add("Evasion DOWN")

    # 12. STATUS (ATK / DEF / HP UP & DOWN)
    if re.search(r"atk\s*up|increase.*atk", text_lower): tags.add("ATK UP")
    if re.search(r"atk\s*down|reduce.*atk|lower.*atk", text_lower): tags.add("ATK DOWN")
    if re.search(r"def\s*up|increase.*def", text_lower): tags.add("DEF UP")
    if re.search(r"def\s*down|reduce.*def|lower.*def", text_lower): tags.add("DEF DOWN")
    if re.search(r"hp\s*up|increase.*hp|stats\s*up", text_lower): tags.add("HP UP")
    if re.search(r"hp\s*down|reduce.*hp|lower.*hp", text_lower): tags.add("HP DOWN")

    # 13. ESTADOS DE ALTERACIÓN (INFLICTING STATUS AILMENT ONLY - EXCLUIR RES / CURE / CLEANSE)
    status_list = [
        (r"\bbleed\b(?!\s*res|\s*cure|\s*cleanse)", "Bleed"),
        (r"\bburn\b(?!\s*res|\s*cure|\s*cleanse)", "Burn"),
        (r"\bpoison\b(?!\s*res|\s*cure|\s*cleanse)", "Poison"),
        (r"\bfreeze\b(?!\s*res|\s*cure|\s*cleanse)", "Freeze"),
        (r"\bparalys|\bparalyz(?!\s*res|\s*cure|\s*cleanse)", "Paralysis"),
        (r"\bfaint\b(?!\s*res|\s*cure|\s*cleanse)", "Faint"),
        (r"\bblind\b(?!\s*res|\s*cure|\s*cleanse)", "Blind"),
        (r"\bdisease\b(?!\s*res|\s*cure|\s*cleanse)", "Disease"),
        (r"\bseal\b(?!\s*res|\s*cure|\s*cleanse)", "Seal")
    ]
    for pat, tag_name in status_list:
        if re.search(pat, text_lower): tags.add(tag_name)

    # 14. BREAK
    if re.search(r"break\s*power|break\s*res|break\s*gauge", text_lower):
        tags.add("Break Power UP")

    return list(tags)

def scan_equip_tags(equip_json):
    """Escanea descripciones y propiedades de equipos garantizando 100% de cobertura de etiquetas tácticas."""
    if not isinstance(equip_json, dict):
        return []

    tags = set()
    
    # 1. Etiqueta de Tipo de Slot
    eq_type = map_equip_type(equip_json.get("type"))
    if eq_type:
        tags.add(eq_type)
        if "6★" in eq_type or "physLB6" in str(equip_json.get("type")) or "magLB6" in str(equip_json.get("type")):
            tags.add("Slot 6★")

    # 2. Etiqueta de Rareza / Estrellas
    star = equip_json.get("star", 5)
    tags.add(f"★{star}")
    if star == 6:
        tags.add("Ultra Relic")

    # 3. Etiquetas tácticas derivadas del mismo motor de Unidades
    derived_tags = scan_unit_tags(equip_json, [])
    for t in derived_tags:
        if t not in ["Awoken", "Ascended"]:
            tags.add(t)

    # 4. Detección de Origen y Ubicación
    name = str(equip_json.get("name", "")).lower()
    loc = str(equip_json.get("location", "")).lower()
    full_text = f"{name} {loc}"

    if "true weapon" in full_text or name.startswith("true "):
        tags.add("True Weapon")
    if "collab" in loc or "crossover" in loc:
        tags.add("Collab")
    if "mines" in loc:
        tags.add("Mines")
    if "giant boss" in loc or "raid" in loc:
        tags.add("Giant Boss")
    if "side story" in loc or "main story" in loc or "farmable" in loc:
        tags.add("Side Story / Main Story")
    if "craft" in loc or "recipe" in loc or "smith" in loc:
        tags.add("Crafting Recipe")
    if "rainbow" in loc or "alchemy" in loc or "alchemist" in loc:
        tags.add("Rainbow Orb Exchange")
    if "gacha" in loc or "summon" in loc:
        tags.add("Permanent Gacha")
    if not any(t in tags for t in ["True Weapon", "Collab", "Mines", "Giant Boss", "Side Story / Main Story", "Crafting Recipe", "Rainbow Orb Exchange", "Permanent Gacha"]):
        tags.add("Event")

    return list(tags)

def check_for_new_units_remote():
    """Retorna el número actual de unidades en la base de datos Global remota."""
    url_units = "https://www.grandsummoners.info/api/units.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url_units, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return len(data)
    except: pass
    return 0

def get_color_for_type(t_name):
    """Mapea el nombre del tipo al color táctico."""
    tn = t_name.lower()
    if "físico" in tn or "phys" in tn: return "Rojo"
    if "mágico" in tn or "mag" in tn: return "Morado"
    if "defensa" in tn or "def" in tn: return "Azul"
    if "soporte" in tn or "supp" in tn: return "Dorado"
    if "curación" in tn or "heal" in tn: return "Verde"
    return "Gris"

def extract_unit_buffs_and_debuffs(unit_json):
    buffs = []
    debuffs = []
    skillset = unit_json.get("skillset", {}) or {}
    passives = unit_json.get("passive", {}) or {}
    
    moves = [
        ("Skill", skillset.get("skill")),
        ("Arts", skillset.get("arts")),
        ("True Arts", skillset.get("truearts")),
        ("Super Arts", skillset.get("superarts"))
    ]
    if isinstance(passives, dict):
        for pk, pv in passives.items():
            moves.append((str(pk), str(pv)))

    for m_name, m_desc in moves:
        if not m_desc or m_desc == "None": continue
        desc = str(m_desc)
        desc_lower = desc.lower()

        # Barrier
        if "barrier" in desc_lower or "barrera" in desc_lower or "バリア" in desc_lower:
            m_num = re.search(r'(\d[\d,]*)\s*(?:hp|barrier|damage)', desc_lower)
            val = m_num.group(1).replace(",", "") if m_num else "30000"
            buffs.append({"name": "Barrier", "value": val, "target": "Team", "move": m_name, "desc": desc})

        # Accuracy UP
        if "accuracy" in desc_lower or "precisión" in desc_lower or "命中" in desc_lower:
            m_num = re.search(r'accuracy by (\d+)%|precisión en (\d+)%', desc_lower)
            val = ((m_num.group(1) or m_num.group(2)) + "%") if m_num else "100%"
            buffs.append({"name": "Accuracy UP", "value": val, "target": "Team", "tag": "STRONGEST", "move": m_name, "desc": desc})

        # CRI Rate UP
        if "cri rate" in desc_lower or "crit rate" in desc_lower or "クリティカル率" in desc_lower:
            is_self = "self" in desc_lower or "own" in desc_lower
            m_num = re.search(r'rate by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "100%"
            buffs.append({"name": "CRI Rate UP", "value": val, "target": "Self" if is_self else "Team", "move": m_name, "desc": desc})

        # CRI DMG UP
        if "cri dmg" in desc_lower or "crit dmg" in desc_lower or "クリティカルダメージ" in desc_lower:
            m_num = re.search(r'cri(?:tical)? dmg by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "300%"
            buffs.append({"name": "CRI DMG UP", "value": val, "target": "Team", "move": m_name, "desc": desc})

        # Equip CT UP / Speed
        if "equip ct" in desc_lower or "ct of equips" in desc_lower or "equipment ct speed" in desc_lower:
            is_self = "own" in desc_lower
            m_num = re.search(r'by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "50%"
            buffs.append({"name": "Equip CT Speed", "value": val, "target": "Self" if is_self else "Team", "tag": "STRONGEST", "move": m_name, "desc": desc})

        # DMG RES UP
        if "dmg res" in desc_lower or "damage resist" in desc_lower or "被ダメージ" in desc_lower:
            m_num = re.search(r'res by (\d+)%|resist by (\d+)%', desc_lower)
            val = ((m_num.group(1) or m_num.group(2)) + "%") if m_num else "30%"
            buffs.append({"name": "DMG RES UP", "value": val, "target": "Team", "move": m_name, "desc": desc})

        # Max HP UP
        if "max hp" in desc_lower:
            m_num = re.search(r'max hp by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "20%"
            buffs.append({"name": "Max HP UP", "value": val, "target": "Team", "move": m_name, "desc": desc})

        # Stats UP
        if "stats" in desc_lower or "ステータス" in desc_lower:
            m_num = re.search(r'stats by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "30%"
            buffs.append({"name": "Stats UP", "value": val, "target": "Team", "move": m_name, "desc": desc})

        # ATK UP / Human ATK UP
        if "atk" in desc_lower and "up" in desc_lower or "atk by" in desc_lower:
            is_human = "human" in desc_lower
            is_self = "own" in desc_lower
            m_num = re.search(r'atk by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "100%"
            name = "ATK UP (Human)" if is_human else "ATK UP"
            buffs.append({"name": name, "value": val, "target": "Self" if is_self else "Team", "move": m_name, "desc": desc})

        # Debuffs: CRI RES DOWN
        if "cri res" in desc_lower and "down" in desc_lower or "cri res by" in desc_lower:
            m_num = re.search(r'res by (\d+)%', desc_lower)
            val = (m_num.group(1) + "%") if m_num else "100%"
            debuffs.append({"name": "CRI RES DOWN", "value": val, "move": m_name, "desc": desc})

        # Debuffs: Water / Fire / Earth / Light / Dark / Elem RES DOWN
        if "res by" in desc_lower and ("water" in desc_lower or "fire" in desc_lower or "earth" in desc_lower or "light" in desc_lower or "dark" in desc_lower or "elem" in desc_lower):
            m_num = re.search(r'(water|fire|earth|light|dark|elem(?:ental)?) res by (\d+)%', desc_lower)
            if m_num:
                elem = m_num.group(1).capitalize()
                val = m_num.group(2) + "%"
                name = f"{elem} RES DOWN" if elem != "Elem" else "Elem RES DOWN"
                debuffs.append({"name": name, "value": val, "move": m_name, "desc": desc})
            else:
                m_num2 = re.search(r'by (\d+)%', desc_lower)
                val = (m_num2.group(1) + "%") if m_num2 else "80%"
                debuffs.append({"name": "Elem RES DOWN", "value": val, "move": m_name, "desc": desc})

    return buffs, debuffs

def sync_from_global_db(ruta_cache):
    """
    Sincronización Híbrida 120.0: Soporte Forever Summons Septiembre 2026.
    """
    url_units = "https://www.grandsummoners.info/api/units.json"
    url_equips = "https://www.grandsummoners.info/api/equips.json"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        # 0. Cargar el Pool de Forever Summons (AIDs)
        fs_pool_aids = get_forever_summons_pool()
        
        # 1. Cargar el Bridge Mapping
        mapa_bridge = {}
        py_dir = os.path.dirname(os.path.abspath(__file__))
        ruta_bridge = os.path.join(py_dir, "bridge_mapping.json")
        bridge_data_full = {}
        
        if os.path.exists(ruta_bridge):
            try:
                with open(ruta_bridge, "r", encoding="utf-8") as f:
                    bridge_data_full = json.load(f)
                    if "mapping" in bridge_data_full: mapa_bridge = bridge_data_full["mapping"]
                    else: mapa_bridge = bridge_data_full
            except: pass

        val_ultimo = bridge_data_full.get("__ULTIMO_ID_ALTEMA__", "511")
        try: ultimo_id_altema = int(str(val_ultimo))
        except: ultimo_id_altema = 511

        bridge_changed = False

        r_u = requests.get(url_units, headers=headers, timeout=30)
        if r_u.status_code != 200: return False
        units_data = r_u.json()
        r_e = requests.get(url_equips, headers=headers, timeout=30)
        equips_data = r_e.json() if r_e.status_code == 200 else []
        
        mapa_tiers = extract_global_tiers()
        lista_personajes = []
        ids_ocupados = set()
        
        carpeta_raw = os.path.join(ruta_cache, "raw_data")
        if not os.path.exists(carpeta_raw): os.makedirs(carpeta_raw)

        map_elem = {"Fire": "Fuego", "Water": "Agua", "Earth": "Tierra", "Light": "Luz", "Dark": "Oscuridad"}
        map_race = {"Human": "Humano", "Demon": "Demonio", "God": "Dios", "Spirit": "Espíritu", "Machine": "Máquina", "Beast": "Bestia", "Dragon" : "Dragón", "Giant": "Gigante"}

        # 2. PROCESAR UNIDADES DE GLOBAL
        for unit in units_data:
            u_id = str(unit.get("id"))
            name_en = str(unit.get("name", "Unknown")).strip()
            
            entry = mapa_bridge.get(name_en)
            if not entry:
                # Intento de emparejamiento exacto ignorando mayúsculas/minúsculas
                name_en_lower = name_en.lower()
                for k, v in mapa_bridge.items():
                    if k.startswith("__"): continue
                    if name_en_lower == k.lower():
                        entry = v; break
            
            if not entry:
                # Intento de emparejamiento por ID Global (Fail-safe)
                u_id_str = str(u_id)
                for k, v in mapa_bridge.items():
                    if k.startswith("__"): continue
                    try:
                        if v.get("altema_id") == u_id_str:
                            entry = v; break
                    except: pass
            
            alt_id = "0"
            rol_final = "N/A"
            seiyuu_final = "N/A"

            if entry:
                try:
                    alt_id = entry.get("altema_id", "0")
                    rol_final = entry.get("role", "N/A")
                    seiyuu_final = entry.get("seiyuu", "N/A")
                except: alt_id = str(entry)

            if not rol_final or rol_final == "N/A":
                rol_global = unit.get("role")
                if rol_global: rol_final = str(rol_global)

            if not alt_id or alt_id == "0":
                # GENERACIÓN DE ID PARA NUEVOS PERSONAJES
                ultimo_id_altema += 1
                alt_id = str(ultimo_id_altema)
                
                # Crear entrada en el bridge para persistencia
                bridge_data_full[name_en] = {
                    "altema_id": alt_id,
                    "role": "N/A",
                    "seiyuu": "N/A"
                }
                bridge_changed = True
                print(f"🆕 Nueva unidad detectada: {name_en} -> ID: {alt_id}")
            
            # Caso especial: Unidades Global-Only explícitamente marcadas en el bridge
            if alt_id == "N/A":
                href_altema = f"GLOBAL_{u_id}"
            else:
                href_altema = f"/grandsummoners/unit/{alt_id}"

            with open(os.path.join(carpeta_raw, f"unit_{u_id}.json"), 'w', encoding='utf-8') as f:
                json.dump(unit, f, ensure_ascii=False)

            skillset = unit.get("skillset", {})
            
            found_entries = []
            for k, lbl in [('superarts', 'SA'), ('protagonize', 'PZ'), ('hero', 'EXA'), ('phantombullet', 'PB'), ('crossarts', 'XA'), ('truearts', 'TA'), ('arts', 'A'), ('skill', 'S')]:
                txt = str(skillset.get(k, ""))
                if "Arts Gen is Type" in txt:
                    # PRIORIDAD: Buscar EX\d* primero, luego letras A-Z
                    matches = re.findall(r"Type\s+(EX\d*|[A-Z])", txt, re.I)
                    for t_found in matches:
                        t_found = t_found.upper()
                        dup = False
                        for e in found_entries:
                            if e["type"] == t_found and e["source"] == lbl: dup = True; break
                        if not dup: found_entries.append({"type": t_found, "source": lbl})

            if passives := unit.get("passive"):
                for pk, ptxt in passives.items():
                    if "Arts Gen is Type" in str(ptxt):
                        matches = re.findall(r"Type\s+(EX\d*|[A-Z])", str(ptxt), re.I)
                        for t_found in matches:
                            t_found = t_found.upper()
                            dup = False
                            for e in found_entries:
                                if e["type"] == t_found and e["source"] == "P": dup = True; break
                            if not dup: found_entries.append({"type": t_found, "source": "P"})

            unique_types = []
            for e in found_entries:
                if e["type"] not in unique_types: unique_types.append(e["type"])
            unique_types.sort()
            
            p_slots = []
            slots_data = unit.get("slots", {}) or unit
            for i in [1, 2, 3]:
                st = slots_data.get(f"equip_type_{i}") or slots_data.get(f"slot{i}type")
                
                # CASO HÍBRIDO (SA)
                if i == 3 and not st:
                    st = slots_data.get("slot31type")
                    st_alt = slots_data.get("slot32type")
                    if st and st_alt:
                        type_name = map_equip_type(st) + " / " + map_equip_type(st_alt)
                        color_name = get_color_for_type(map_equip_type(st)) + " / " + get_color_for_type(map_equip_type(st_alt))
                        sr = slots_data.get("slot3") or "5"
                        p_slots.append({"tipo": type_name, "valor": f"★{sr}", "color": color_name})
                        continue

                if st:
                    type_name = map_equip_type(st)
                    color_name = get_color_for_type(type_name)
                    sr = slots_data.get(f"equip_rank_{i}") or slots_data.get(f"slot{i}") or "5"
                    
                    # REGLA TÁCTICA: 6 estrellas solo permitido en el Slot 1
                    if i > 1 and str(sr) == "6":
                        sr = "5"
                        
                    p_slots.append({"tipo": type_name, "valor": f"★{sr}", "color": color_name})

            img_info = unit.get("image", {})
            img_f = img_info.get("detailsuper") or img_info.get("detailawk") or img_info.get("detail5") or img_info.get("detail")
            img_full = "https://www.grandsummoners.info" + img_f if img_f else f"https://www.grandsummoners.info/db/Units/Thumbnail/unit_thumbnail_{u_id}.webp"
            img_special = "https://www.grandsummoners.info" + img_info["detailspecial"] if img_info.get("detailspecial") else ""
            img_awk = "https://www.grandsummoners.info" + img_info["detailawk"] if img_info.get("detailawk") else ""
            img_super = "https://www.grandsummoners.info" + img_info["detailsuper"] if img_info.get("detailsuper") else ""
            img_5star = "https://www.grandsummoners.info" + img_info["detail5"] if img_info.get("detail5") else ""

            # Marcar si es parte del Forever Summons (Sept 2026)
            base_tags = unique_types + ([rol_final] if rol_final != "N/A" else [])
            if str(alt_id) in fs_pool_aids:
                base_tags.append("FOREVER_POOL")
            
            unit_tags = scan_unit_tags(unit, base_tags)
            has_super_arts = bool(skillset.get("superarts")) if skillset.get("superarts") else False
            classification_tag = "Ascended" if has_super_arts else "Awoken"
            if "Ascended" in unit_tags: unit_tags.remove("Ascended")
            if "Awoken" in unit_tags: unit_tags.remove("Awoken")
            unit_tags.insert(0, classification_tag)

            is_gl = bool(unit.get("global", True))
            unit_tags.append("Global" if is_gl else "Japón (JP)")

            has_dream = bool(unit.get("dream") or unit.get("dreamJP") or unit.get("dreamGL"))
            if has_dream:
                unit_tags.append("Dream Awakening")

            unit_buffs, unit_debuffs = extract_unit_buffs_and_debuffs(unit)

            lista_personajes.append({
                "id": u_id, "nombre": unit.get("name"), "nombre_original": unit.get("name"),
                "href": href_altema, "imagen_url": f"https://www.grandsummoners.info/db/Units/Thumbnail/unit_thumbnail_{u_id}.webp",
                "imagen_full": img_full,
                "imagen_special": img_special,
                "imagen_awk": img_awk,
                "imagen_super": img_super,
                "imagen_5star": img_5star,
                "elemento": map_elem.get(unit.get("attribute"), unit.get("attribute", "N/A")),
                "raza": map_race.get(unit.get("race"), unit.get("race", "N/A")), "rol": rol_final,
                "tier": mapa_tiers.get(u_id, "N/A"), "rareza": f"★{unit.get('rarity', '5')}",
                "seiyuu": seiyuu_final,
                "is_sa": has_super_arts,
                "is_global": is_gl,
                "has_dream": has_dream,
                "skillset": skillset,
                "arts_gen_type": unique_types[0] if unique_types else "None",
                "arts_gen_details": found_entries,
                "buffs_details": unit_buffs,
                "debuffs_details": unit_debuffs,
                "tags": unit_tags, "slots": p_slots
            })

        # 3. UNIDADES DE RELLENO (PERMANENTES)
        ruta_fillers = os.path.join(py_dir, "fillers_permanent.json")
        if os.path.exists(ruta_fillers):
            try:
                with open(ruta_fillers, "r", encoding="utf-8") as f:
                    fillers_data = json.load(f)
                    for p_f in fillers_data:
                        f_id_str = str(p_f["id"])
                        if f_id_str not in ids_ocupados:
                            if "arts_gen_details" not in p_f: p_f["arts_gen_details"] = []
                            if "arts_gen_type" not in p_f: p_f["arts_gen_type"] = "None"
                            lista_personajes.append(p_f)
                            ids_ocupados.add(f_id_str)
            except: pass

        # 4. PROCESAR OBJETOS
        lista_objetos = []
        for eq in equips_data:
            e_id = str(eq.get("id"))
            with open(os.path.join(carpeta_raw, f"equip_{e_id}.json"), 'w', encoding='utf-8') as f:
                json.dump(eq, f, ensure_ascii=False)
            
            img_info = eq.get("image", {}) or {}
            img_url = img_info.get("thumbmax") or img_info.get("thumb")
            if img_url and str(img_url).startswith("/"): 
                img_url = "https://www.grandsummoners.info" + str(img_url)
            
            lista_objetos.append({
                "id": e_id, 
                "nombre": str(eq.get("name", "Unknown")), 
                "nombre_original": str(eq.get("translate") or eq.get("name", "Unknown")), 
                "rareza": "★" + str(eq.get("star", "5")), 
                "tipo": map_equip_type(eq.get("type")), 
                "tags": scan_equip_tags(eq),
                "imagen_url": img_url or f"https://www.grandsummoners.info/db/Equips/Thumbnail/equip_thumbnail_{e_id}.webp"
            })

        # --- Re-población de Guía Arts Gen ---
        guia_arts_gen = []
        for p in lista_personajes:
            if p.get("arts_gen_type") and p["arts_gen_type"] != "None":
                guia_arts_gen.append({
                    "id": p["id"],
                    "name": p["nombre"],
                    "name_jp": p.get("nombre_original", p["nombre"]),
                    "img": p["imagen_url"],
                    "arts_gen": p["arts_gen_type"],
                    "details": p.get("arts_gen_details", [])
                })

        with open(os.path.join(ruta_cache, "lista_personajes_global.json"), 'w', encoding='utf-8') as f:
            json.dump(lista_personajes, f, ensure_ascii=False, indent=2)
        with open(os.path.join(ruta_cache, "lista_objetos_global.json"), 'w', encoding='utf-8') as f:
            json.dump(lista_objetos, f, ensure_ascii=False, indent=2)
        with open(os.path.join(ruta_cache, "arts_gen_db.json"), 'w', encoding='utf-8') as f:
            json.dump(guia_arts_gen, f, ensure_ascii=False, indent=2)
            
        # 5. GUARDAR BRIDGE ACTUALIZADO (SI CAMBIÓ)
        if bridge_changed:
            bridge_data_full["__ULTIMO_ID_ALTEMA__"] = str(ultimo_id_altema)
            with open(ruta_bridge, 'w', encoding='utf-8') as f:
                json.dump(bridge_data_full, f, ensure_ascii=False, indent=2)
            print(f"✅ Bridge actualizado. Último ID: {ultimo_id_altema}")

        return True
    except Exception as e:
        print(f"Error Sync: {e}")
        return False

def download_unit_details_batch(unit_ids, target_dir):
    """Función desactivada para optimizar velocidad de sincronización."""
    return

def obtener_detalle_unidad_vivo(u_id, ruta_cache=""):
    """
    Obtiene en tiempo real los detalles y sinergia de una unidad desde grandsummoners.info/api/units.json
    y guarda el JSON localmente en cache/raw_data/unit_details_{u_id}.json.
    """
    try:
        url_units = "https://www.grandsummoners.info/api/units.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url_units, headers=headers, timeout=10)
        if r.status_code == 200:
            units_data = r.json()
            for unit in units_data:
                unit_id_str = str(unit.get("id"))
                unit_name = str(unit.get("name", "")).strip()
                if unit_id_str == str(u_id) or unit_name.lower() == str(u_id).lower():
                    buffs, debuffs = extract_unit_buffs_and_debuffs(unit)
                    
                    res_obj = {
                        "id": unit_id_str,
                        "nombre": unit_name,
                        "skillset": unit.get("skillset", {}),
                        "passive": unit.get("passive", {}),
                        "buffs_details": buffs,
                        "debuffs_details": debuffs
                    }
                    
                    if ruta_cache:
                        raw_dir = os.path.join(ruta_cache, "raw_data")
                        if not os.path.exists(raw_dir): os.makedirs(raw_dir)
                        with open(os.path.join(raw_dir, f"unit_details_{unit_id_str}.json"), "w", encoding="utf-8") as f:
                            json.dump(res_obj, f, ensure_ascii=False, indent=2)
                            
                    return json.dumps(res_obj, ensure_ascii=False)
    except Exception as e:
        print(f"Error live detail sync: {e}")
    return "{}"

def preparar_descarga_global(ruta_cache, carpeta_imgs):
    success = sync_from_global_db(ruta_cache)
    if not success: return {"personajes": [], "objetos": [], "faltantes": []}
    try:
        with open(os.path.join(ruta_cache, "lista_personajes_global.json"), 'r', encoding='utf-8') as f:
            personajes = json.load(f)
        with open(os.path.join(ruta_cache, "lista_objetos_global.json"), 'r', encoding='utf-8') as f:
            objetos = json.load(f)
    except: return {"personajes": [], "objetos": [], "faltantes": []}

    archivos = set(os.listdir(carpeta_imgs)) if os.path.exists(carpeta_imgs) else set()
    faltantes = []
    for p in personajes:
        if f"{p['id']}.jpg" not in archivos:
            faltantes.append({"id": p["id"], "url": p["imagen_url"], "tipo": "P"})
    for o in objetos:
        if f"equip_{o['id']}.jpg" not in archivos:
            faltantes.append({"id": o["id"], "url": o["imagen_url"], "tipo": "O"})
    return {"personajes": personajes, "objetos": objetos, "faltantes": faltantes}
