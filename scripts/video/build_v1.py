#!/usr/bin/env python3
"""Generate HyperFrames index.html for HEAVY MECH (16:9 and 9:16) from one template."""
import json, sys, pathlib

HERE = pathlib.Path(__file__).parent
TOTAL = 46.0
VID_END = 42.79

# shot boundaries (render s) and 9:16 crop centre (fraction of source width)
SHOTS = [
    (0.0, 4.0, 0.47), (4.0, 8.4, 0.52), (8.4, 9.87, 0.57), (9.87, 14.0, 0.42),
    (14.0, 16.17, 0.36), (16.17, 19.7, 0.47), (19.7, 21.598, 0.55), (21.598, 23.0, 0.50),
    (23.0, 24.45, 0.42), (24.45, 25.25, 0.48), (25.25, 28.243, None), (28.243, 31.957, 0.42),
    (31.957, 35.258, 0.36), (35.258, 43.0, 0.47),
]

TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=__W__, height=__H__" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:__W__px;height:__H__px;overflow:hidden;background:#000}
#root{position:relative;width:100%;height:100%;overflow:hidden;background:#000;
  --amber:#F2A93B;--olive:#A9B66B;--red:#FF4545;--ink:#F3ECDD;
  font-family:'JetBrains Mono',monospace;color:var(--ink)}
#vwrap{position:absolute;left:0;top:0;width:__VW__px;height:__VH__px}
#cine{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.hud{position:absolute;inset:0;pointer-events:none;text-shadow:0 2px 8px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9)}
.mono{font-family:'JetBrains Mono',monospace}
.tag{display:inline-block;padding:6px 14px;border:2px solid var(--amber);background:rgba(10,10,6,.55);
  color:var(--amber);font-weight:700;letter-spacing:.12em;white-space:nowrap}
