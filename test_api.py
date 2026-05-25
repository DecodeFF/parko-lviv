import requests, urllib3
urllib3.disable_warnings()
base = 'https://127.0.0.1:5001'

coords = [
    (49.8397, 24.0297),
    (49.8420, 24.0310),
    (49.8380, 24.0260),
]
for lat, lon in coords:
    r = requests.post(base + '/api/coordinates',
                      json={'latitude': lat, 'longitude': lon}, verify=False)
    d = r.json()
    rec_id = d.get('id', 'ERROR')
    print('POST', r.status_code, '| id:', rec_id, '| lat:', lat, '| lon:', lon)

r = requests.get(base + '/api/coordinates/track', verify=False)
data = r.json()
print('\nВсього в базі:', len(data['track']), 'записів')
