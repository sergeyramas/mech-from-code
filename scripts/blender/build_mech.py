# Build the heavy mech. Run inside Blender: exec(open(path).read())
import os
import bpy
exec(open(os.path.expanduser('~/Documents/learning/mech-test/blender/scripts/mech_lib.py')).read())

COLL = 'HeavyMech'
# ---- clear previous build ----
coll = bpy.data.collections.get(COLL)
if coll:
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    coll = bpy.data.collections.new(COLL)
    bpy.context.scene.collection.children.link(coll)
for me in list(bpy.data.meshes):
    if me.users == 0:
        bpy.data.meshes.remove(me)

build_materials()

root = bpy.data.objects.new('mech_root', None)
root.empty_display_type = 'PLAIN_AXES'
root.empty_display_size = 1.0
coll.objects.link(root)

LX = 1.8
HIP_Z, KNEE_Z, ANK_Z = 5.0, 3.15, 1.0
DZ = 0.0  # upper body built at old height, shifted down
UOFF = (0, 0, DZ)
WAIST = (0, 0, 5.55)
OBJ = {}


def side_faces(s):
    return ('+x', '-x') if s > 0 else ('-x', '+x')


# ================= HIP =================
p = Part('hip', UOFF)
p.box((0, 0.05, 5.0), (2.0, 1.5, 0.9), mat='metal', bev=0.06)
p.cyl((0, 0, 5.0), 0.38, 2.6, rot=(0, 90, 0), mat='metal', n=20, bev=0.02)
p.plate((0, -0.82, 4.85), (1.1, 0.25, 0.95), rot=(-12, 0, 0), face='-y', cham=0.22)
p.decal((0, -0.82, 4.85), (1.1, 0.25, 0.95), (-12, 0, 0), '-y', 0, 0.05, 0.22, 0.6, mat='red')
p.plate((0, 0.85, 4.95), (1.3, 0.25, 0.8), rot=(10, 0, 0), face='+y', cham=0.15)
p.gear((0, 0, 5.5), 0.78, 0.18, teeth=22, mat='metal')
p.cyl((0, 0, 5.38), 0.6, 0.35, mat='steel', n=24)
for s in (-1, 1):
    p.plate((s * 0.75, -0.6, 4.75), (0.4, 0.3, 0.55), face='-y', mat='armor_dark', rivet=False, bev=0.04)
OBJ['hip'] = finish(p, (0, 0, 5.0), coll, root)

# ================= TORSO =================
p = Part('torso', UOFF)
p.box((0, 0.15, 6.8), (3.7, 2.6, 2.1), mat='metal', bev=0.08)
p.box((0, -0.15, 5.95), (2.3, 1.9, 0.65), mat='metal', bev=0.06)
p.grille((0, -1.06, 5.95), (1.5, 0.12, 0.42), n=5, face='-y')
for s in (-1, 1):
    p.plate((s * 1.0, -0.95, 5.95), (0.5, 0.35, 0.55), face='-y', mat='armor_dark', cham=0.08)
# chest centre + sides
p.plate((0, -1.25, 6.55), (1.25, 0.42, 1.35), rot=(8, 0, 0), face='-y', cham=0.28)
p.grille((0, -1.47, 6.45), (0.6, 0.06, 0.5), rot=(8, 0, 0), n=4)
for s in (-1, 1):
    c = (s * 1.3, -1.1, 6.78)
    sz = (1.45, 0.5, 1.85)
    r = (0, 0, s * 16)
    p.plate(c, sz, r, face='-y', cham=0.3)
    # lower belly plate under chest side
    p.plate((s * 1.05, -0.95, 5.72), (1.0, 0.35, 0.5), rot=(-15, 0, s * 12), face='-y', mat='armor_dark', cham=0.1)
    # side plates
    p.plate((s * 1.92, 0.05, 6.75), (0.25, 2.2, 1.75), face=side_faces(s)[0], cham=0.3)
    p.grille((s * 2.06, 0.15, 6.7), (0.05, 1.0, 0.9), face=side_faces(s)[0], n=6)