.panel{position:absolute;padding:16px 20px;border-left:3px solid var(--amber);background:rgba(8,9,5,.55)}
.panel .row{display:flex;gap:18px;font-size:__FS__px;line-height:1.5;white-space:nowrap}
.panel .k{color:var(--olive);min-width:__KW__px}
.panel .v{color:var(--ink);font-weight:700}
.small{font-size:__FSS__px;color:rgba(243,236,221,.65)}
/* chrome */
.corner{position:absolute;width:70px;height:70px;border-color:rgba(242,169,59,.8);border-style:solid;border-width:0}
.c-tl{left:__CI__px;top:__CIT__px;border-left-width:3px;border-top-width:3px}
.c-tr{right:__CI__px;top:__CIT__px;border-right-width:3px;border-top-width:3px}
.c-bl{left:__CI__px;bottom:__CIB__px;border-left-width:3px;border-bottom-width:3px}
.c-br{right:__CI__px;bottom:__CIB__px;border-right-width:3px;border-bottom-width:3px}
#chromeTL{position:absolute;left:__CTX__px;top:__CTY__px;font-size:__FSS__px;color:var(--amber);letter-spacing:.14em;white-space:nowrap}
#chromeTR{position:absolute;right:__CTX__px;top:__CTY__px;text-align:right;font-size:__FS__px;color:var(--ink);white-space:nowrap}
#rate{color:var(--amber);font-size:__FSS__px;letter-spacing:.1em}
#recdot{display:inline-block;width:14px;height:14px;border-radius:50%;background:var(--red);margin-right:10px;vertical-align:middle}
/* title */
#t1{position:absolute;left:__TX__px;top:__TY__px}
#t1name{font-family:'Oswald',sans-serif;font-weight:700;font-size:__TFS__px;line-height:1;letter-spacing:.08em;color:var(--ink);white-space:nowrap;display:flex;align-items:center}
#t1name span{display:inline-block;overflow:hidden;white-space:nowrap;max-width:0}
#t1cur{display:inline-block;width:__CURW__px;height:__CURH__px;background:var(--amber);margin-left:12px}
#t1unit{margin-top:18px;font-size:__TUFS__px;letter-spacing:.5em;color:var(--amber);white-space:nowrap}
#t1line{height:3px;background:var(--amber);margin-top:16px;width:0}
/* brackets box */
.box{position:absolute;left:0;top:0}
.box i{position:absolute;width:46px;height:46px;border:0 solid var(--amber)}
.box i:nth-child(1){left:0;top:0;border-left-width:4px;border-top-width:4px}
.box i:nth-child(2){right:0;top:0;border-right-width:4px;border-top-width:4px}
.box i:nth-child(3){left:0;bottom:0;border-left-width:4px;border-bottom-width:4px}
.box i:nth-child(4){right:0;bottom:0;border-right-width:4px;border-bottom-width:4px}
#lockbox i{border-color:var(--red)}
#lockbox .cross{position:absolute;left:50%;top:50%;width:26px;height:26px;margin:-13px 0 0 -13px;border:2px solid var(--red);border-radius:50%}
.lab{position:absolute;left:0;top:0;white-space:nowrap;font-weight:700;letter-spacing:.14em;font-size:__FS__px}
#locklab{color:var(--red)}
#destroyed{color:var(--ink);background:rgba(200,30,30,.75);padding:6px 16px;font-size:__FSB__px;letter-spacing:.2em}
/* salvo */
#msl .big{margin-top:6px;font-size:__BIG__px;font-weight:700;color:var(--amber);line-height:1}
#struct .bar{width:__BARW__px;height:14px;border:2px solid var(--ink);margin-top:10px;position:relative}
#struct .fill{position:absolute;left:0;top:0;bottom:0;background:var(--amber);width:100%}
#frag{position:absolute}
/* alarm */
#alarmframe{position:absolute;inset:14px;border:10px solid var(--red);box-shadow:inset 0 0 120px rgba(255,40,40,.45)}
#incoming{position:absolute;left:0;right:0;top:__ALY__px;text-align:center}
#incoming .tag{border-color:var(--red);color:#fff;background:rgba(170,20,20,.8);font-size:__FSB__px}
#warn{position:absolute;left:0;right:0;top:__WY__px;text-align:center}
#warn .tag{border:3px solid var(--red);color:var(--red);background:rgba(20,0,0,.6);font-size:__WFS__px;padding:12px 28px}
/* callout */
#callout{position:absolute;left:0;top:0;width:100%;height:100%}
#cdot{position:absolute;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border:3px solid var(--amber);border-radius:50%}
#cline{position:absolute;left:0;top:0;height:3px;background:var(--amber);transform-origin:0 50%}
#clabel{position:absolute;left:0;top:0;padding:14px 20px;background:rgba(8,9,5,.72);border:2px solid var(--amber)}
#clabel .t{font-size:__FSB__px;font-weight:700;color:var(--amber);letter-spacing:.08em;white-space:nowrap;display:flex;align-items:center;gap:14px}
#clabel .s{font-size:__FS__px;color:var(--ink);margin-top:6px;white-space:nowrap}
.rad{width:__RAD__px;height:__RAD__px}
/* lost */
#flash{position:absolute;inset:0;background:#fff;opacity:0}
#noise{position:absolute;inset:-10%;opacity:0;mix-blend-mode:screen;
 background:repeating-linear-gradient(0deg,rgba(255,255,255,.18) 0 2px,rgba(0,0,0,.25) 2px 4px)}
#bars{position:absolute;inset:0;opacity:0}
#bars div{position:absolute;left:0;width:100%;background:rgba(255,255,255,.35);mix-blend-mode:difference}
#lostwrap{position:absolute;left:0;right:0;top:__LY__px;text-align:center}
#lost{position:relative;display:inline-block;font-family:'Oswald',sans-serif;font-weight:700;font-size:__LFS__px;letter-spacing:.12em;color:#fff;white-space:nowrap}
#lost span{position:absolute;left:0;top:0}
#lost span:nth-child(1){color:#ff2b2b;mix-blend-mode:screen}
#lost span:nth-child(2){color:#22e0ff;mix-blend-mode:screen}
#lostsub{font-size:__FS__px;letter-spacing:.3em;color:var(--red);margin-top:8px}
/* final */
#black{position:absolute;inset:0;background:#000;opacity:0}
#scrim{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.15) 0%,rgba(0,0,0,.55) 30%,rgba(0,0,0,.55) 65%,rgba(0,0,0,.15) 100%)}
#final{position:absolute;left:0;right:0;top:__FY__px;text-align:center;padding:0 60px}
.fl{font-family:'Montserrat',sans-serif;font-weight:700;font-size:__FFS__px;line-height:1.25;color:var(--ink)}
.fl2{font-family:'Montserrat',sans-serif;font-weight:500;font-size:__FFS2__px;color:rgba(243,236,221,.85);margin-top:14px}
#final2{position:absolute;left:0;right:0;top:__FY2__px;text-align:center}
#final2 .m{font-size:__FFS3__px;letter-spacing:.18em;color:var(--amber);font-weight:700}
/* overlays */
#grain{position:absolute;inset:-50%;opacity:.10;
 background:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.7' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
