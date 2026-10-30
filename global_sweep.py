import requests
import json

url = 'https://www.grandsummoners.info/api/units.json'
headers = {'User-Agent': 'Mozilla/5.0'}

try:
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        results = []
        for u in data:
            results.append({
                'id_global': u.get('id'),
                'name_en': u.get('name'),
                'name_jp': u.get('translate'),
                'arts_gen': str(u.get('skillset', {}).get('truearts', ''))
            })
        
        with open('global_sweep.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print('Global sweep finished. Count: ' + str(len(results)))
except Exception as e:
    print('Error Global: ' + str(e))