# red markings: big patch on L chest, stripe on R chest edge
p.decal((-1.3, -1.1, 6.78), (1.45, 0.5, 1.85), (0, 0, -16), '-y', -0.15, 0.1, 0.55, 1.1, mat='red')
p.decal((1.3, -1.1, 6.78), (1.45, 0.5, 1.85), (0, 0, 16), '-y', 0.5, 0.0, 0.18, 1.3, mat='red')
# extra angled upper-chest plates and pipes
for s in (-1, 1):
    p.plate((s * 0.78, -1.42, 7.48), (0.75, 0.28, 0.5), rot=(-25, 0, s * 10), face='-y', cham=0.12, spacing=0.18)
    p.plate((s * 0.55, -1.38, 5.95), (0.6, 0.25, 0.45), rot=(-10, 0, s * 8), face='-y', mat='armor', cham=0.1,
            spacing=0.18)
    for k in range(3):
        p.pipe((s * 2.08, -0.7 + k * 0.18, 7.4), (s * 2.08, -0.7 + k * 0.18, 6.0), r=0.045)
    p.pipe((s * 0.9, 1.88, 7.6), (s * 1.6, 1.4, 6.2), r=0.06)
# top deck
p.plate((0, 0.25, 7.88), (3.4, 2.3, 0.22), face='+z', cham=0.3)
for s in (-1, 1):
    p.plate((s * 0.85, -0.55, 7.75), (0.75, 0.9, 0.35), rot=(0, s * -8, 0), face='+z', mat='armor', cham=0.1)
    # sensor boxes
    p.box((s * 0.5, 0.6, 8.12), (0.32, 0.36, 0.28), mat='armor_dark', bev=0.03)
    p.box((s * 0.5, 0.41, 8.14), (0.2, 0.03, 0.1), mat='glass', bev=0.0)
    p.cyl((s * 0.95, 0.9, 8.3), 0.025, 0.6, mat='steel', n=6)
# back pack
p.plate((0, 1.55, 6.95), (2.9, 0.6, 1.7), face='+y', cham=0.3)
for s in (-1, 1):
    p.cyl((s * 0.75, 1.95, 7.2), 0.2, 0.9, mat='metal', n=16, bev=0.02)
    p.tube((s * 0.75, 1.95, 7.68), 0.17, 0.1, ring_mat='metal')
    p.piston((s * 0.3, 1.85, 6.4), (s * 0.3, 1.85, 7.5), 0.07)
p.grille((0, 1.82, 6.6), (1.2, 0.06, 0.6), face='+y', n=5)
# shoulder-joint sockets on torso sides
for s in (-1, 1):
    p.cyl((s * 1.95, 0, 6.75), 0.55, 0.3, rot=(0, 90, 0), mat='armor_dark', n=24, bev=0.03)
OBJ['torso'] = finish(p, WAIST, coll, OBJ['hip'], (0, 0, HIP_Z))

# ================= COCKPIT =================
p = Part('cockpit', UOFF)
CP = (0, -0.9, 7.25)
p.box((0, -1.2, 7.45), (1.35, 1.0, 0.8), mat='armor', bev=0.08, taper=(0.85, 0.85))
p.plate((0, -1.66, 7.67), (1.2, 0.22, 0.42), rot=(-28, 0, 0), face='-y', cham=0.12, spacing=0.2)
p.plate((0, -1.7, 7.2), (1.15, 0.22, 0.36), rot=(18, 0, 0), face='-y', cham=0.1, spacing=0.2)
p.box((0, -1.74, 7.43), (0.98, 0.1, 0.16), mat='glass', bev=0.015)
for i in range(4):
    p.box((-0.33 + i * 0.22, -1.79, 7.43), (0.15, 0.03, 0.075), mat='glow', bev=0.0)
for s in (-1, 1):
    p.plate((s * 0.68, -1.25, 7.45), (0.12, 0.85, 0.6), face=side_faces(s)[0], cham=0.1, spacing=0.2)
    p.grille((s * 0.85, -1.3, 7.15), (0.1, 0.4, 0.5), face=side_faces(s)[0], n=5)
    p.box((s * 0.69, -1.5, 7.55), (0.04, 0.12, 0.07), mat='glow', bev=0.0)
OBJ['cockpit'] = finish(p, CP, coll, OBJ['torso'], WAIST)