#vig{position:absolute;inset:0;background:radial-gradient(ellipse at center,transparent 50%,rgba(0,0,0,.55) 100%)}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__TOTAL__" data-width="__W__" data-height="__H__" data-fps="24">
  <div id="vwrap">
    <video id="cine" class="clip" src="assets/cine.mp4" muted playsinline data-start="0" data-duration="__VEND__" data-track-index="0"></video>
  </div>

  <div id="chrome" class="hud clip" data-start="3.6" data-duration="24.7" data-track-index="2">
    <div class="corner c-tl"></div><div class="corner c-tr"></div><div class="corner c-bl"></div><div class="corner c-br"></div>
    <div id="chromeTL">UNIT 07 · FCS ONLINE</div>
    <div id="chromeTR"><span id="recdot"></span><span id="tc">T+00:00.00</span><div id="rate">×1.00</div></div>
  </div>

  <div id="title1" class="hud clip" data-start="0" data-duration="4.0" data-track-index="3">
    <div id="t1">
      <div id="t1name"><span id="t1txt">HEAVY MECH</span><i id="t1cur"></i></div>
      <div id="t1line"></div>
      <div id="t1unit">UNIT 07</div>
    </div>
  </div>

  <div id="mechhud" class="hud clip" data-start="4.15" data-duration="4.2" data-track-index="3">
    <div id="mechbox" class="box"><i></i><i></i><i></i><i></i></div>
    <div id="mechpanel" class="panel">
      <div class="row"><span class="k">HEIGHT</span><span class="v">9.0 m</span></div>
      <div class="row"><span class="k">MASS</span><span class="v">62 t*</span></div>
      <div class="row"><span class="k">STATUS</span><span class="v" style="color:var(--olive)">ACTIVE</span></div>
      <div class="small" style="margin-top:8px">* условная масса</div>
    </div>
  </div>

  <div id="lockhud" class="hud clip" data-start="8.4" data-duration="1.47" data-track-index="3">
    <div id="lockbox" class="box"><i></i><i></i><i></i><i></i><div class="cross"></div></div>
    <div id="locklab" class="lab">ACQUIRING…</div>
  </div>
  <div id="desthud" class="hud clip" data-start="10.05" data-duration="2.6" data-track-index="3">
    <div id="destroyed" class="lab">DESTROYED</div>
  </div>

  <div id="salvo" class="hud clip" data-start="14.0" data-duration="5.65" data-track-index="3">
    <div id="msl" class="panel">
      <div class="small" style="color:var(--olive)">MSL READY</div>
      <div class="big"><span id="mslv">6</span><span class="small"> / 6</span></div>
    </div>
    <div id="struct" class="panel">
      <div class="row"><span class="k">STRUCTURE</span><span class="v" id="structv">100%</span></div>
      <div class="bar"><div class="fill" id="structfill"></div></div>
    </div>
    <div id="frag" class="tag">220 FRAGMENTS</div>
  </div>

  <div id="alarm" class="hud clip" data-start="19.7" data-duration="3.3" data-track-index="3">
    <div id="alarmframe"></div>
    <div id="incoming"><span class="tag">INCOMING FIRE · APC</span></div>
  </div>

  <div id="warnhud" class="hud clip" data-start="23.0" data-duration="2.3" data-track-index="3">
    <div id="alarmframe2" style="position:absolute;inset:14px;border:6px solid var(--red)"></div>
    <div id="warn"><span class="tag">WARNING · MISSILE LOCK</span></div>
  </div>

  <div id="callhud" class="hud clip" data-start="25.35" data-duration="2.85" data-track-index="3">
    <div id="callout">
      <div id="cline"></div>
      <div id="cdot"></div>
      <div id="clabel">
        <div class="t"><svg class="rad" viewBox="-50 -50 100 100"><circle r="48" fill="#F2A93B"/><circle r="9" fill="#111"/>
          <g fill="#111"><path d="M0 0 L-20.5 -35.5 A41 41 0 0 1 20.5 -35.5Z" transform="translate(0,-2)"/><path d="M0 0 L-20.5 -35.5 A41 41 0 0 1 20.5 -35.5Z" transform="rotate(120) translate(0,-2)"/><path d="M0 0 L-20.5 -35.5 A41 41 0 0 1 20.5 -35.5Z" transform="rotate(240) translate(0,-2)"/></g><circle r="13" fill="#F2A93B"/><circle r="9" fill="#111"/></svg>W-12 TAC-NUKE</div>
        <div class="s">YIELD 0.3 kt</div>
      </div>
    </div>
  </div>

  <div id="losthud" class="hud clip" data-start="28.28" data-duration="6.9" data-track-index="4">
    <div id="noise"></div>
    <div id="bars"><div style="top:18%;height:5%"></div><div style="top:44%;height:2%"></div><div style="top:61%;height:8%"></div><div style="top:83%;height:3%"></div></div>
    <div id="lostwrap"><div id="lost"><span>SIGNAL LOST</span><span>SIGNAL LOST</span>SIGNAL LOST</div><div id="lostsub">UNIT 07 · NO TELEMETRY</div></div>
    <div id="flash"></div>
  </div>

  <div id="endhud" class="hud clip" data-start="35.6" data-duration="10.4" data-track-index="5">
    <div id="scrim"></div><div id="black"></div>
    <div id="final"><div class="fl" id="fl1">Создано ИИ-агентами.</div><div class="fl2" id="fl2">Без единого готового ассета.</div></div>
    <div id="final2"><div class="m" id="fm">BLENDER · КОД · 1 ВЕЧЕР</div></div>
  </div>

  <div class="hud" id="ovl" style="z-index:50"><div id="vig"></div><div id="grain"></div></div>
