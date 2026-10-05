"""Generate sound effects with ElevenLabs Sound Effects API (template).

Key is read ONLY from the environment variable ELEVENLABS_API_KEY - never write it into a file.

  export ELEVENLABS_API_KEY=...        # your own key
  python3 elevenlabs_sfx.py out_dir    # generates every entry of SFX below as out_dir/<name>.mp3

Then convert to wav for mixing:  ffmpeg -i name.mp3 -ar 48000 -ac 2 name.wav
"""
import os
import sys
import json
import urllib.request

SFX = {
    # name: (prompt, duration seconds)
    'explosion_big': ('huge truck explosion, deep boom, debris falling, cinematic', 4.0),
    'building_collapse': ('concrete building collapsing, rumble, crumbling debris, distant', 6.0),
    'rocket_flyby': ('missile flying past camera, whoosh, doppler, slow motion', 4.0),
    'nuke_boom': ('distant nuclear explosion, massive low boom, pressure wave', 6.0),
    'amb_ruins': ('quiet wind in ruined city, very sparse, no music', 10.0),
}


def gen(name, prompt, dur, out_dir, key):
    body = json.dumps({'text': prompt, 'duration_seconds': dur, 'prompt_influence': 0.5}).encode()
    req = urllib.request.Request('https://api.elevenlabs.io/v1/sound-generation', data=body, method='POST',
                                 headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    path = os.path.join(out_dir, name + '.mp3')
    open(path, 'wb').write(data)
    print(f'{name:24s} {len(data) / 1024:7.1f} KB -> {path}')


if __name__ == '__main__':
    key = os.environ.get('ELEVENLABS_API_KEY')
    if not key:
        sys.exit('Set ELEVENLABS_API_KEY in the environment first.')
    out = sys.argv[1] if len(sys.argv) > 1 else 'gen_sfx'
    os.makedirs(out, exist_ok=True)
    for n, (p, d) in SFX.items():
        if not os.path.exists(os.path.join(out, n + '.mp3')):
            gen(n, p, d, out, key)
