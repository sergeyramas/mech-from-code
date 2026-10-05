#!/usr/bin/env python3
"""Generate hf/how-agents/index.html for video 2 "Я не умею 3D..." (1920x1080, 30 fps)."""
import json, math, pathlib, subprocess
import numpy as np

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
VO = json.load(open(ROOT / "work/vo/vo_timing.json"))

S = [0, 14, 33, 55, 84, 98, 121, 150, 167]     # scene starts
END = 184.0
OFF = [3.0, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8]  # VO offset inside scene
def vo0(i): return S[i] + OFF[i]
def at(i, rel): return round(vo0(i) + rel, 3)   # absolute time from VO-relative time

# ---------------- captions: balanced 1-2 line chunks per sentence ----------------
def captions():
    out = []
    groups = []
    for c in VO["captions"]:
        if groups and groups[-1][-1]["scene"] == c["scene"] and not groups[-1][-1]["text"].rstrip().endswith((".", "!", "?", "»")):
            groups[-1].append(c)
        else:
            groups.append([c])
    for g in groups:
        sc = g[0]["scene"]; text = " ".join(x["text"] for x in g)
        t0, t1 = g[0]["start"], g[-1]["end"]
        if text.startswith("«"):   # quotes are shown as chat bubbles in scene 6
            continue
        k = max(1, math.ceil(len(text) / 80))
        words = text.split(" ")
        parts = []
        start = 0
        for j in range(1, k):
            target = len(text) * j / k
            best, bs = None, 1e9
            for wi in range(start + 1, len(words)):
                pos = len(" ".join(words[:wi]))
                scr = abs(pos - target) - (14 if words[wi-1][-1] in ",:;—" else 0) - (14 if words[wi] == "—" else 0)
                if scr < bs: bs, best = scr, wi
            parts.append(" ".join(words[start:best])); start = best
        parts.append(" ".join(words[start:]))
        L = sum(len(p) for p in parts); acc = 0
        for p in parts:
            a = t0 + (t1 - t0) * acc / L; acc += len(p); b = t0 + (t1 - t0) * acc / L
            out.append((at(sc, a), at(sc, b) + 0.25, p))
    # remove overlaps
    for i in range(len(out) - 1):
        if out[i][1] > out[i + 1][0]:
            out[i] = (out[i][0], out[i + 1][0], out[i][2])
    return out

CAPS = captions()

# ---------------- waveform for scene 4 ----------------
def waveform(n=220, dur=14.0):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ROOT.parent / "blender/renders/mech_walk_v2_audio.wav"),
                          "-t", str(dur), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    seg = np.array_split(a, n)
    pk = np.array([np.sqrt(np.mean(s ** 2)) if len(s) else 0 for s in seg])
    pk = pk / (pk.max() + 1e-9)
    return [round(float(max(0.03, v ** 0.7)), 3) for v in pk]

WF = waveform()

# ---------------- html pieces ----------------
def vclip(id_, src, start, dur, mstart, wrap_style="", cls="vfull"):
    return (f'<div class="vwrap {cls}" id="w_{id_}" style="{wrap_style}">'
            f'<video id="{id_}" class="clip" src="{src}" muted playsinline data-start="{start}" data-duration="{dur}" '
            f'data-media-start="{mstart}" data-track-index="0"></video></div>')

VIDEOS = [
    # scene 0
    vclip("v0a", "assets/cine.mp4", 0, 3.0, 25.55),
    vclip("v0b", "assets/cine.mp4", 3.0, 3.2, 4.2),
    vclip("v0c", "assets/cine.mp4", 6.2, 2.8, 16.5),
    vclip("v0d", "assets/cine.mp4", 9.0, 5.0, 36.0),
    # scene 4 walk (framed)
    vclip("v4", "assets/walk.mp4", 84.0, 14.0, 0, "left:391px;top:90px;width:1138px;height:640px;", "vbox"),
    # scene 6 quote results
    vclip("v6a", "assets/cine.mp4", 126.4, 2.8, 16.4),
    vclip("v6b", "assets/cine.mp4", 129.8, 2.65, 22.6),
    vclip("v6c", "assets/cine.mp4", 133.2, 3.0, 25.55),
    vclip("v6d", "assets/cine.mp4", 136.2, 2.9, 28.25),
    # scene 7 background
    vclip("v7", "assets/cine.mp4", 150.0, 17.0, 25.0),
]

CAP_HTML = "\n".join(
    f'<div class="cap clip" data-start="{a}" data-duration="{round(b - a, 3)}" data-track-index="6"><span>{t}</span></div>'
    for a, b, t in CAPS)

WF_HTML = "".join(f'<i style="height:{int(v * 100)}%"></i>' for v in WF)

COUNTERS = [("6,5", "ч", "работы, вечер"), ("7", "", "ИИ-агентов"), ("0", "", "строк кода от меня"),
            ("1027", "", "кадров"), ("62", "мин", "рендер"), ("215", "", "частей робота"), ("220", "", "обломков здания")]