</div>
<script>
const L = __LAYOUT__;
const SH = __SHOTS__;
const W=__W__, H=__H__, VW=__VW__, VH=__VH__;
const tl = gsap.timeline({ paused: true });
const $ = (s)=>document.querySelector(s);
// crop offset (x px of vwrap) for a given source-x centre fraction
function off(c){ if(L.portrait){ return Math.round(W/2 - c*VW); } return 0; }
// map source fraction -> canvas px under the crop active at that moment
function mx(fx,c){ return fx*VW + off(c); }
function my(fy){ return fy*VH; }
// --- shot crops (9:16) ---
if(L.portrait){
  SH.forEach(([a,b,c])=>{ if(c!==null) tl.set("#vwrap",{x:off(c)},a); });
}
// bullet-time: crop follows the rocket badge in portrait
const RK=[[25.7,0.44,0.51],[26.0,0.45,0.51],[26.83,0.465,0.51],[27.67,0.52,0.49],[28.15,0.58,0.49]];
const rc=(fx)=>Math.min(0.62,Math.max(0.36,fx-0.03));
if(L.portrait){
  tl.set("#vwrap",{x:off(rc(RK[0][1]))},25.25);
  for(let i=1;i<RK.length;i++) tl.to("#vwrap",{x:off(rc(RK[i][1])),duration:RK[i][0]-RK[i-1][0],ease:"none"},RK[i-1][0]);
}

// --- grain jitter (deterministic) ---
for(let i=0;i<__TOTAL__*12;i++){ const t=i/12; tl.set("#grain",{x:((i*37)%11-5)*14,y:((i*53)%13-6)*12},t); }

