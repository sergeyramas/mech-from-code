from pathlib import Path
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
from scipy.ndimage import binary_fill_holes, gaussian_filter

ROOT = Path(__file__).parent
W, H = 1280, 720
PIL = Image.Resampling.LANCZOS
IMPACT = Image.open(ROOT / 'still_impact.png').convert('RGB')
ROCKET = Image.open(ROOT / 'still_rocket.png').convert('RGB')
MECH = Image.open(ROOT / 'mech.png').convert('RGB')
FONT = '/System/Library/Fonts/Supplemental/Impact.ttf'
MONO = '/System/Library/Fonts/Supplemental/Andale Mono.ttf'


def cover(im, size):
    sw, sh = im.size
    tw, th = size
    k = max(tw / sw, th / sh)
    im = im.resize((math.ceil(sw*k), math.ceil(sh*k)), PIL)
    left = (im.width-tw)//2
    top = (im.height-th)//2
    return im.crop((left, top, left+tw, top+th))


def background(variant):
    # A real impact frame provides the ruined checkpoint and real debris.
    src = IMPACT.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if variant == 1 else IMPACT
    bg = cover(src, (W,H)).filter(ImageFilter.GaussianBlur(5))
    ar = np.asarray(bg).astype(np.float32)
    grey = ar.mean(2, keepdims=True)
    ar = .43*ar + .57*grey
    ar *= np.array([.42,.55,.62], np.float32)
    yy,xx = np.mgrid[0:H,0:W]
    cx,cy = (915,350) if variant == 1 else (910,330)
    glow = np.exp(-(((xx-cx)/260)**2+((yy-cy)/210)**2)*1.3)
    ar += glow[...,None]*np.array([120,48,3],np.float32)
    core=np.exp(-(((xx-cx)/110)**2+((yy-cy)/105)**2)*1.7)
    ar += core[...,None]*np.array([115,83,19],np.float32)
    # Dark vignette keeps the pale blast from washing out the subjects.
    vg = np.clip(1-.48*((xx-W/2)/(W/2))**2-.43*((yy-H/2)/(H/2))**2,.34,1)
    ar *= vg[...,None]
    return Image.fromarray(np.uint8(np.clip(ar,0,255)),'RGB').convert('RGBA')


def mech_cutout():
    ar = np.asarray(MECH).astype(np.float32)
    luma = ar.max(2)
    # Its source background is nearly pure black. Retain dark armour by
    # filling enclosed gaps after identifying the outer silhouette.
    binary = luma > 17
    binary = binary_fill_holes(binary)
    mask = np.uint8(np.clip(gaussian_filter(binary.astype(float),1.1)*255,0,255))
    rgba = MECH.convert('RGBA')
    rgba.putalpha(Image.fromarray(mask,'L'))
    return rgba.crop((55,42,1360,1100))


def rocket_cutout():
    # Tight hand traced matte follows the actual missile body and fins.
    box = (0,345,1920,760)
    crop = ROCKET.crop(box).convert('RGBA')
    pts = [
        (0,1),(75,6),(170,12),(340,22),(520,34),(760,46),
        (920,55),(980,17),(1030,19),(1145,102),(1160,77),
        (1280,75),(1328,81),(1450,96),(1600,125),(1750,163),
        (1880,188),(1919,198),(1919,305),(1850,324),(1700,350),
        (1510,355),(1360,350),(1290,345),(1165,346),
        (1120,389),(1010,414),(950,338),(800,323),(530,307),
        (260,298),(0,267)
    ]
    mask = Image.new('L',crop.size)
    ImageDraw.Draw(mask).polygon(pts,fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(2.0))
    crop.putalpha(mask)
    return crop


def orange_rim(img, x, y, blur=8):
    alpha = img.getchannel('A')
    dilated = alpha.filter(ImageFilter.MaxFilter(15))
    edge = np.maximum(np.asarray(dilated).astype(np.int16)-np.asarray(alpha).astype(np.int16),0)
    rim = Image.new('RGBA',img.size,(255,123,20,0))
    rim.putalpha(Image.fromarray(np.uint8(edge),'L').filter(ImageFilter.GaussianBlur(blur)))
    return rim