for side, s in (('L', -1), ('R', 1)):
    so, si = side_faces(s)
    SOFF = (s * 0.6, 0, 0.2)
    # ================= SHOULDER =================
    SH = (s * 1.9, 0, 6.75)
    p = Part('shoulder_' + side, SOFF)
    p.cyl((s * 2.05, 0, 6.75), 0.5, 0.5, rot=(0, 90, 0), mat='metal', n=24, bev=0.03)
    p.gear((s * 2.25, 0, 6.75), 0.58, 0.1, teeth=16, rot=(0, 90, 0))
    p.plate((s * 2.8, 0, 6.75), (1.35, 1.55, 0.45), face='+z', mat='armor_dark', cham=0.2)
    p.plate((s * 2.8, -0.82, 6.65), (1.2, 0.15, 0.35), face='-y', cham=0.08, spacing=0.2)
    OBJ['shoulder_' + side] = finish(p, SH, coll, OBJ['torso'], WAIST)

    # ================= LAUNCHER =================
    LP = (s * 2.8, 0, 7.0)
    p = Part('launcher_' + side, SOFF)
    cx, cy, cz = s * 2.85, -0.12, 7.72
    W, Dp, H = 1.45, 1.9, 1.38
    fy = cy - Dp / 2
    p.box((cx, cy, cz), (W, Dp, H), mat='armor_dark', bev=0.06)
    # front bezel
    p.box((cx, fy - 0.02, cz + H / 2 - 0.06), (W + 0.12, 0.3, 0.2), mat='armor', bev=0.04)
    p.box((cx, fy - 0.02, cz - H / 2 + 0.06), (W + 0.12, 0.3, 0.2), mat='armor', bev=0.04)
    for k in (-1, 1):
        p.box((cx + k * (W / 2 - 0.02), fy - 0.02, cz), (0.2, 0.3, H), mat='armor', bev=0.04)
    p.rivets((cx, fy - 0.02, cz + H / 2 - 0.06), (W + 0.12, 0.3, 0.2), face='-y', spacing=0.2, margin=0.06)
    p.rivets((cx, fy - 0.02, cz - H / 2 + 0.06), (W + 0.12, 0.3, 0.2), face='-y', spacing=0.2, margin=0.06)
    p.box((cx, fy + 0.02, cz), (W - 0.2, 0.1, H - 0.2), mat='metal', bev=0.0)
    for i in range(3):
        for j in range(3):
            p.tube((cx + (i - 1) * 0.37, fy - 0.02, cz + (j - 1) * 0.37), 0.155, 0.16, rot=(90, 0, 0))
    # side armour
    p.plate((cx + s * (W / 2 + 0.06), cy + 0.05, cz), (0.14, Dp - 0.25, H - 0.12), face=so, cham=0.2)
    p.plate((cx - s * (W / 2 + 0.05), cy + 0.05, cz), (0.12, Dp - 0.35, H - 0.25), face=si, cham=0.15,
            mat='armor')
    p.plate((cx, cy + 0.1, cz + H / 2 + 0.05), (W - 0.05, Dp - 0.3, 0.12), face='+z', cham=0.2)
    if s < 0:
        p.decal((cx + s * (W / 2 + 0.06), cy + 0.05, cz), (0.14, Dp - 0.25, H - 0.12), (0, 0, 0), so,
                -0.35, 0.0, 0.3, H - 0.3, mat='red')
    # back cap + small sensor
    p.box((cx, cy + Dp / 2 + 0.06, cz), (W - 0.25, 0.15, H - 0.25), mat='metal', bev=0.03)
    p.box((cx - s * 0.35, cy - 0.45, cz + H / 2 + 0.22), (0.3, 0.32, 0.22), mat='armor', bev=0.03)
    p.box((cx - s * 0.35, cy - 0.62, cz + H / 2 + 0.22), (0.2, 0.03, 0.08), mat='glass', bev=0.0)
    # mount bracket
    p.box((cx, cy + 0.2, 7.0), (0.7, 1.0, 0.2), mat='metal', bev=0.03)
    OBJ['launcher_' + side] = finish(p, LP, coll, OBJ['shoulder_' + side], SH)

    # ================= UPPER ARM =================
    AP = (s * 2.8, 0, 6.2)
    EL = (s * 2.85, -0.05, 5.1)
    p = Part('arm_' + side, SOFF)
    p.cyl(AP, 0.42, 0.95, rot=(0, 90, 0), mat='metal', n=20, bev=0.03)
    p.gear((s * 3.3, 0, 6.2), 0.46, 0.1, teeth=14, rot=(0, 90, 0))
    p.box((s * 2.85, 0.0, 5.65), (0.6, 0.7, 1.1), mat='metal', bev=0.04)
    p.plate((s * 2.85, -0.42, 5.7), (0.85, 0.22, 0.9), face='-y', cham=0.16, spacing=0.2)
    p.plate((s * 3.28, -0.02, 5.68), (0.15, 0.85, 0.85), face=so, cham=0.15, spacing=0.2)
    p.plate((s * 2.85, 0.4, 5.7), (0.8, 0.15, 0.8), face='+y', cham=0.12, rivet=False)
    p.piston((s * 2.42, 0.2, 6.05), (s * 2.42, 0.15, 5.25), 0.07)
    OBJ['arm_' + side] = finish(p, AP, coll, OBJ['shoulder_' + side], SH)

    if side == 'L':
        # ================= FIST (L) =================
        p = Part('fist_L', SOFF)
        fx = s * 3.0
        p.cyl(EL, 0.4, 0.95, rot=(0, 90, 0), mat='metal', n=20, bev=0.03)
        p.gear((s * 3.4, -0.05, 5.1), 0.42, 0.1, teeth=12, rot=(0, 90, 0))
        p.gear((s * 2.55, -0.05, 5.1), 0.36, 0.1, teeth=10, rot=(0, 90, 0))
        # forearm segment
        p.box((fx, -0.3, 4.6), (1.0, 1.1, 1.0), mat='metal', bev=0.05)
        p.plate((fx + s * 0.6, -0.3, 4.65), (0.24, 1.3, 1.05), face=so, cham=0.22)
        p.decal((fx + s * 0.6, -0.3, 4.65), (0.24, 1.3, 1.05), (0, 0, 0), so, 0.25, 0.0, 0.25, 0.8, mat='red')
        p.plate((fx - s * 0.56, -0.3, 4.65), (0.18, 1.1, 0.9), face=si, cham=0.15, mat='armor_dark')
        p.plate((fx, -0.92, 4.7), (1.05, 0.22, 0.9), face='-y', cham=0.18, spacing=0.2)
        p.plate((fx, 0.32, 4.65), (0.95, 0.2, 0.85), face='+y', cham=0.15)
        p.plate((fx, -0.3, 5.18), (1.1, 1.2, 0.16), face='+z', cham=0.2, spacing=0.2)
        p.spring((fx - s * 0.68, 0.05, 4.4), 0.12, 0.9, coils=8)
        p.piston((fx - s * 0.62, -0.75, 4.95), (fx - s * 0.62, -0.75, 3.75), 0.07)
        # wrist
        p.gear((fx, -0.35, 4.08), 0.62, 0.14, teeth=18, mat='metal')
        p.box((fx, -0.35, 4.08), (0.95, 0.95, 0.1), mat='armor_dark', bev=0.02)
        # hand block
        p.box((fx, -0.45, 3.55), (1.15, 1.25, 0.85), mat='metal', bev=0.05)
        p.plate((fx + s * 0.66, -0.45, 3.55), (0.24, 1.4, 0.95), face=so, cham=0.22)
        p.decal((fx + s * 0.66, -0.45, 3.55), (0.24, 1.4, 0.95), (0, 0, 0), so, -0.15, 0.1, 0.7, 0.22, mat='red')
        p.plate((fx - s * 0.62, -0.4, 3.6), (0.2, 1.0, 0.8), face=si, cham=0.15)
        p.plate((fx, 0.25, 3.6), (1.05, 0.2, 0.75), face='+y', cham=0.15, spacing=0.2)
        p.plate((fx, -0.45, 4.0), (1.15, 1.3, 0.12), face='+z', mat='armor_dark', cham=0.15, spacing=0.2)
        # knuckles + 3-segment fingers
        p.plate((fx, -1.15, 3.85), (1.2, 0.3, 0.3), face='-y', mat='armor_dark', cham=0.06, spacing=0.17, sub=False)
        for i in range(4):
            xi = fx + (i - 1.5) * 0.29
            p.plate((xi, -1.2, 3.55), (0.26, 0.42, 0.36), face='-y', cham=0.05, bev=0.03, spacing=0.15,
                    margin=0.06, sub=False)
            p.cyl((xi, -1.05, 3.33), 0.09, 0.25, rot=(0, 90, 0), mat='metal', n=10)
            p.box((xi, -1.08, 3.15), (0.25, 0.38, 0.32), rot=(-25, 0, 0), mat='armor', bev=0.03)
            p.box((xi, -0.78, 2.98), (0.23, 0.36, 0.24), rot=(-55, 0, 0), mat='armor_dark', bev=0.03)
            p.rivets((xi, -1.08, 3.15), (0.25, 0.38, 0.32), (-25, 0, 0), face='-y', spacing=0.12, margin=0.05,
                     r=0.02)
        if True:
            # thumb (inner side, 2 segments)
            p.box((fx - s * 0.66, -0.95, 3.45), (0.26, 0.45, 0.5), rot=(0, 0, 0), mat='armor', bev=0.04)
            p.box((fx - s * 0.6, -1.15, 3.12), (0.24, 0.35, 0.32), rot=(-30, 0, 0), mat='armor_dark', bev=0.03)
        p.box((fx - s * 0.71, -0.85, 4.85), (0.05, 0.12, 0.08), mat='glow', bev=0.0)
        OBJ['fist_L'] = finish(p, EL, coll, OBJ['arm_L'])
    else:
        # ================= CANNON (R) =================
        p = Part('cannon_R', SOFF)
        cx = s * 2.9
        p.cyl(EL, 0.5, 1.05, rot=(0, 90, 0), mat='metal', n=24, bev=0.03)
        p.gear((s * 3.45, -0.05, 5.1), 0.58, 0.14, teeth=16, rot=(0, 90, 0))
        p.cyl((s * 3.55, -0.05, 5.1), 0.3, 0.12, rot=(0, 90, 0), mat='armor_dark', n=16, bev=0.02)
        p.box((cx, -0.95, 5.2), (0.95, 1.5, 0.95), mat='metal', bev=0.05)
        p.plate((cx + 0.53, -0.95, 5.2), (0.15, 1.4, 0.88), face='+x', cham=0.15, spacing=0.2)
        p.plate((cx - 0.53, -0.95, 5.2), (0.15, 1.4, 0.88), face='-x', cham=0.15, spacing=0.2)
        p.plate((cx, -0.95, 5.73), (0.98, 1.45, 0.14), face='+z', cham=0.15, spacing=0.2)
        p.plate((cx, -1.72, 5.2), (1.05, 0.14, 1.05), face='-y', cham=0.2, spacing=0.2)
        # ammo drum / box on top
        p.cyl((cx, -0.6, 6.05), 0.32, 0.6, rot=(0, 90, 0), mat='armor_dark', n=20, bev=0.03)
        p.box((cx, -1.15, 5.95), (0.45, 0.5, 0.3), mat='metal', bev=0.03)
        for z in (5.43, 4.97):
            p.cyl((cx, -2.2, z), 0.2, 1.0, rot=(90, 0, 0), mat='metal', n=20, bev=0.02)
            for k in range(5):
                p.cyl((cx, -1.85 - k * 0.17, z), 0.225, 0.05, rot=(90, 0, 0), mat='armor_dark', n=20)
            p.cyl((cx, -3.4, z), 0.13, 1.6, rot=(90, 0, 0), mat='steel', n=18)
            for yy in (-2.95, -3.55):
                p.cyl((cx, yy, z), 0.16, 0.1, rot=(90, 0, 0), mat='metal', n=18, bev=0.01)
            p.cyl((cx, -4.15, z), 0.19, 0.36, rot=(90, 0, 0), mat='metal', n=18, bev=0.02)
            p.cyl((cx, -4.15, z), 0.105, 0.365, rot=(90, 0, 0), mat='muzzle', n=14)
            for k in range(4):
                p.box((cx, -4.08, z), (0.42, 0.06, 0.08), rot=(0, 45 * k, 0), mat='metal', bev=0.0)
        p.box((cx, -2.75, 5.2), (0.12, 0.3, 0.4), mat='armor_dark', bev=0.02)
        OBJ['cannon_R'] = finish(p, EL, coll, OBJ['arm_R'], AP)

    # ================= THIGH =================
    x = s * LX
    H = HIP_Z
    HP = (x, 0, H)
    p = Part('thigh_' + side)
    p.cyl(HP, 0.6, 0.9, rot=(0, 90, 0), mat='metal', n=24, bev=0.03)
    p.gear((x + s * 0.5, 0, H), 0.66, 0.12, teeth=16, rot=(0, 90, 0))
    p.cyl((x + s * 0.58, 0, H), 0.28, 0.12, rot=(0, 90, 0), mat='armor_dark', n=16, bev=0.02)
    p.box((x, 0.05, H - 0.85), (0.9, 0.95, 1.4), mat='metal', bev=0.05)
    p.plate((x, -0.55, H - 0.75), (1.45, 0.38, 1.3), rot=(-6, 0, 0), face='-y', cham=0.3)
    p.plate((x + s * 0.66, 0.0, H - 0.8), (0.28, 1.3, 1.2), face=so, cham=0.25)
    p.plate((x - s * 0.55, 0.0, H - 0.85), (0.2, 1.0, 0.95), face=si, mat='armor_dark', rivet=False)
    p.plate((x, 0.55, H - 0.7), (1.2, 0.3, 1.1), face='+y', cham=0.2)
    if side == 'R':
        p.decal((x, -0.55, H - 0.75), (1.45, 0.38, 1.3), (-6, 0, 0), '-y', 0.3, -0.15, 0.4, 0.7, mat='red')
    p.piston((x + s * 0.1, 0.72, H - 0.2), (x + s * 0.1, 0.65, KNEE_Z + 0.2), 0.1)
    p.piston((x + s * 0.62, -0.62, H - 0.35), (x + s * 0.62, -0.7, KNEE_Z + 0.25), 0.08)
    p.pipe((x - s * 0.55, 0.45, H - 0.3), (x - s * 0.55, 0.45, KNEE_Z + 0.3), r=0.05)
    p.gear((x - s * 0.48, 0, H), 0.5, 0.1, teeth=14, rot=(0, 90, 0))
    OBJ['thigh_' + side] = finish(p, HP, coll, OBJ['hip'])

    # ================= SHIN =================
    K = KNEE_Z
    A0 = ANK_Z
    KP = (x, 0, K)
    p = Part('shin_' + side)
    p.cyl(KP, 0.55, 1.1, rot=(0, 90, 0), mat='metal', n=24, bev=0.03)
    p.gear((x + s * 0.6, 0, K), 0.62, 0.13, teeth=16, rot=(0, 90, 0))
    p.gear((x - s * 0.6, 0, K), 0.5, 0.1, teeth=12, rot=(0, 90, 0))
    p.cyl((x + s * 0.7, 0, K), 0.3, 0.12, rot=(0, 90, 0), mat='armor_dark', n=16, bev=0.02)
    p.plate((x, -0.62, K + 0.05), (1.1, 0.38, 0.8), rot=(15, 0, 0), face='-y', cham=0.22, spacing=0.2)
    p.box((x, 0.05, (K + A0) / 2 + 0.1), (0.95, 0.95, K - A0 - 0.2), mat='metal', bev=0.05)
    p.plate((x, -0.6, K - 0.9), (1.55, 0.4, 1.35), rot=(-6, 0, 0), face='-y', cham=0.32)
    p.plate((x, -0.6, K - 1.78), (1.35, 0.36, 0.7), rot=(10, 0, 0), face='-y', cham=0.18, mat='armor_dark')
    p.plate((x + s * 0.72, 0.05, K - 1.05), (0.28, 1.3, 1.65), face=so, cham=0.28)
    p.plate((x - s * 0.6, 0.05, K - 0.9), (0.2, 1.05, 1.2), face=si, cham=0.18, mat='armor_dark', rivet=False)
    p.plate((x, 0.62, K - 0.85), (1.25, 0.38, 1.4), face='+y', cham=0.22)
    p.gear((x + s * 0.62, 0.0, K - 0.35), 0.3, 0.1, teeth=10, rot=(0, 90, 0))
    p.pipe((x - s * 0.55, -0.3, K - 0.3), (x - s * 0.55, -0.35, A0 + 0.5), r=0.05)
    p.pipe((x - s * 0.55, -0.1, K - 0.3), (x - s * 0.55, -0.15, A0 + 0.5), r=0.05)
    p.piston((x + s * 0.5, 0.65, K - 0.3), (x + s * 0.5, 0.6, ANK_Z + 0.35), 0.11)
    p.piston((x - s * 0.45, 0.65, K - 0.3), (x - s * 0.45, 0.6, ANK_Z + 0.35), 0.09)
    OBJ['shin_' + side] = finish(p, KP, coll, OBJ['thigh_' + side])

    # ================= FOOT =================
    A = ANK_Z
    FP = (x, 0, A)
    p = Part('foot_' + side)
    p.cyl(FP, 0.4, 1.0, rot=(0, 90, 0), mat='metal', n=20, bev=0.03)
    for dx in (-0.55, 0.55):
        p.gear((x + dx, 0, A), 0.46, 0.12, teeth=14, rot=(0, 90, 0))
    p.gear((x - s * 0.2, 0.85, 0.95), 0.36, 0.14, teeth=12, rot=(0, 90, 0))
    p.gear((x + s * 0.15, 0.78, 0.85), 0.3, 0.12, teeth=10, rot=(0, 90, 0))
    p.box((x, -0.25, 0.12), (2.1, 3.2, 0.24), mat='metal', bev=0.04)
    p.plate((x, -0.05, 0.6), (1.5, 1.6, 0.72), face='+z', cham=0.22)
    p.plate((x, -0.8, 0.62), (1.35, 0.22, 0.55), rot=(-30, 0, 0), face='-y', cham=0.12, spacing=0.2)
    for dx in (-0.68, 0.0, 0.68):
        p.plate((x + dx, -1.35, 0.42), (0.62, 1.05, 0.55), rot=(-8, 0, 0), face='+z', bev=0.06, cham=0.1)
        p.plate((x + dx, -1.88, 0.3), (0.56, 0.14, 0.42), rot=(-22, 0, 0), face='-y', mat='armor_dark',
                bev=0.03, spacing=0.16, margin=0.07)
    p.plate((x, 1.15, 0.42), (1.45, 0.65, 0.6), face='+z', bev=0.06, cham=0.14)
    p.plate((x + s * 0.98, -0.25, 0.45), (0.14, 2.1, 0.5), face=so, cham=0.1)
    p.plate((x - s * 0.98, -0.25, 0.45), (0.14, 2.1, 0.5), face=si, cham=0.1)
    OBJ['foot_' + side] = finish(p, FP, coll, OBJ['shin_' + side])

from mathutils import Matrix
OBJ['fist_L'].data.transform(Matrix.Scale(1.2, 4))
TS = Matrix.Diagonal((1.22, 1.12, 1.15, 1.0))
OBJ['torso'].data.transform(TS)
OBJ['cockpit'].data.transform(TS)
OBJ['cockpit'].location = TS.to_3x3() @ OBJ['cockpit'].location
for sd in ('L', 'R'):
    OBJ['launcher_' + sd].data.transform(Matrix.Scale(1.1, 4))
for sd in ('L', 'R'):
    for nm in ('thigh_', 'shin_', 'foot_'):
        OBJ[nm + sd].data.transform(Matrix.Diagonal((1.3, 1.2, 1.0, 1.0)))
# rest pose: fist arm swung forward like the reference
OBJ['arm_L'].rotation_euler.x = math.radians(-18)
OBJ['fist_L'].rotation_euler.x = math.radians(-12)
OBJ['arm_R'].rotation_euler.x = math.radians(-6)
OBJ['cannon_R'].rotation_euler.x = math.radians(6)
objs = [o for o in coll.objects if o.type == 'MESH']
print('objects', len(objs), 'tris', tri_count(objs))
print(sorted((o.name, o.parent.name if o.parent else None) for o in coll.objects))