// --- title typing ---
tl.fromTo("#t1txt",{maxWidth:0},{maxWidth:L.tW,duration:1.3,ease:"steps(10)"},0.35);
tl.fromTo("#t1line",{width:0},{width:L.tW,duration:0.7,ease:"power2.out"},1.6);
tl.fromTo("#t1unit",{opacity:0},{opacity:1,duration:0.05},1.9);
for(let i=0;i<9;i++) tl.set("#t1cur",{opacity:i%2?1:0},0.1+i*0.4);
tl.to("#t1",{opacity:0,duration:0.35},3.6);

// --- ticker: timecode, missiles, structure ---
const SEG=[[0,25.25,0,25.25],[25.25,25.552,25.25,25.55],[25.552,28.102,25.55,25.6775],[28.102,28.243,25.6775,25.901],
           [28.243,31.957,25.901,26.774],[31.957,35.258,26.774,28.26],[35.258,46,28.26,38.99]];
function story(t){ for(const [a,b,s0,s1] of SEG){ if(t<=b) return s0+(s1-s0)*Math.max(0,(t-a))/(b-a); } return 38.99; }
function rate(t){ for(const [a,b,s0,s1] of SEG){ if(t<=b) return (s1-s0)/(b-a); } return 1; }
const MSL=[15.8,16.05,16.3,16.55];
const tick={t:0};
function render(t){
  const s=story(t); const mm=Math.floor(s/60), ss=s-mm*60;
  $("#tc").textContent="T+"+String(mm).padStart(2,"0")+":"+ss.toFixed(2).padStart(5,"0");
  const r=rate(t); $("#rate").textContent=(r<0.99?"SLOW-MO ":"")+"×"+r.toFixed(2);
  $("#rate").style.color = r<0.99 ? "#FF4545" : "#F2A93B";
  let n=6; MSL.forEach(m=>{ if(t>=m) n--; }); $("#mslv").textContent=String(n);
  const p = t<16.35?100: t>17.6?0: Math.round(100*(1-(t-16.35)/1.25));
  $("#structv").textContent=p+"%"; $("#structfill").style.width=p+"%";
  $("#structv").style.color = p<30 ? "#FF4545" : "#F3ECDD";
}
tl.fromTo(tick,{t:0},{t:__TOTAL__,duration:__TOTAL__,ease:"none",onUpdate:()=>render(tick.t)},0);
for(let i=0;i<60;i++) tl.set("#recdot",{opacity:i%2?0.25:1},3.6+i*0.5);

// --- mech box (shot 02) ---
const MB=L.mech; // [x,y,w,h] in canvas px
gsap.set("#mechbox",{left:MB[0],top:MB[1],width:MB[2],height:MB[3]});
gsap.set("#mechpanel",{left:L.mechPanel[0],top:L.mechPanel[1]});
tl.fromTo("#mechbox",{scale:1.12,opacity:0},{scale:1,opacity:1,duration:0.45,ease:"power3.out"},4.15);
tl.fromTo("#mechpanel",{opacity:0,x:-30},{opacity:1,x:0,duration:0.4,ease:"power2.out"},4.5);
tl.fromTo("#mechpanel .row",{opacity:0},{opacity:1,duration:0.05,stagger:0.18},4.6);
tl.to(["#mechbox","#mechpanel"],{opacity:0,duration:0.25},8.1);

// --- target lock (03a) truck track ---
const LK=[[8.4,0.65,0.53],[8.8,0.58,0.53],[9.3,0.515,0.53],[9.75,0.53,0.52]];
const cA = 0.57;
function lockPos(i){ return [mx(LK[i][1],cA), my(LK[i][2])]; }
const s0=lockPos(0);
gsap.set("#lockbox",{x:s0[0],y:s0[1],width:380,height:300,xPercent:-50,yPercent:-50});
gsap.set("#locklab",{x:s0[0],y:s0[1]+100});
for(let i=1;i<LK.length;i++){ const p=lockPos(i); tl.to("#lockbox",{x:p[0],y:p[1],duration:LK[i][0]-LK[i-1][0],ease:"none"},LK[i-1][0]);
  tl.to("#locklab",{x:p[0]-90,y:p[1]+60,duration:LK[i][0]-LK[i-1][0],ease:"none"},LK[i-1][0]); }