def fade_bottom(img, depth=70):
    alpha=np.asarray(img.getchannel('A')).copy()
    ramp=np.clip((img.height-1-np.arange(img.height))/depth,0,1)
    alpha=np.uint8(alpha*ramp[:,None])
    img.putalpha(Image.fromarray(alpha,'L'))
    return img


def streaks(base, variant):
    layer = Image.new('RGBA',(W,H))
    d = ImageDraw.Draw(layer)
    rng = np.random.default_rng(22+variant)
    for _ in range(48):
        x = int(rng.integers(30,1250)); y = int(rng.integers(295,635))
        if x < 500: continue
        le = int(rng.integers(9,44)); width = int(rng.integers(1,4))
        d.line((x,y,x-le,y+le*.18),fill=(255,181,84,int(rng.integers(75,180))),width=width)
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(.45)))


def fit_font(text, limit, desired):
    for size in range(desired,20,-1):
        ft=ImageFont.truetype(FONT,size)
        if ImageDraw.Draw(Image.new('RGB',(1,1))).textbbox((0,0),text,font=ft,stroke_width=5)[2] <= limit:
            return ft
    return ft


def labels(base):
    shadow = Image.new('RGBA',(W,H))
    ds=ImageDraw.Draw(shadow)
    txt=Image.new('RGBA',(W,H))
    d=ImageDraw.Draw(txt)
    lines=[('Я НЕ УМЕЮ',37,fit_font('Я НЕ УМЕЮ',670,94)),('3D',133,ImageFont.truetype(FONT,105))]
    for s,y,f in lines:
        ds.text((48,y+8),s,font=f,fill=(0,0,0,220),stroke_width=10,stroke_fill=(0,0,0,230))
        d.text((43,y),s,font=f,fill='white',stroke_width=6,stroke_fill=(2,5,9))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9)))
    base.alpha_composite(txt)
    tag=Image.new('RGBA',(W,H)); td=ImageDraw.Draw(tag)
    td.polygon([(36,257),(515,245),(529,305),(44,317)],fill=(4,7,9,245),outline=(255,196,0,255),width=3)
    tag=tag.filter(ImageFilter.GaussianBlur(.25)); base.alpha_composite(tag)
    d=ImageDraw.Draw(base)
    f=fit_font('ЭТО СДЕЛАЛ ИИ',449,50)
    d.text((58,249),'ЭТО СДЕЛАЛ ИИ',font=f,fill='#FFC400',stroke_width=1,stroke_fill='#FFC400')
    # Bottom-left micro label sits safely above the YouTube controls.
    badge=(37,657,576,704)
    d.rounded_rectangle(badge,radius=3,fill=(4,9,12,226),outline=(243,166,45,255),width=2)
    bf=ImageFont.truetype(MONO,22)
    d.text((50,669),'BLENDER · 0 МОДЕЛЕЙ ИЗ ИНТЕРНЕТА',font=bf,fill='#FFBD59')


def make(variant):
    if variant == 2:
        plate=Image.open(ROOT/'thumbnail_v2_plate.png').convert('RGB')
        canvas=cover(plate,(W,H)).convert('RGBA')
        # All Cyrillic remains native code-rendered type over the visual plate.
        labels(canvas)
        return canvas.convert('RGB')
    canvas=background(variant)
    mech=mech_cutout()
    mech=fade_bottom(mech.resize((730,592),PIL).crop((0,0,730,465)))
    canvas.alpha_composite(orange_rim(mech,0,0), (620,163))
    canvas.alpha_composite(mech,(620,163))
    rocket=rocket_cutout().resize((1040,225),PIL)
    rocket=rocket.rotate(-7,resample=Image.Resampling.BICUBIC,expand=True)
    canvas.alpha_composite(rocket,(-86,341))
    streaks(canvas,variant)
    labels(canvas)
    return canvas.convert('RGB')


if __name__=='__main__':
    for v in (1,2):
        image=make(v)
        image.save(ROOT/f'thumbnail_v{v}.png',optimize=True)
        image.resize((320,180),PIL).save(ROOT/f'thumbnail_v{v}_small.png',optimize=True)