CNT_HTML = "".join(
    f'<div class="cnt" id="cnt{i}"><div class="cn"><b data-to="{v}">{v}</b><small>{u}</small></div><div class="cl">{l}</div></div>'
    for i, (v, u, l) in enumerate(COUNTERS))

HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden;background:#15170F}
#root{position:relative;width:1920px;height:1080px;overflow:hidden;background:#15170F;
 --bg:#15170F;--panel:#22261A;--line:#3A4029;--amber:#E8A33A;--olive:#9DAA68;--red:#E5484D;--ink:#EDE6D6;--dim:#A39C8C;
 font-family:'Montserrat',sans-serif;color:var(--ink)}
.mono{font-family:'JetBrains Mono',monospace}
#bg{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#232818 0%,#15170F 70%);z-index:0}
#bggrid{position:absolute;inset:0;opacity:.35;background-image:linear-gradient(rgba(157,170,104,.10) 1px,transparent 1px),linear-gradient(90deg,rgba(157,170,104,.10) 1px,transparent 1px);background-size:60px 60px}
.vwrap{position:absolute;z-index:1;overflow:hidden}
.vfull{left:0;top:0;width:1920px;height:1080px}
.vwrap video{width:100%;height:100%;object-fit:cover;display:block}
.vbox{border:2px solid var(--line)}
.scene{position:absolute;inset:0;z-index:2}
.chap{position:absolute;left:60px;top:48px;font-family:'JetBrains Mono',monospace;font-size:22px;letter-spacing:.18em;color:var(--amber);text-shadow:0 2px 6px rgba(0,0,0,.7)}
.chap b{color:var(--ink);font-weight:700;margin-right:14px}
.h1{font-weight:800;font-size:76px;line-height:1.08;letter-spacing:-.01em}
.h2{font-weight:700;font-size:52px;line-height:1.15}
.lab{font-family:'JetBrains Mono',monospace;font-size:24px;letter-spacing:.12em;color:var(--olive);text-transform:uppercase}
.amber{color:var(--amber)}
.card{position:absolute;background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
.chip{display:inline-block;padding:10px 20px;border-radius:999px;border:2px solid var(--amber);color:var(--ink);font-weight:600;font-size:30px;background:rgba(232,163,58,.10)}
.img{position:absolute;overflow:hidden;border-radius:12px;border:1px solid var(--line);background:#000}
.img img{width:100%;height:100%;object-fit:cover;display:block}
.kb{width:100%;height:100%}
.tag{position:absolute;font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;padding:6px 14px;background:var(--amber);color:#15170F;border-radius:6px;letter-spacing:.06em}
/* captions */
.cap{position:absolute;left:160px;right:160px;bottom:54px;text-align:center;z-index:8}
.cap span{display:inline-block;max-width:1500px;padding:12px 26px;border-radius:12px;background:rgba(12,13,8,.78);font-weight:600;font-size:40px;line-height:1.3;color:#F4EEE0}
/* progress */
#prog{position:absolute;left:0;top:0;height:5px;width:1920px;background:var(--amber);transform-origin:0 50%;z-index:9;opacity:.85}
/* S0 */
#s0title{position:absolute;left:0;right:0;top:300px;text-align:center}
#s0title .row{display:flex;justify-content:center;align-items:baseline;gap:34px;font-weight:800;font-size:88px;text-shadow:0 4px 24px rgba(0,0,0,.8)}
#s0title .arr{color:var(--amber);font-family:'JetBrains Mono',monospace;font-weight:700}
#s0shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.25),rgba(0,0,0,.55))}
/* S1 */
.rule{display:flex;align-items:center;gap:26px;font-size:46px;font-weight:600;margin:22px 0}
.rule .x{width:56px;height:56px;border-radius:50%;background:var(--red);color:#fff;display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:800}
.rule .t{position:relative}
.rule .t i{position:absolute;left:-6px;right:-6px;top:52%;height:5px;background:var(--red);transform-origin:0 50%}
#codebg{position:absolute;right:80px;top:140px;width:760px;font-family:'JetBrains Mono',monospace;font-size:22px;line-height:1.6;color:rgba(157,170,104,.55);white-space:pre}
/* S2 diagram */
.node{position:absolute;padding:22px 30px;border-radius:14px;background:var(--panel);border:2px solid var(--line);text-align:center;min-width:260px}
.node .n{font-weight:700;font-size:36px}
.node .d{font-family:'JetBrains Mono',monospace;font-size:21px;color:var(--dim);margin-top:6px;letter-spacing:.04em}
.node.main{border-color:var(--amber);box-shadow:0 0 40px rgba(232,163,58,.25)}
svg.wires{position:absolute;left:0;top:0;width:1920px;height:1080px;overflow:visible}
.wire{stroke:var(--olive);stroke-width:3;fill:none;stroke-dasharray:10 8}
#loop text{font-family:'JetBrains Mono',monospace;font-size:24px;fill:#EDE6D6;font-weight:700}
/* S3 */
#vcount{position:absolute;right:70px;top:40px;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:64px;color:var(--amber)}
#vcount small{display:block;font-size:20px;letter-spacing:.2em;color:var(--olive);text-align:right}
.meter{position:absolute;left:160px;right:160px;top:800px}
.meter .bar{height:16px;border-radius:8px;background:#2D3222;overflow:hidden}
.meter .fill{height:100%;width:100%;background:linear-gradient(90deg,var(--olive),var(--amber));transform-origin:0 50%}
.meter .row{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}
.meter .big{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:56px;color:var(--amber)}
#scan{position:absolute;top:0;bottom:0;width:4px;background:var(--amber);box-shadow:0 0 24px var(--amber)}
/* S4 */
#osc{position:absolute;left:160px;top:760px;width:1600px;height:150px;display:flex;align-items:center;gap:2px}
#osc i{flex:1;background:var(--olive);border-radius:2px;opacity:.85}
#playhead{position:absolute;left:160px;top:745px;width:3px;height:180px;background:var(--amber);box-shadow:0 0 14px var(--amber)}
.sfx{position:absolute;top:650px}
/* S5 */
.pb{margin:26px 0}
.pb .top{display:flex;justify-content:space-between;font-size:34px;font-weight:600;margin-bottom:12px}
.pb .top .mono{color:var(--amber)}
.pb .bar{height:26px;border-radius:13px;background:#2D3222;overflow:hidden}
.pb .fill{height:100%;width:100%;transform-origin:0 50%;background:var(--olive)}
.vl{position:absolute;top:640px;text-align:center;transform:translateX(-50%)}
/* S6 */
.bubble{position:absolute;left:80px;top:110px;max-width:900px;padding:22px 30px;border-radius:24px 24px 24px 6px;background:rgba(237,230,214,.96);color:#15170F;font-weight:600;font-size:40px;line-height:1.28;box-shadow:0 18px 50px rgba(0,0,0,.5)}
.bubble .who{font-family:'JetBrains Mono',monospace;font-size:20px;letter-spacing:.14em;color:#7A6A3A;margin-bottom:8px}
.res{position:absolute;right:70px;top:110px}
.grid6{position:absolute;left:160px;top:190px;width:1600px;display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.grid6 .g{position:relative;height:300px;border-radius:10px;overflow:hidden;border:1px solid var(--line)}
.grid6 .g img{width:100%;height:100%;object-fit:cover}
.grid6 .g span{position:absolute;left:10px;bottom:10px;font-family:'JetBrains Mono',monospace;font-size:20px;background:rgba(12,13,8,.8);color:var(--amber);padding:4px 10px;border-radius:4px}
/* S7 */
#s7shade{position:absolute;inset:0;background:rgba(14,15,10,.78)}
#cgrid{position:absolute;left:120px;right:120px;top:170px;display:grid;grid-template-columns:repeat(4,1fr);gap:28px}
.cnt{background:rgba(34,38,26,.9);border:1px solid var(--line);border-radius:14px;padding:28px 26px;height:230px}
.cnt .cn{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:88px;color:var(--amber);line-height:1;white-space:nowrap}
.cnt .cn small{font-size:36px;margin-left:10px;color:var(--ink)}
.cnt .cl{font-size:30px;font-weight:600;margin-top:20px;color:var(--ink)}
/* S8 */
#s8img{position:absolute;right:0;top:0;width:1000px;height:1080px;overflow:hidden}
#s8img img{width:100%;height:100%;object-fit:cover;object-position:50% 40%}
#s8fade{position:absolute;right:0;top:0;width:1000px;height:1080px;background:linear-gradient(90deg,#15170F 0%,rgba(21,23,15,.2) 45%,rgba(21,23,15,0) 100%)}
#black{position:absolute;inset:0;background:#000;opacity:0;z-index:10}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__END__" data-width="1920" data-height="1080" data-fps="30">
<div id="bg"><div id="bggrid"></div></div>
__VIDEOS__

<!-- S0 -->
<div class="scene clip" id="s0" data-start="0" data-duration="14" data-track-index="1">
  <div id="s0shade"></div>
  <div id="s0title">
    <div class="row"><span id="t0a">0 навыков в 3D</span><span class="arr" id="t0b">→</span><span id="t0c">1 вечер</span></div>
    <div class="row" style="margin-top:22px"><span class="arr" id="t0d">→</span><span id="t0e" class="amber">вот это</span></div>
  </div>
</div>

<!-- S1 -->
<div class="scene clip" id="s1" data-start="14" data-duration="19" data-track-index="1">
  <div class="chap"><b>01</b>ИДЕЯ</div>
  <div id="s1a">
    <div class="img" id="inspo" style="left:160px;top:170px;width:960px;height:540px"><img src="assets/inspo.jpg" /></div>
    <div class="lab" style="position:absolute;left:160px;top:730px">кадр из ролика-вдохновения</div>
    <div style="position:absolute;left:1180px;top:200px;width:640px">
      <div class="h2" style="margin-bottom:34px">Нейросети делают игру про&nbsp;боевых роботов</div>
      <div class="chip" id="ch1" style="margin:0 12px 16px 0">модели в Blender</div>
      <div class="chip" id="ch2" style="margin:0 12px 16px 0">звуки</div>
      <div class="chip" id="ch3">сборка в Unity</div>
    </div>
  </div>
  <div id="s1b">
    <div id="codebg">import bpy, bmesh
for i, rivet in enumerate(rivets):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.018, depth=0.01,
        location=rivet.co)
mat = make_steel(rust=0.35)
leg = build_leg(segments=7)
render(camera="three_quarter")
iou = compare(render, blueprint)
</div>
    <div style="position:absolute;left:160px;top:230px">
      <div class="lab" style="margin-bottom:24px">условие</div>
      <div class="rule" id="r1"><div class="x">✕</div><div class="t">Генераторы 3D-моделей<i></i></div></div>
      <div class="rule" id="r2"><div class="x">✕</div><div class="t">Скачанные ассеты<i></i></div></div>
      <div class="h1 amber" id="r3" style="margin-top:50px">Только код.</div>
    </div>
  </div>
</div>

<!-- S2 -->
<div class="scene clip" id="s2" data-start="33" data-duration="22" data-track-index="1">
  <div class="chap"><b>02</b>КАК УСТРОЕНО</div>
  <svg class="wires" id="wires">
    <path class="wire" id="w1" d="M 420 250 L 700 250" />
    <path class="wire" id="w2" d="M 1160 250 C 1260 250, 1260 150, 1380 150" />
    <path class="wire" id="w3" d="M 1160 250 L 1380 250" />
    <path class="wire" id="w4" d="M 1160 250 C 1260 250, 1260 350, 1380 350" />
  </svg>
  <div class="node" id="nS" style="left:120px;top:190px"><div class="n">Сергей</div><div class="d">задачи голосом</div></div>
  <div class="node main" id="nC" style="left:700px;top:180px;min-width:460px;padding:26px 34px"><div class="n">Claude</div><div class="d">главный агент · раздаёт работу</div></div>
  <div class="node" id="h1" style="left:1380px;top:110px;min-width:400px;padding:14px 24px"><div class="n" style="font-size:30px">Моделлер</div></div>
  <div class="node" id="h2" style="left:1380px;top:210px;min-width:400px;padding:14px 24px"><div class="n" style="font-size:30px">Звукорежиссёр</div></div>
  <div class="node" id="h3" style="left:1380px;top:310px;min-width:400px;padding:14px 24px"><div class="n" style="font-size:30px">Unity-агент</div></div>
  <svg class="wires" id="loop">
    <ellipse id="lpath" cx="960" cy="690" rx="560" ry="150" fill="none" stroke="#3A4029" stroke-width="3" />
    <circle id="ldot" cx="0" cy="0" r="14" fill="#E8A33A" />
    <g id="lbl1"><rect x="330" y="660" width="300" height="60" rx="10" fill="#22261A" stroke="#9DAA68" stroke-width="2"/><text x="480" y="699" text-anchor="middle">Python-скрипт</text></g>
    <g id="lbl2"><rect x="830" y="510" width="260" height="60" rx="10" fill="#22261A" stroke="#9DAA68" stroke-width="2"/><text x="960" y="549" text-anchor="middle">Blender</text></g>
    <g id="lbl3"><rect x="1290" y="660" width="300" height="60" rx="10" fill="#22261A" stroke="#9DAA68" stroke-width="2"/><text x="1440" y="699" text-anchor="middle">рендер</text></g>
    <g id="lbl4"><rect x="760" y="810" width="400" height="60" rx="10" fill="#22261A" stroke="#E8A33A" stroke-width="2"/><text x="960" y="849" text-anchor="middle">агент смотрит → правит</text></g>
  </svg>
  <div class="lab" id="loopn" style="position:absolute;left:0;right:0;top:672px;text-align:center;color:#E8A33A;font-size:30px">цикл <span id="loopc">×1</span></div>
</div>

<!-- S3 -->
<div class="scene clip" id="s3" data-start="55" data-duration="29" data-track-index="1">
  <div class="chap"><b>03</b>РОБОТ</div>
  <div id="vcount"><small>версия</small><span id="vtxt">v1</span></div>
  <div id="s3a">
    <div class="img" id="iv1" style="left:120px;top:150px;width:800px;height:600px"><div class="kb" id="kbv1"><img src="assets/v1.png" /></div></div>
    <div class="tag" id="tv1" style="left:140px;top:170px">v1</div>
    <div class="lab" id="lv1" style="position:absolute;left:120px;top:770px">«похож на робота… издалека»</div>
    <div class="img" id="isheet" style="left:1000px;top:150px;width:800px;height:666px;background:#000"><img src="assets/sheet.png" style="object-fit:contain" /></div>
    <div class="tag" id="tsheet" style="left:1020px;top:170px">чертёж · 4 вида</div>
  </div>
  <div id="s3b">
    <div class="img" id="icmp" style="left:160px;top:140px;width:1600px;height:661px;background:#fff"><img src="assets/compare.jpg" style="object-fit:contain" /><div id="scan"></div></div>
    <div class="meter" id="meter" style="top:830px">
      <div class="row"><span class="lab">силуэт сбоку vs чертёж · итерация <span id="iter" class="amber">1</span>/22</span><span class="big" id="iou">0%</span></div>
      <div class="bar"><div class="fill" id="ioufill"></div></div>
    </div>
  </div>
  <div id="s3c">
    <div class="img" style="left:120px;top:150px;width:760px;height:632px;background:#000"><img src="assets/ref.png" style="object-fit:contain"/></div>
    <div class="tag" style="left:140px;top:170px;background:#9DAA68">референс</div>
    <div class="img" style="left:920px;top:150px;width:880px;height:732px;background:#000"><div class="kb" id="kbv3"><img src="assets/v31.png" style="object-fit:contain"/></div></div>
    <div class="tag" style="left:940px;top:170px">v3.1 · код</div>
    <div style="position:absolute;left:120px;top:810px;display:flex;gap:16px">
      <div class="chip" id="c3a"><span class="mono">245 000</span> треугольников</div>
      <div class="chip" id="c3b">каждая заклёпка — кодом</div>
    </div>
  </div>
</div>

<!-- S4 -->
<div class="scene clip" id="s4" data-start="84" data-duration="14" data-track-index="1">
  <div class="chap"><b>04</b>ЗВУК</div>
  <div id="osc">__WF__</div>
  <div id="playhead"></div>
  <div class="lab" style="position:absolute;left:160px;top:930px;font-size:20px">mech_walk_v2_audio.wav · синтез кодом, без сэмплов</div>
  <div class="chip sfx" id="sf1" style="left:200px">удар металла</div>
  <div class="chip sfx" id="sf2" style="left:520px">гидравлика</div>
  <div class="chip sfx" id="sf3" style="left:800px">шаги</div>
  <div class="chip sfx" id="sf4" style="left:1000px;border-color:#9DAA68">синтез формулами</div>
</div>

<!-- S5 -->
<div class="scene clip" id="s5" data-start="98" data-duration="23" data-track-index="1">
  <div class="chap"><b>05</b>ОКРУЖЕНИЕ</div>
  <div id="s5a">
    <div class="img" style="left:160px;top:130px;width:1600px;height:800px"><div class="kb" id="kbenv"><img src="assets/env_early.png" style="position:absolute;inset:0"/><img id="envf" src="assets/env_final.png" style="position:absolute;inset:0"/></div></div>
    <div class="tag" id="envtag" style="left:180px;top:150px">ранний тест</div>
  </div>
  <div id="s5b" style="position:absolute;left:160px;top:240px;width:1600px">
    <div class="lab" style="margin-bottom:20px">два агента · одновременно</div>
    <div class="pb"><div class="top"><span>Агент А · город, блокпост</span><span class="mono" id="pbA">0 мин</span></div><div class="bar"><div class="fill" id="fA"></div></div></div>
    <div class="pb"><div class="top"><span>Агент Б · машины</span><span class="mono" id="pbB">0 мин</span></div><div class="bar"><div class="fill" id="fB" style="background:#E8A33A"></div></div></div>
    <div class="lab" style="margin-top:30px;color:#A39C8C;font-size:20px">шкала — минуты работы агента</div>
  </div>
  <div id="s5c">
    <div class="img" style="left:160px;top:150px;width:1600px;height:667px;background:#4a4a4a"><img src="assets/vehicles.png" style="object-fit:contain"/></div>
    <div class="vl" style="left:470px;top:300px"><div class="chip" id="vl1">грузовик</div></div>
    <div class="vl" style="left:880px;top:300px"><div class="chip" id="vl2">БТР</div></div>
    <div class="vl" style="left:1250px;top:300px"><div class="chip" id="vl3">джип</div></div>
    <div class="vl" style="left:1540px;top:300px"><div class="chip" id="vl4">седан</div></div>
    <div id="parts" style="position:absolute;left:160px;top:840px;display:flex;gap:16px">
      <div class="chip" style="border-color:#E5484D">колёса</div><div class="chip" style="border-color:#E5484D">двери</div><div class="chip" style="border-color:#E5484D">башня</div>
      <div class="lab" style="align-self:center;margin-left:14px">отдельные объекты — чтобы взрывать</div>
    </div>
  </div>
</div>

<!-- S6 -->
<div class="scene clip" id="s6" data-start="121" data-duration="29" data-track-index="1">
  <div class="chap"><b>06</b>РЕЖИССУРА СЛОВАМИ</div>
  <div id="s6intro" style="position:absolute;left:160px;top:330px">
    <div class="lab" style="margin-bottom:20px">промпт → сцена</div>
    <div class="h1">Кино — словами.<br/><span class="amber">Сцены — кодом.</span></div>
  </div>
  <div class="bubble" id="q1"><div class="who">СЕРГЕЙ</div>«Здание должно разлететься в&nbsp;щепки»</div>
  <div class="bubble" id="q2"><div class="who">СЕРГЕЙ</div>«Пусть он испуганно повернёт корпус»</div>
  <div class="bubble" id="q3"><div class="who">СЕРГЕЙ</div>«Ракета пролетает мимо камеры медленно, и&nbsp;на&nbsp;ней написано, что&nbsp;это ядерный заряд»</div>
  <div class="tag res" id="rs">→ кадр из фильма</div>
  <div class="grid6" id="g6">
    <div class="g"><img src="assets/st_01.png"/><span>shot_01_establish.py</span></div>
    <div class="g"><img src="assets/st_04b.png"/><span>shot_04b_building.py</span></div>
    <div class="g"><img src="assets/st_05a.png"/><span>shot_05a_jeep.py</span></div>
    <div class="g"><img src="assets/st_06c.png"/><span>shot_06c_bullet.py</span></div>
    <div class="g"><img src="assets/st_07.png"/><span>shot_07_impact.py</span></div>
    <div class="g"><img src="assets/st_08.png"/><span>shot_08_mushroom.py</span></div>
  </div>
</div>

<!-- S7 -->
<div class="scene clip" id="s7" data-start="150" data-duration="17" data-track-index="1">
  <div id="s7shade"></div>
  <div class="chap"><b>07</b>ИТОГ</div>
  <div id="cgrid">__CNT__</div>
</div>

<!-- S8 -->
<div class="scene clip" id="s8" data-start="167" data-duration="17" data-track-index="1">
  <div id="s8img"><div class="kb" id="kbv8"><img src="assets/v31.png"/></div></div>
  <div id="s8fade"></div>
  <div class="chap"><b>08</b>ДАЛЬШЕ</div>
  <div style="position:absolute;left:140px;top:300px;width:900px">
    <div class="lab" id="n1" style="margin-bottom:24px">следующий шаг</div>
    <div class="h1" id="n2">Unity <span class="amber">→</span> игра</div>
    <div class="h2" id="n3" style="margin-top:28px;color:#A39C8C;font-weight:600">робот переедет в движок, им&nbsp;можно будет управлять</div>
    <div class="chip" id="n4" style="margin-top:50px;background:#E8A33A;color:#15170F;font-weight:800">Подписывайтесь — покажу</div>
  </div>
</div>

__CAPS__
<div id="prog"></div>
<div id="black"></div>
</div>
<script>
const tl = gsap.timeline({ paused: true });
const END = __END__;
const show=(sel,t,d=0.5,from={opacity:0,y:24})=>tl.fromTo(sel,from,{opacity:1,y:0,x:0,scale:1,duration:d,ease:"power3.out"},t);
const hide=(sel,t,d=0.4)=>tl.to(sel,{opacity:0,duration:d,ease:"power2.in"},t);
const kb=(sel,t0,dur,s0=1.0,s1=1.08,x1=0,y1=0)=>tl.fromTo(sel,{scale:s0,x:0,y:0},{scale:s1,x:x1,y:y1,duration:dur,ease:"none"},t0);
tl.fromTo("#prog",{scaleX:0},{scaleX:1,duration:END,ease:"none"},0);

// ---------- S0 ----------
kb("#v0b",3.0,3.2,1.0,1.06); kb("#v0c",6.2,2.8,1.04,1.0); kb("#v0d",9.0,5.0,1.0,1.06);
tl.fromTo("#s0shade",{opacity:0},{opacity:0,duration:0.01},0);
tl.to("#s0shade",{opacity:1,duration:0.6},9.2);
show("#t0a",9.5,0.5); show("#t0b",10.2,0.3,{opacity:0,x:-20}); show("#t0c",10.4,0.5);
show("#t0d",11.4,0.3,{opacity:0,x:-20}); show("#t0e",11.6,0.6,{opacity:0,scale:1.2});
hide("#s0title",13.6,0.35);

// ---------- S1 ----------
show("#inspo",14.3,0.7,{opacity:0,scale:0.96}); kb("#inspo img",14.3,9,1.0,1.06);
show("#s1a .lab",14.7,0.4); show("#s1a .h2",15.0,0.6);
show("#ch1",__C1__,0.35,{opacity:0,scale:0.8}); show("#ch2",__C2__,0.35,{opacity:0,scale:0.8}); show("#ch3",__C3__,0.35,{opacity:0,scale:0.8});
hide("#s1a",23.9,0.45);
tl.set("#s1b",{opacity:0},0); tl.to("#s1b",{opacity:1,duration:0.3},24.3);
show("#codebg",24.3,1.0,{opacity:0,y:0});
show("#r1",24.9,0.4,{opacity:0,x:-30}); tl.fromTo("#r1 .t i",{scaleX:0},{scaleX:1,duration:0.35,ease:"power2.out"},26.6);
show("#r2",28.4,0.4,{opacity:0,x:-30}); tl.fromTo("#r2 .t i",{scaleX:0},{scaleX:1,duration:0.35,ease:"power2.out"},29.3);
show("#r3",30.5,0.5,{opacity:0,scale:1.15});

// ---------- S2 ----------
show("#nS",33.8,0.5);
tl.fromTo("#w1",{strokeDashoffset:300,opacity:0},{strokeDashoffset:0,opacity:1,duration:0.6},35.6);
show("#nC",36.1,0.6,{opacity:0,scale:0.9});
["#w2","#w3","#w4"].forEach((w,i)=>tl.fromTo(w,{opacity:0},{opacity:1,duration:0.4},__H1__-0.3+i*1.6));
show("#h1",__H1__,0.45,{opacity:0,x:40}); show("#h2",__H1__+1.6,0.45,{opacity:0,x:40}); show("#h3",__H1__+3.2,0.45,{opacity:0,x:40});
// wire flow: dash offset animation (deterministic)
tl.fromTo(".wire",{strokeDashoffset:0},{strokeDashoffset:-360,duration:19,ease:"none"},35.6);
tl.set("#loop",{opacity:0},0); tl.to("#loop",{opacity:1,duration:0.5},44.1);
tl.set("#loopn",{opacity:0},0); tl.to("#loopn",{opacity:1,duration:0.4},45.0);
["#lbl1","#lbl2","#lbl3","#lbl4"].forEach((s,i)=>show(s,44.3+i*0.9,0.4,{opacity:0,y:10}));
const LD={a:0}, cx=960, cy=690, rx=560, ry=150;
function placeDot(){ const a=LD.a; const ang=Math.PI - a*2*Math.PI; // start at left (script), go up (Blender), right (render), bottom (agent)
  const el=document.getElementById("ldot"); el.setAttribute("cx",cx+rx*Math.cos(ang)); el.setAttribute("cy",cy-ry*Math.sin(ang));
  document.getElementById("loopc").textContent="×"+(1+Math.floor(a)); }
tl.fromTo(LD,{a:0},{a:5.999,duration:10.5,ease:"none",onUpdate:placeDot},44.4);
placeDot();

// ---------- S3 ----------
show("#iv1",55.4,0.6,{opacity:0,scale:0.96}); kb("#kbv1",55.4,9,1.0,1.1,0,-20); show("#tv1",55.8,0.3); show("#lv1",58.6,0.4);
show("#isheet",59.9,0.6,{opacity:0,x:60}); show("#tsheet",60.3,0.3);
hide("#s3a",62.9,0.4);
tl.set("#s3b",{opacity:0},0); tl.to("#s3b",{opacity:1,duration:0.4},63.2);
tl.fromTo("#scan",{x:0},{x:1596,duration:2.2,ease:"sine.inOut",repeat:2,yoyo:true},63.4);
const IOU=__IOU__; const io={i:0};
function renderIou(){ const k=Math.min(IOU.length-1,Math.floor(io.i)); const v=IOU[k];
  document.getElementById("iter").textContent=String(k+1);
  document.getElementById("iou").textContent=Math.round(v*100)+"%";
  document.getElementById("ioufill").style.transform="scaleX("+v+")";
  document.getElementById("vtxt").textContent = k<10?"v3":"v3.1"; }
tl.set("#vtxt",{textContent:"v1"},55);
tl.fromTo(io,{i:0},{i:IOU.length-0.001,duration:7.2,ease:"none",onUpdate:renderIou},63.4);
renderIou(); tl.set("#vtxt",{textContent:"v1"},0);
hide("#s3b",70.5,0.4);
tl.set("#s3c",{opacity:0},0); tl.to("#s3c",{opacity:1,duration:0.5},70.8);
kb("#kbv3",70.8,13,1.0,1.08);
show("#c3a",71.6,0.4,{opacity:0,y:20}); show("#c3b",74.3,0.4,{opacity:0,y:20});

// ---------- S4 ----------
tl.set("#w_v4",{opacity:0},0); tl.to("#w_v4",{opacity:1,duration:0.4},84.0); tl.to("#w_v4",{opacity:0,duration:0.3},97.6);
show("#osc",84.3,0.5,{opacity:0,y:0});
tl.fromTo("#playhead",{x:0},{x:1600,duration:14,ease:"none"},84.0);
show("#sf1",__SF1__,0.35,{opacity:0,y:20}); show("#sf2",__SF2__,0.35,{opacity:0,y:20}); show("#sf3",__SF3__,0.35,{opacity:0,y:20}); show("#sf4",__SF4__,0.35,{opacity:0,y:20});
// light pulse on bars
for(let i=0;i<28;i++) tl.fromTo("#osc",{filter:"brightness(1.25)"},{filter:"brightness(1)",duration:0.3},84.2+i*0.5);

// ---------- S5 ----------
show("#s5a",98.0,0.5,{opacity:0,y:0}); kb("#kbenv",98.0,4.6,1.0,1.06);
tl.fromTo("#envf",{opacity:0},{opacity:1,duration:1.0,ease:"none"},100.2);
tl.set("#envtag",{textContent:"финал"},100.7);
hide("#s5a",102.5,0.4);
tl.set("#s5b",{opacity:0},0); tl.to("#s5b",{opacity:1,duration:0.4},102.7);
const pb={m:0};
function renderPb(){ const m=pb.m; const a=Math.min(m,3), b=Math.min(m,10);
  document.getElementById("pbA").textContent=(a>=3?"готово · ":"")+a.toFixed(0)+" мин";
  document.getElementById("pbB").textContent=(b>=10?"готово · ":"")+b.toFixed(0)+" мин";
  document.getElementById("fA").style.transform="scaleX("+(a/10)+")"; document.getElementById("fB").style.transform="scaleX("+(b/10)+")"; }
tl.fromTo(pb,{m:0},{m:10,duration:5.0,ease:"none",onUpdate:renderPb},103.0); renderPb();
hide("#s5b",108.3,0.4);
tl.set("#s5c",{opacity:0},0); tl.to("#s5c",{opacity:1,duration:0.4},108.4);
["#vl1","#vl3","#vl2","#vl4"].forEach((s,i)=>show(s,__VL__+i*0.75,0.35,{opacity:0,y:-16}));
show("#parts",112.2,0.5);

// ---------- S6 ----------
show("#s6intro",121.4,0.6); hide("#s6intro",125.4,0.3);
const Q=[["#q1",__Q1__,129.6],["#q2",__Q2__,133.0],["#q3",__Q3__,139.0]];
Q.forEach(([s,a,b])=>{ show(s,a,0.35,{opacity:0,y:20,scale:0.96}); hide(s,b,0.3); });
tl.set("#rs",{opacity:0},0);
[[126.4,129.5],[129.8,132.9],[133.2,138.9]].forEach(([a,b])=>{ tl.to("#rs",{opacity:1,duration:0.2},a+0.1); tl.to("#rs",{opacity:0,duration:0.2},b-0.2); });
kb("#v6a",126.4,2.8,1.0,1.05); kb("#v6b",129.8,2.65,1.0,1.05);
tl.set("#g6",{opacity:0},0);
tl.to("#g6",{opacity:1,duration:0.01},139.2);
tl.fromTo("#g6 .g",{opacity:0,scale:0.9},{opacity:1,scale:1,duration:0.4,stagger:0.25,ease:"power3.out"},139.2);

// ---------- S7 ----------
const nums=[6.5,7,0,1027,62,215,220];
const cnt={p:0};
function renderCnt(){ for(let i=0;i<nums.length;i++){ const p=Math.max(0,Math.min(1,(cnt.p - i*0.55)/1.4)); const e=1-Math.pow(1-p,3);
  const v=nums[i]*e; const el=document.querySelector("#cnt"+i+" b");
  el.textContent = i===0 ? v.toFixed(1).replace(".",",") : String(Math.round(v)); } }
tl.fromTo(".cnt",{opacity:0,y:30},{opacity:1,y:0,duration:0.45,stagger:0.55,ease:"power3.out"},151.0);
tl.fromTo(cnt,{p:0},{p:6*0.55+1.4,duration:6*0.55+1.4,ease:"none",onUpdate:renderCnt},151.0); renderCnt();
kb("#v7",150,17,1.0,1.06);

// ---------- S8 ----------
show("#s8img",167.0,0.8,{opacity:0,y:0}); kb("#kbv8",167,17,1.0,1.1,-30,0);
show("#n1",167.9,0.4); show("#n2",168.3,0.6,{opacity:0,y:30}); show("#n3",170.2,0.5); show("#n4",173.5,0.5,{opacity:0,scale:0.85});
tl.fromTo("#black",{opacity:0},{opacity:1,duration:1.6,ease:"none"},END-1.8);
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""

def main():
    caps1 = {c["text"]: c for c in VO["captions"]}
    iou_rows = [l.split("\t") for l in open(ROOT.parent / "blender/renders/v3_iou_log.tsv").read().strip().split("\n")[1:]]
    iou = [round(float(r[4]), 3) for r in iou_rows]
    # step-in from v1 baseline: start meter at value of first iteration
    rep = {
        "__END__": str(END), "__VIDEOS__": "\n".join(VIDEOS), "__CAPS__": CAP_HTML, "__WF__": WF_HTML, "__CNT__": CNT_HTML,
        "__IOU__": json.dumps(iou),
        "__C1__": str(at(1, 5.2)), "__C2__": str(at(1, 6.5)), "__C3__": str(at(1, 7.3)),
        "__H1__": str(at(2, 5.6)),
        "__SF1__": str(at(4, 2.1)), "__SF2__": str(at(4, 3.3)), "__SF3__": str(at(4, 4.1)), "__SF4__": str(at(4, 5.0)),
        "__VL__": str(at(5, 9.7)),
        "__Q1__": str(at(6, 3.8)), "__Q2__": str(at(6, 7.2)), "__Q3__": str(at(6, 10.6)),
    }
    html = HTML
    for k, v in rep.items():
        html = html.replace(k, v)
    (HERE / "how-agents/index.html").write_text(html)
    print("captions", len(CAPS), "iou", iou[0], iou[-1], "len", len(iou))
    for a, b, t in CAPS: print(f"{a:7.2f} {b:7.2f} {t}")

if __name__ == "__main__":
    main()