tl.to("#lockbox",{width:150,height:110,duration:0.75,ease:"power3.inOut"},8.4);
tl.set("#locklab",{textContent:"TARGET LOCKED"},9.15);
for(let i=0;i<6;i++) tl.set("#lockbox i",{opacity:i%2?0.3:1},9.15+i*0.1);
// destroyed (03b)
gsap.set("#destroyed",{x:mx(0.42,0.42),y:my(0.62),xPercent:-50});
tl.fromTo("#destroyed",{opacity:0,scale:1.4},{opacity:1,scale:1,duration:0.2,ease:"power4.out"},10.05);
tl.to("#destroyed",{opacity:0,duration:0.3},12.3);

// --- salvo ---
gsap.set("#msl",{left:L.msl[0],top:L.msl[1]});
gsap.set("#struct",{left:L.struct[0],top:L.struct[1]});
gsap.set("#frag",{left:L.frag[0],top:L.frag[1]});
tl.fromTo("#msl",{opacity:0,x:-30},{opacity:1,x:0,duration:0.35},14.2);
MSL.forEach(m=>tl.fromTo("#mslv",{scale:1.5,color:"#FF4545"},{scale:1,color:"#F2A93B",duration:0.2},m));
tl.to("#msl",{opacity:0,duration:0.3},16.9);
tl.fromTo("#struct",{opacity:0},{opacity:1,duration:0.3},16.25);
tl.fromTo("#frag",{opacity:0,scale:1.3},{opacity:1,scale:1,duration:0.2,ease:"power3.out"},17.65);
tl.to(["#struct","#frag"],{opacity:0,duration:0.3},19.3);

// --- alarm ---
for(let i=0;i<8;i++) tl.fromTo("#alarmframe",{opacity:1},{opacity:0.25,duration:0.4,ease:"sine.inOut"},19.7+i*0.41);
tl.fromTo("#incoming",{opacity:0,y:-20},{opacity:1,y:0,duration:0.2},19.75);
// --- missile lock warning: accelerating blink ---
gsap.set("#warn",{opacity:0});
let tt=23.0, per=0.36;
while(tt<25.25){ tl.set(["#warn","#alarmframe2"],{opacity:1},tt); tl.set(["#warn","#alarmframe2"],{opacity:0.3},tt+per*0.6); tt+=per; per=Math.max(0.09,per*0.86); }

// --- bullet-time callout ---
function rk(i){ const c = L.portrait ? rc(RK[i][1]) : 0; return [mx(RK[i][1],c), my(RK[i][2])]; }
function place(i){ const [x,y]=rk(i); const lx=x+L.cOff[0], ly=y+L.cOff[1];
  return {x,y,lx,ly,len:Math.hypot(lx-x,ly-y),ang:Math.atan2(ly-y,lx-x)*180/Math.PI}; }
const P0=place(0);
gsap.set("#cdot",{x:P0.x,y:P0.y}); gsap.set("#cline",{x:P0.x,y:P0.y,width:P0.len,rotation:P0.ang});
gsap.set("#clabel",{x:P0.lx,y:P0.ly,yPercent:-100});
for(let i=1;i<RK.length;i++){ const P=place(i), d=RK[i][0]-RK[i-1][0], at=RK[i-1][0];
  tl.to("#cdot",{x:P.x,y:P.y,duration:d,ease:"none"},at);
  tl.to("#cline",{x:P.x,y:P.y,width:P.len,rotation:P.ang,duration:d,ease:"none"},at);
  tl.to("#clabel",{x:P.lx,y:P.ly,duration:d,ease:"none"},at); }
tl.fromTo("#cdot",{scale:3,opacity:0},{scale:1,opacity:1,duration:0.3},25.72);
tl.fromTo("#cline",{scaleX:0},{scaleX:1,duration:0.35,ease:"power2.out"},25.85);
tl.fromTo("#clabel",{opacity:0},{opacity:1,duration:0.25},26.05);
tl.to("#callout",{opacity:0,duration:0.12},28.05);

// --- signal lost ---
tl.fromTo("#flash",{opacity:0},{opacity:1,duration:0.06},28.30);
tl.to("#flash",{opacity:0,duration:0.5,ease:"power2.in"},28.40);
tl.fromTo("#noise",{opacity:0},{opacity:0.9,duration:0.05},28.34);
tl.to("#noise",{opacity:0.25,duration:1.2},29.0);
for(let i=0;i<30;i++){ const t=28.34+i*0.083; tl.set("#noise",{y:((i*29)%17-8)*10},t);
  tl.set("#bars",{opacity:(i%3===0||i<8)?1:0,y:((i*41)%23-11)*18},t);
  tl.set("#lost span:nth-child(1)",{x:((i*7)%9-4)*(i<10?4:1.2)},t); tl.set("#lost span:nth-child(2)",{x:-((i*5)%9-4)*(i<10?4:1.2)},t); }
tl.set("#bars",{opacity:0},30.9);
tl.fromTo("#lostwrap",{opacity:0},{opacity:1,duration:0.05},28.5);
tl.to("#lostwrap",{scale:L.lostShrink,y:L.lostY,duration:0.6,ease:"power3.inOut"},31.0);
for(let i=0;i<8;i++) tl.set("#lostwrap",{opacity:i%2?0.35:1},31.6+i*0.45);
tl.to(["#lostwrap","#noise"],{opacity:0,duration:0.5},34.6);

// --- final titles ---
tl.fromTo("#scrim",{opacity:0},{opacity:1,duration:1.0},35.6);
tl.fromTo("#fl1",{opacity:0,y:20},{opacity:1,y:0,duration:0.8,ease:"power2.out"},36.0);
tl.fromTo("#fl2",{opacity:0,y:20},{opacity:1,y:0,duration:0.8,ease:"power2.out"},37.1);
tl.fromTo("#fm",{opacity:0,scale:1.12},{opacity:1,scale:1,duration:1.0,ease:"power2.out"},39.4);
tl.fromTo("#black",{opacity:0},{opacity:1,duration:1.0,ease:"none"},41.8);
tl.to(["#final","#final2"],{opacity:0,duration:0.8},45.0);
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""

LAYOUTS = {
  "16x9": dict(W=1920, H=1080, VW=1920, VH=1080, FS=30, FSS=24, FSB=38, KW=140, CI=40, CIT=40, CIB=40, CTX=70, CTY=58,
    TX=140, TY=640, TFS=150, TUFS=34, CURW=26, CURH=120, BIG=120, BARW=300, ALY=110, WY=120, WFS=56, RAD=44,
    LY=420, LFS=150, FY=380, FFS=64, FFS2=46, FY2=640, FFS3=40,
    L=dict(portrait=False, tW=900, mech=[420,120,1240,930], mechPanel=[80,560], msl=[80,820], struct=[1480,150], frag=[1500,300],
           cOff=[140,-170], lostShrink=0.35, lostY=-380)),
  "9x16": dict(W=1080, H=1920, VW=3413, VH=1920, FS=32, FSS=26, FSB=40, KW=150, CI=36, CIT=230, CIB=380, CTX=66, CTY=250,
    TX=80, TY=1240, TFS=128, TUFS=36, CURW=22, CURH=104, BIG=110, BARW=320, ALY=420, WY=420, WFS=54, RAD=48,
    LY=760, LFS=118, FY=700, FFS=64, FFS2=46, FY2=1120, FFS3=40,
    L=dict(portrait=True, tW=760, mech=[60,380,960,1300], mechPanel=[70,1460], msl=[70,1420], struct=[560,360], frag=[580,520],
           cOff=[-120,-260], lostShrink=0.45, lostY=-430)),
}

def build(layout, outdir):
    p = LAYOUTS[layout]
    html = TEMPLATE
    for k, v in p.items():
        if k == "L":
            continue
        html = html.replace(f"__{k}__", str(v))
    html = html.replace("__LAYOUT__", json.dumps(p["L"]))
    html = html.replace("__SHOTS__", json.dumps(SHOTS))
    html = html.replace("__TOTAL__", str(TOTAL)).replace("__VEND__", str(VID_END))
    assert "__" not in html.replace("__timelines", "").replace("__hyperframes", ""), [l for l in html.splitlines() if "__" in l and "__timelines" not in l][:5]
    (HERE / outdir / "index.html").write_text(html)
    print("wrote", outdir)

if __name__ == "__main__":
    build("16x9", "heavy-mech")
    build("9x16", "heavy-mech-916")
