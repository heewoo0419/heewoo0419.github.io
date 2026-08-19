#!/usr/bin/env python3
"""표지 손글씨(Our Wedding Day)를 획 순서대로 쓰이는 SVG 로 만들어 index.html 에 심습니다.

왜 SVG 인가
  폰트 텍스트로는 글자 하나하나를 잡을 수 없어 획을 따라 쓰이게 만들 수 없습니다.
  글리프를 path 로 떠서 심으면 글자마다 마스크를 걸 수 있고, Bluekendy 폰트 자체를
  배포에서 뺄 수 있습니다(이 손글씨에만 쓰이던 폰트라 — 옛 화면은 Rockville Solid).

어떻게 획 순서를 알아내는가
  폰트에는 외곽선만 있고 '펜이 지나간 길'은 없습니다. 그래서
    1. 글자를 이미지로 굽고
    2. 세선화(Zhang-Suen)로 1픽셀 뼈대를 만들고
    3. 끝점에서 시작해 이웃을 따라가며 순서 있는 궤적으로 잇습니다.
  그 궤적을 굵은 선으로 그려 마스크로 쓰면, 마스크가 열리는 만큼 원본 글자가
  드러납니다. 보이는 것은 언제나 원본이라 글자 모양이 변하지 않습니다.

  자동 추출은 궤적의 모양까지입니다. '어느 쪽에서 시작해 어느 획부터 쓰는지' 는
  알지 못하므로, 눈으로 보고 아래 REVERSE / SPLIT / ORDER 에 적어 고칩니다.

쓰는 법
    pip install fonttools pillow uharfbuzz
    python3 tools/build-cover-handwriting.py          # index.html 을 고칩니다
    python3 tools/build-cover-handwriting.py --dry    # 결과만 보고 파일은 두기
  고친 뒤에는 tools/stamp-assets.py 로 ?v= 를 다시 찍으세요.

  글자를 바꾸면 LINES 를 고치고, 새 글자의 획이 어색하면 아래 표에 한 줄 더합니다.
  획 번호를 확인하려면 --debug 로 궤적 그림을 저장해 보세요.
"""
import argparse
import pathlib
import re
import sys

try:
    import uharfbuzz as hb
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:                                  # noqa: BLE001
    sys.exit(f"필요한 패키지가 없습니다: {e}\n  pip install fonttools pillow uharfbuzz")

BASE = pathlib.Path(__file__).resolve().parent.parent
FONT_PATH = BASE / "assets/fonts/Bluekendy.ttf"           # .gitignore — 로컬에만 둡니다
INDEX = BASE / "index.html"

LINES = ["Our", "Wedding Day"]        # 줄 단위. 두 줄을 각각 SVG 하나로 만듭니다

# 낱말 사이(스페이스) 폭을 폰트 기본의 몇 배로 둘지. Bluekendy 의 스페이스는 199 로
# 본문용이라, 두 낱말짜리 표지에는 넓어 "Wedding  Day" 처럼 벌어집니다.
# 줄 전체는 폭 100% 로 맞춰 그리므로, 좁힌 만큼 글자가 그만큼 커집니다.
SPACE_SCALE = 0.65

# ── 손으로 고치는 표 ────────────────────────────────────────────
# 번호는 각 단계 직전의 획 순서(0부터).
REVERSE = {
    "D": {1},           # 세로 작대기를 위에서 아래로
    "d": {0},           # o 부분 위에서 시작해 돌고, 오른쪽 획을 올라갔다 내려오게
    "e": {0},           # 가운데 왼쪽에서 시작해 고리를 돌고 오른쪽으로 빠지게
                        # (뒤집기 전에는 나가는 획에서 시작해 가운데에서 멈췄습니다)
}
SPLIT = {
    "d": {0: [11]},     # 한 붓 궤적을 11번째 점에서 — 세로획 왕복 / o 부분
}
ORDER = {
    "D": [1, 0, 2],     # 세로 작대기 → 곡선 → 나머지
    "d": [1, 0, 2],     # o → 세로획 → 나머지
}

# ── 손대는 일이 드문 값들 ───────────────────────────────────────
RASTER_SIZE = 260     # 글자를 구울 크기. 클수록 궤적이 정밀하지만 느립니다
RASTER_PAD = 24
VPAD = 40             # viewBox 여백 (획이 잘리지 않게)
PEN_W = 24            # 교차점의 미래 획을 미리 열지 않는 기본 마스크 폭
WRITE_SEC = 2.70      # 너무 서두르지 않도록 일정한 펜 속도로 씁니다
START_SEC = 0.30
GAP_SEC = 0.0         # 글자 사이 쉼. 필기체는 붙어 흐르므로 0
SIMPLIFY_TOL = 1.4
# 솎아낸 점 사이를 곡선으로 이어 이 간격(폰트 단위)으로 다시 뜁니다. 0 이면 끕니다.
# 왜 필요한가: 점 사이는 직선이라, 느리게 보면 O 같은 곡선이 다각형처럼 꺾여 그려집니다.
# 래스터 계단을 다시 끌어오지 않으려면 점을 새로 찍지 말고 곡선으로 보간해야 합니다.
CURVE_STEP = 16

N8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

font = TTFont(FONT_PATH)
gs = font.getGlyphSet()
cmap = font.getBestCmap()
UPEM = font["head"].unitsPerEm
pil = ImageFont.truetype(str(FONT_PATH), RASTER_SIZE)
ASCENT = pil.getmetrics()[0]
SCALE = UPEM / RASTER_SIZE


# ── 1. 글자를 이미지로 굽기 ─────────────────────────────────────
def raster(ch):
    box = pil.getbbox(ch)
    w = box[2] - box[0] + RASTER_PAD * 2
    h = box[3] - box[1] + RASTER_PAD * 2
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((RASTER_PAD - box[0], RASTER_PAD - box[1]), ch, font=pil, fill=255)
    px = im.load()
    return [[px[x, y] > 110 for x in range(w)] for y in range(h)], w, h


# ── 2. 세선화 (Zhang-Suen) ─────────────────────────────────────
def _nb(g, x, y):
    return [g[y - 1][x], g[y - 1][x + 1], g[y][x + 1], g[y + 1][x + 1],
            g[y + 1][x], g[y + 1][x - 1], g[y][x - 1], g[y - 1][x - 1]]


def _transitions(n):
    s = n + n[:1]
    return sum(1 for i in range(8) if not s[i] and s[i + 1])


def thin(grid, w, h):
    g = [r[:] for r in grid]
    changed, rounds = True, 0
    while changed and rounds < 60:
        changed = False
        for step in (0, 1):
            drop = []
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if not g[y][x]:
                        continue
                    n = _nb(g, x, y)
                    if not (2 <= sum(n) <= 6) or _transitions(n) != 1:
                        continue
                    p2, p3, p4, p5, p6, p7, p8, p9 = n
                    if step == 0 and ((p2 and p4 and p6) or (p4 and p6 and p8)):
                        continue
                    if step == 1 and ((p2 and p4 and p8) or (p2 and p6 and p8)):
                        continue
                    drop.append((x, y))
            if drop:
                changed = True
                for x, y in drop:
                    g[y][x] = False
        rounds += 1
    return g


# ── 3. 뼈대를 순서 있는 궤적으로 ────────────────────────────────
def _deg(pts, p):
    x, y = p
    return sum(1 for dx, dy in N8 if (x + dx, y + dy) in pts)


def _farthest(pts, start):
    seen, frontier, d = {start}, [start], 0
    while frontier:
        nxt = []
        for x, y in frontier:
            for dx, dy in N8:
                q = (x + dx, y + dy)
                if q in pts and q not in seen:
                    seen.add(q); nxt.append(q)
        if nxt:
            d += 1
        frontier = nxt
    return d


def trace(pts):
    """끝점에서 출발해 한 붓 그리기처럼 잇습니다. 시작은 왼쪽 우선(필기 방향)."""
    pts, strokes = set(pts), []
    while pts:
        ends = [p for p in pts if _deg(pts, p) == 1]
        cur = min(ends or pts, key=lambda p: (p[0], p[1]))
        line = [cur]
        pts.discard(cur)
        while True:
            x, y = cur
            cand = [(x + dx, y + dy) for dx, dy in N8 if (x + dx, y + dy) in pts]
            if not cand:
                break
            cur = max(cand, key=lambda q: _farthest(pts, q)) if len(cand) > 1 else cand[0]
            line.append(cur)
            pts.discard(cur)
        if len(line) > 8:                 # 부스러기는 버립니다
            strokes.append(line)
    strokes.sort(key=len, reverse=True)   # 긴 획부터
    return strokes


def simplify(line, tol=SIMPLIFY_TOL):
    """Douglas–Peucker — 점을 줄여 path 를 가볍게"""
    if len(line) < 3:
        return line

    def dist(p, a, b):
        (px, py), (ax, ay), (bx, by) = p, a, b
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** .5
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** .5

    worst, idx = 0, 0
    for i in range(1, len(line) - 1):
        d = dist(line[i], line[0], line[-1])
        if d > worst:
            worst, idx = d, i
    if worst <= tol:
        return [line[0], line[-1]]
    return simplify(line[:idx + 1], tol)[:-1] + simplify(line[idx:], tol)


def densify(pts, step=CURVE_STEP):
    """솎아낸 점들을 Catmull-Rom 으로 이어 step 간격으로 다시 뜁니다.

    새 점은 원래 점들을 지나는 곡선 위에서 나오므로, 모양은 그대로 두고
    마디만 잘게 나눕니다(세선화의 계단이 되살아나지 않습니다)."""
    if step <= 0 or len(pts) < 3:
        return pts
    P = [pts[0]] + list(pts) + [pts[-1]]       # 양 끝을 복제해 접선을 잡습니다
    out = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = P[i], P[i+1], P[i+2], P[i+3]
        d = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** .5
        n = max(1, round(d / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append((
                .5 * (2*x1 + (-x0 + x2)*t + (2*x0 - 5*x1 + 4*x2 - x3)*t2 + (-x0 + 3*x1 - 3*x2 + x3)*t3),
                .5 * (2*y1 + (-y0 + y2)*t + (2*y0 - 5*y1 + 4*y2 - y3)*t2 + (-y0 + 3*y1 - 3*y2 + y3)*t3),
            ))
    out.append(pts[-1])
    return out


_pen_cache = {}


def manual_o():
    """O의 중심선.

    자동 세선화 결과는 안쪽 진입선과 고리가 만나는 왼쪽 아래에서 진행 방향이
    갑자기 뒤집혀 매듭처럼 보입니다. 원본 글리프는 그대로 두고, 그 위를 여는
    마스크만 진입선 → 고리 → 나가는 꼬리 순서의 매끄러운 한 줄로 만듭니다.
    """
    start = (73, 288)
    curves = [
        ((68, 255), (55, 200), (44, 169)),
        # 여기서 되돌아 올라가지 않고 그대로 아래쪽 고리로 이어집니다.
        ((39, 128), (43, 75), (65, 55)),
        ((96, 20), (145, 14), (195, 40)),
        ((251, 70), (300, 132), (331, 197)),
        ((369, 276), (389, 354), (365, 405)),
        ((342, 454), (292, 480), (234, 482)),
        ((184, 484), (126, 460), (81, 425)),
        ((35, 390), (12, 337), (10, 278)),
        ((8, 236), (18, 199), (25, 175)),
        ((27, 160), (36, 145), (38, 135)),
        # 꼬리도 위로 꺾지 않고 화면 아래 방향으로 빠집니다.
        ((40, 125), (47, 117), (58, 113)),
        ((92, 98), (137, 87), (190, 84)),
    ]
    d = f"M{start[0]} {start[1]}" + "".join(
        f"C{a[0]} {a[1]} {b[0]} {b[1]} {c[0]} {c[1]}" for a, b, c in curves
    )
    body_curves, tail_curves = curves[:10], curves[10:]
    body_d = f"M{start[0]} {start[1]}" + "".join(
        f"C{a[0]} {a[1]} {b[0]} {b[1]} {c[0]} {c[1]}" for a, b, c in body_curves
    )
    tail_start = body_curves[-1][2]
    tail_d = f"M{tail_start[0]} {tail_start[1]}" + "".join(
        f"C{a[0]} {a[1]} {b[0]} {b[1]} {c[0]} {c[1]}" for a, b, c in tail_curves
    )
    pts, p0 = [start], start
    for p1, p2, p3 in curves:
        for k in range(1, 17):
            t = k / 16
            u = 1 - t
            pts.append((
                u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1],
            ))
        p0 = p3
    return pts, d, body_d, tail_d


MANUAL_O_POINTS, MANUAL_O_D, MANUAL_O_BODY_D, MANUAL_O_TAIL_D = manual_o()
# 교차점 가까이에 있는 나가는 꼬리가 고리를 그릴 때 미리 드러나지 않게 덮는 선입니다.
# 실제 글자에는 포함되지 않고 SVG mask 안에서만 검게 칠해지는 임시 가림막입니다.
MANUAL_O_GUARD_D = "M46 151C67 140 99 111 130 94C151 86 174 84 195 84"
MANUAL_O_BRIDGE_D = "M37 185C34 165 35 145 39 124"
MANUAL_O_CROSS_POINT = 1 * 16
MANUAL_O_TAIL_POINT = 10 * 16


def manual_curve(start, curves):
    """수동 cubic Bézier를 길이 계산용 점들과 SVG path로 함께 만듭니다."""
    d = f"M{start[0]} {start[1]}" + "".join(
        f"C{a[0]} {a[1]} {b[0]} {b[1]} {c[0]} {c[1]}" for a, b, c in curves
    )
    pts, p0 = [start], start
    for p1, p2, p3 in curves:
        for k in range(1, 17):
            t, u = k / 16, 1 - k / 16
            pts.append((
                u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1],
            ))
        p0 = p3
    return pts, d


# u의 마지막 (277,188)과 r의 시작 (0,188)은 조판 위치를 더하면 둘 다 (668,188).
# 따라서 글자 경계에서도 펜이 뜨거나 되돌아가지 않고 그대로 이어집니다.
MANUAL_U_POINTS, MANUAL_U_D = manual_curve((8, 180), [
    ((24, 197), (46, 224), (64, 245)),
    ((54, 218), (38, 180), (25, 140)),
    ((16, 108), (15, 83), (22, 76)),
    ((34, 66), (54, 85), (76, 112)),
    ((101, 142), (124, 181), (145, 215)),
    ((153, 228), (158, 239), (163, 243)),
    ((168, 246), (169, 238), (166, 226)),
    ((157, 196), (145, 155), (136, 116)),
    ((129, 87), (127, 72), (133, 74)),
    ((144, 61), (168, 87), (191, 109)),
    ((220, 137), (249, 165), (277, 188)),
])
MANUAL_R_POINTS, MANUAL_R_D = manual_curve((0, 188), [
    ((17, 204), (35, 224), (46, 231)),
    ((47, 237), (48, 243), (48, 246)),
    ((61, 248), (76, 246), (88, 242)),
    ((105, 238), (117, 231), (123, 227)),
    ((122, 212), (115, 198), (105, 185)),
    ((92, 168), (78, 151), (69, 138)),
    ((61, 125), (58, 109), (58, 96)),
    ((58, 83), (65, 77), (76, 76)),
    ((96, 76), (113, 86), (134, 100)),
    ((160, 118), (184, 139), (208, 158)),
])
MANUAL_I_BODY_POINTS, MANUAL_I_BODY_D = manual_curve((0, 188), [
    ((8, 205), (18, 218), (26, 220)),
    ((24, 212), (20, 204), (17, 199)),
    ((10, 180), (0, 155), (-12, 125)),
    ((-18, 108), (-14, 99), (-5, 100)),
    ((10, 103), (28, 119), (45, 132)),
    ((65, 147), (84, 161), (107, 188)),
])
MANUAL_I_DOT_POINTS, MANUAL_I_DOT_D = manual_curve((50, 276), [
    ((48, 267), (42, 252), (36, 243)),
])
MANUAL_N_POINTS, MANUAL_N_D = manual_curve((0, 188), [
    ((20, 208), (40, 228), (57, 230)),
    ((72, 230), (76, 210), (68, 185)),
    ((62, 165), (56, 145), (54, 130)),
    ((70, 150), (95, 190), (120, 220)),
    ((135, 238), (150, 250), (160, 245)),
    ((170, 238), (160, 215), (150, 190)),
    ((138, 162), (122, 125), (121, 105)),
    ((121, 92), (135, 96), (150, 104)),
    ((180, 120), (212, 150), (245, 184)),
])
_G_CURVES = [
    ((18, 204), (38, 220), (55, 220)),
    ((75, 221), (88, 205), (84, 178)),
    ((82, 162), (72, 143), (60, 128)),
    ((45, 108), (27, 92), (10, 92)),
    ((-10, 92), (-22, 105), (-23, 125)),
    ((-24, 150), (-10, 185), (11, 204)),
    ((30, 220), (52, 224), (69, 207)),
    ((82, 194), (88, 173), (89, 159)),
    ((96, 140), (92, 120), (85, 96)),
    ((75, 60), (60, 20), (45, -15)),
    ((25, -60), (8, -100), (-12, -120)),
    ((-24, -130), (-31, -110), (-30, -80)),
    ((-28, -40), (-10, 0), (15, 35)),
    ((40, 70), (65, 90), (85, 96)),
    ((108, 120), (145, 155), (192, 185)),
]
MANUAL_G_POINTS, MANUAL_G_D = manual_curve((0, 184), _G_CURVES)
_, MANUAL_G_BODY_D = manual_curve((0, 184), _G_CURVES[:14])
_, MANUAL_G_TAIL_D = manual_curve((85, 96), _G_CURVES[14:])
MANUAL_G_PHASE_POINT = 14 * 16
MANUAL_A_POINTS, MANUAL_A_D = manual_curve((-44, 100), [
    ((-40, 75), (-22, 62), (0, 77)),
    ((20, 94), (38, 119), (50, 150)),
    ((60, 175), (62, 198), (51, 202)),
    ((38, 210), (17, 195), (1, 178)),
    ((-18, 158), (-37, 128), (-44, 100)),
    ((-42, 84), (-27, 67), (-8, 70)),
    ((15, 74), (35, 111), (50, 150)),
    ((62, 165), (75, 167), (83, 163)),
    ((86, 160), (80, 145), (69, 120)),
    ((58, 93), (53, 80), (58, 76)),
    ((63, 71), (79, 80), (95, 90)),
    ((130, 112), (165, 151), (198, 188)),
])
_Y_CURVES = [
    ((18, 205), (35, 220), (53, 219)),
    ((58, 210), (50, 185), (41, 160)),
    ((30, 130), (22, 100), (32, 92)),
    ((45, 83), (65, 101), (84, 119)),
    ((105, 138), (127, 160), (141, 173)),
    ((156, 187), (171, 202), (177, 205)),
    ((184, 207), (181, 190), (174, 172)),
    ((166, 150), (159, 130), (153, 102)),
    ((147, 75), (140, 35), (130, -1)),
    ((116, -45), (96, -88), (69, -115)),
    ((48, -135), (27, -130), (18, -112)),
    ((8, -90), (20, -57), (38, -32)),
    ((62, 2), (91, 32), (120, 60)),
    ((132, 72), (142, 82), (150, 91)),
    ((180, 115), (220, 150), (258, 181)),
]
MANUAL_Y_POINTS, MANUAL_Y_D = manual_curve((0, 188), _Y_CURVES)
_, MANUAL_Y_BODY_D = manual_curve((0, 188), _Y_CURVES[:14])
_, MANUAL_Y_TAIL_D = manual_curve((150, 91), _Y_CURVES[14:])
MANUAL_Y_PHASE_POINT = 14 * 16
MANUAL_PEN = {
    "u": (MANUAL_U_POINTS, MANUAL_U_D),
    "r": (MANUAL_R_POINTS, MANUAL_R_D),
    "n": (MANUAL_N_POINTS, MANUAL_N_D),
    "g": (MANUAL_G_POINTS, MANUAL_G_D),
    "a": (MANUAL_A_POINTS, MANUAL_A_D),
    "y": (MANUAL_Y_POINTS, MANUAL_Y_D),
}

_D_COMMON = [
    ((30, 216), (-5, 184), (-30, 145)),
    ((-48, 115), (-50, 80), (-31, 62)),
    ((-10, 52), (24, 82), (52, 118)),
    ((75, 147), (96, 173), (112, 212)),
    ((125, 235), (145, 259), (165, 300)),
    ((190, 350), (215, 397), (212, 416)),
    ((210, 428), (204, 420), (198, 405)),
    ((180, 370), (157, 322), (137, 263)),
    ((125, 230), (110, 190), (96, 145)),
    ((88, 115), (83, 80), (92, 62)),
    ((103, 48), (125, 62), (150, 80)),
    ((180, 102), (210, 138), (238, 173)),
    ((243, 178), (247, 184), (251, 188)),
]
# e→첫 d는 e의 끝점에, 첫 d→둘째 d는 두 글자의 조판 경계에 정확히 맞춥니다.
_D1_CURVES = [((-20, 160), (20, 205), (54, 231))] + _D_COMMON
_D2_CURVES = [((18, 200), (38, 220), (54, 231))] + _D_COMMON
MANUAL_D1_POINTS, MANUAL_D1_D = manual_curve((-54, 127), _D1_CURVES)
MANUAL_D2_POINTS, MANUAL_D2_D = manual_curve((0, 188), _D2_CURVES)
_, MANUAL_D1_BODY_D = manual_curve((-54, 127), _D1_CURVES[:5])
_, MANUAL_D2_BODY_D = manual_curve((0, 188), _D2_CURVES[:5])
_, MANUAL_D1_TAIL_D = manual_curve((112, 212), _D1_CURVES[5:])
_, MANUAL_D2_TAIL_D = manual_curve((112, 212), _D2_CURVES[5:])
MANUAL_D_PHASE_POINT = 5 * 16
MANUAL_D_VARIANTS = [
    (MANUAL_D1_POINTS, MANUAL_D1_D, MANUAL_D1_BODY_D, MANUAL_D1_TAIL_D),
    (MANUAL_D2_POINTS, MANUAL_D2_D, MANUAL_D2_BODY_D, MANUAL_D2_TAIL_D),
]

def pen_strokes(ch):
    """글자 하나의 궤적을 폰트 좌표(y 위로)로. REVERSE/SPLIT/ORDER 를 적용합니다."""
    if ch in _pen_cache:
        return _pen_cache[ch]
    if ch == "O":
        _pen_cache[ch] = [MANUAL_O_POINTS]
        return _pen_cache[ch]
    if ch == "i":
        _pen_cache[ch] = [MANUAL_I_BODY_POINTS, MANUAL_I_DOT_POINTS]
        return _pen_cache[ch]
    if ch in MANUAL_PEN:
        _pen_cache[ch] = [MANUAL_PEN[ch][0]]
        return _pen_cache[ch]
    grid, w, h = raster(ch)
    sk = thin(grid, w, h)
    box = pil.getbbox(ch)
    ox = RASTER_PAD - box[0]
    by = (RASTER_PAD - box[1]) + ASCENT
    pts = {(x, y) for y in range(h) for x in range(w) if sk[y][x]}
    out = [[((px - ox) * SCALE, (by - py) * SCALE) for px, py in simplify(s)]
           for s in trace(pts)]

    for i in REVERSE.get(ch, ()):
        if i < len(out):
            out[i] = out[i][::-1]
    if ch in SPLIT:
        cut = []
        for si, stroke in enumerate(out):
            at = SPLIT[ch].get(si)
            if not at:
                cut.append(stroke); continue
            prev = 0
            for c in at:
                cut.append(stroke[prev:c + 1]); prev = c
            cut.append(stroke[prev:])
        out = cut
    if ch in ORDER:
        out = [out[i] for i in ORDER[ch] if i < len(out)]
    # 위 표들의 점 번호는 솎아낸 상태를 가리키므로, 촘촘히 뜨는 것은 맨 마지막입니다
    out = [densify(st) for st in out]
    _pen_cache[ch] = out
    return out


# ── 4. 조판은 폰트에 맡깁니다 ──────────────────────────────────
_hb = None


def layout(text):
    """HarfBuzz 가 조판한 자리에 글리프를 놓습니다(커닝·liga·calt)."""
    global _hb
    if _hb is None:
        f = hb.Font(hb.Face(hb.Blob.from_file_path(str(FONT_PATH))))
        f.scale = (UPEM, UPEM)
        _hb = f
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(_hb, buf, {"kern": True, "liga": True, "calt": True})

    names = font.getGlyphOrder()
    items, x, d_seen = [], 0, 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = names[info.codepoint]
        p = SVGPathPen(gs)
        gs[name].draw(p)
        d = p.getCommands()
        ch = text[info.cluster] if info.cluster < len(text) else "?"
        if d:
            manual_pen = manual_parts = None
            pen = pen_strokes(ch)
            if ch == "d":
                manual_pen = MANUAL_D_VARIANTS[min(d_seen, len(MANUAL_D_VARIANTS) - 1)]
                pen = [manual_pen[0]]
                manual_parts = (manual_pen[2], manual_pen[3],
                                MANUAL_D_PHASE_POINT, 56, 18, 32)
                d_seen += 1
            elif ch == "D":
                # 폰트에서 뽑은 정확한 중심선을 사용합니다. 짧은 위 장식은 뒤집어
                # 세로획 시작점에 붙이고, 바깥 곡선은 원본 궤적 그대로 별도 필기합니다.
                stem, outer, flourish = pen
                top_stem = list(reversed(flourish)) + [(273, 464)] + stem
                pen = [top_stem, outer]
            elif ch == "g":
                manual_parts = (MANUAL_G_BODY_D, MANUAL_G_TAIL_D,
                                MANUAL_G_PHASE_POINT, PEN_W, PEN_W, 18)
            elif ch == "y":
                manual_parts = (MANUAL_Y_BODY_D, MANUAL_Y_TAIL_D,
                                MANUAL_Y_PHASE_POINT, PEN_W, PEN_W, 18)
            items.append({"ch": ch, "name": name, "d": d,
                          "x": x + pos.x_offset, "pen": pen,
                          "manual_pen": manual_pen[1] if manual_pen else None,
                          "manual_parts": manual_parts})
        # 스페이스는 그릴 것이 없어 items 에 들어가지 않지만, 폭만큼은 밀어야 합니다
        x += round(pos.x_advance * SPACE_SCALE) if ch == " " else pos.x_advance
    return items


def seg_len(pts):
    return sum(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** .5
               for i in range(len(pts) - 1))


# ── 5. SVG 조립 ───────────────────────────────────────────────
def make(text, cls, clock):
    items = layout(text)
    xmin = ymin = 10 ** 9
    xmax = ymax = -(10 ** 9)
    for it in items:
        bp = BoundsPen(gs)
        gs[it["name"]].draw(bp)
        if not bp.bounds:
            continue
        x0, y0, x1, y1 = bp.bounds
        xmin = min(xmin, it["x"] + x0); xmax = max(xmax, it["x"] + x1)
        ymin = min(ymin, y0);           ymax = max(ymax, y1)

    vx, vy = xmin - VPAD, ymin - VPAD
    vw, vh = (xmax - xmin) + VPAD * 2, (ymax - ymin) + VPAD * 2

    masks, glyphs, pending_i = [], [], None
    for n, it in enumerate(items):
        # edding 본체를 모두 이어 쓴 뒤, Day로 넘어가기 직전에 i의 점을 찍습니다.
        if pending_i and it["ch"] == "D":
            i_it, dot = pending_i
            dot_l, dot_id = seg_len(dot), f"pen{clock[2]}"
            dot_dur = dot_l / clock[1]
            clock[2] += 1
            masks.append(
                f'<mask id="{dot_id}" maskUnits="userSpaceOnUse" '
                f'x="-200" y="-500" width="1600" height="1800"><g class="pen">'
                f'<path d="{MANUAL_I_DOT_D}" style="--l:{dot_l:.0f};--d:{dot_dur:.3f}s;'
                f'--t:{clock[0]:.3f}s"/></g></mask>')
            glyphs.append(f'<path mask="url(#{dot_id})" transform="translate({i_it["x"]},0)" '
                          f'd="{i_it["d"]}"/>')
            clock[0] += dot_dur + GAP_SEC
            glyphs.append(f'<path class="done" style="--t:{clock[0]:.3f}s" '
                          f'transform="translate({i_it["x"]},0)" d="{i_it["d"]}"/>')
            pending_i = None
        if it["ch"] == "O":
            st = it["pen"][0]
            body = st[:MANUAL_O_TAIL_POINT + 1]
            tail = st[MANUAL_O_TAIL_POINT:]
            body_l, tail_l = seg_len(body), seg_len(tail)
            body_dur, tail_dur = body_l / clock[1], tail_l / clock[1]
            cross_t = clock[0] + seg_len(st[:MANUAL_O_CROSS_POINT + 1]) / clock[1]
            tail_t = clock[0] + body_dur
            body_id, tail_id = f"pen{clock[2]}", f"pen{clock[2] + 1}"
            clock[2] += 2
            masks.append(
                f'<mask id="{body_id}" maskUnits="userSpaceOnUse" '
                f'x="-200" y="-500" width="1600" height="1800"><g class="pen">'
                f'<path d="{MANUAL_O_BODY_D}" style="--l:{body_l:.0f};--d:{body_dur:.3f}s;'
                f'--t:{clock[0]:.3f}s;stroke-width:56"/>'
                f'<path class="guard" d="{MANUAL_O_GUARD_D}"/>'
                f'<path class="bridge" d="{MANUAL_O_BRIDGE_D}" style="--t:{cross_t:.3f}s"/>'
                f'</g></mask>')
            masks.append(
                f'<mask id="{tail_id}" maskUnits="userSpaceOnUse" '
                f'x="-200" y="-500" width="1600" height="1800"><g class="pen">'
                f'<path d="{MANUAL_O_TAIL_D}" style="--l:{tail_l:.0f};--d:{tail_dur:.3f}s;'
                f'--t:{tail_t:.3f}s;stroke-width:56"/></g></mask>')
            glyphs.append(f'<path mask="url(#{body_id})" transform="translate({it["x"]},0)" '
                          f'd="{it["d"]}"/>')
            glyphs.append(f'<path mask="url(#{tail_id})" transform="translate({it["x"]},0)" '
                          f'd="{it["d"]}"/>')
            clock[0] += body_dur + tail_dur + GAP_SEC
            glyphs.append(f'<path class="done" style="--t:{clock[0]:.3f}s" '
                          f'transform="translate({it["x"]},0)" d="{it["d"]}"/>')
            continue
        if it["ch"] == "i":
            body, dot = it["pen"]
            body_l, body_id = seg_len(body), f"pen{clock[2]}"
            body_dur = body_l / clock[1]
            clock[2] += 1
            # 본체를 쓰는 동안 점은 숨깁니다. 점 마스크는 edding의 g까지 다 쓴 뒤
            # 생성해, i에서 n으로 넘어가는 한 획을 끊지 않습니다.
            masks.append(
                f'<mask id="{body_id}" maskUnits="userSpaceOnUse" '
                f'x="-200" y="-500" width="1600" height="1800"><g class="pen">'
                f'<path d="{MANUAL_I_BODY_D}" style="--l:{body_l:.0f};--d:{body_dur:.3f}s;'
                f'--t:{clock[0]:.3f}s"/>'
                f'<path class="guard" d="{MANUAL_I_DOT_D}" style="stroke-width:24"/>'
                f'</g></mask>')
            glyphs.append(f'<path mask="url(#{body_id})" transform="translate({it["x"]},0)" '
                          f'd="{it["d"]}"/>')
            clock[0] += body_dur + GAP_SEC
            pending_i = (it, dot)
            continue
        if it.get("manual_parts"):
            st = it["pen"][0]
            body_d, tail_d, phase_point, body_w, tail_w, guard_w = it["manual_parts"]
            body = st[:phase_point + 1]
            tail = st[phase_point:]
            body_l, tail_l = seg_len(body), seg_len(tail)
            body_dur, tail_dur = body_l / clock[1], tail_l / clock[1]
            tail_t = clock[0] + body_dur
            body_id, tail_id = f"pen{clock[2]}", f"pen{clock[2] + 1}"
            clock[2] += 2
            # 몸통 마스크에서는 뒤에 그릴 긴 세로획을 계속 가립니다. 별도의 꼬리
            # 마스크가 같은 점·같은 시각에서 시작하므로 화면에서는 한 획입니다.
            masks.append(
                f'<mask id="{body_id}" maskUnits="userSpaceOnUse" '
                f'x="-200" y="-500" width="1600" height="1800"><g class="pen">'
                f'<path d="{body_d}" style="--l:{body_l:.0f};--d:{body_dur:.3f}s;'
                f'--t:{clock[0]:.3f}s;stroke-width:{body_w}"/>'
                f'<path class="guard" d="{tail_d}" style="stroke-width:{guard_w}"/>'
                # 검은 가림막이 이미 지나간 몸통까지 투명하게 뚫지 않도록, 같은
                # 애니메이션의 좁은 중심선을 맨 위에서 다시 엽니다. 미래 획은 여전히
                # 가려지고 현재 획이 지난 교차점만 즉시 채워집니다.
                f'<path class="restore" d="{body_d}" style="--l:{body_l:.0f};'
                f'--d:{body_dur:.3f}s;--t:{clock[0]:.3f}s;stroke-width:18"/>'
                f'</g></mask>')
            masks.append(
                f'<mask id="{tail_id}" maskUnits="userSpaceOnUse" '
                f'x="-200" y="-500" width="1600" height="1800"><g class="pen">'
                f'<path d="{tail_d}" style="--l:{tail_l:.0f};--d:{tail_dur:.3f}s;'
                f'--t:{tail_t:.3f}s;stroke-width:{tail_w}"/></g></mask>')
            glyphs.append(f'<path mask="url(#{body_id})" transform="translate({it["x"]},0)" '
                          f'd="{it["d"]}"/>')
            glyphs.append(f'<path mask="url(#{tail_id})" transform="translate({it["x"]},0)" '
                          f'd="{it["d"]}"/>')
            clock[0] += body_dur + tail_dur + GAP_SEC
            glyphs.append(f'<path class="done" style="--t:{clock[0]:.3f}s" '
                          f'transform="translate({it["x"]},0)" d="{it["d"]}"/>')
            continue
        segs = []
        for si, st in enumerate(it["pen"]):
            if len(st) < 2:
                continue
            L = seg_len(st)
            dur = L / clock[1]
            style = f'--l:{L:.0f};--d:{dur:.3f}s;--t:{clock[0]:.3f}s'
            if it.get("manual_pen"):
                segs.append(f'<path d="{it["manual_pen"]}" style="{style};stroke-width:56"/>')
            elif it["ch"] in MANUAL_PEN:
                segs.append(f'<path d="{MANUAL_PEN[it["ch"]][1]}" style="{style}"/>')
            else:
                # 마스크는 글자 path 의 좌표계로 해석됩니다 — x 를 또 더하면 두 번 밀립니다
                pts = " ".join(f"{px:.0f},{py:.0f}" for px, py in st)
                segs.append(f'<polyline points="{pts}" style="{style}"/>')
            clock[0] += dur
        clock[0] += GAP_SEC
        if not segs:                      # 궤적을 못 뽑으면 그냥 보이게
            glyphs.append(f'<path transform="translate({it["x"]},0)" d="{it["d"]}"/>')
            continue
        mid = f"pen{clock[2]}"
        clock[2] += 1
        masks.append(f'<mask id="{mid}" maskUnits="userSpaceOnUse" '
                     f'x="-200" y="-500" width="1600" height="1800">'
                     f'<g class="pen">{"".join(segs)}</g></mask>')
        glyphs.append(f'<path mask="url(#{mid})" transform="translate({it["x"]},0)" d="{it["d"]}"/>')
        # 마스크는 중심선이라 뾰족한 획 끝을 덮지 못합니다. 필기체에서 다음 글자로
        # 넘어가는 연결선이 그 끝이라, 다 쓰고 나면 원본을 덧대 이음새를 메웁니다.
        glyphs.append(f'<path class="done" style="--t:{clock[0]:.3f}s" '
                      f'transform="translate({it["x"]},0)" d="{it["d"]}"/>')

    inner = (f'<defs>{"".join(masks)}</defs>'
             f'<g transform="translate(0,{ymax + VPAD:.0f}) scale(1,-1)">{"".join(glyphs)}</g>')
    return (f'<svg class="{cls}" viewBox="{vx:.0f} {vy:.0f} {vw:.0f} {vh:.0f}" '
            f'aria-hidden="true">{inner}</svg>'), vw / vh


def build():
    total = sum(seg_len(st) for t in LINES for it in layout(t)
                for st in it["pen"] if len(st) >= 2)
    speed = total / WRITE_SEC
    clock = [START_SEC, speed, 0]        # [시각, 속도, 마스크 번호]

    svgs, ratios = [], []
    for i, text in enumerate(LINES):
        svg, ratio = make(text, f"cs cs--{'our' if i == 0 else 'wed'}", clock)
        svgs.append(svg); ratios.append(ratio)

    block = ('    <p class="cover-script">\n'
             + "".join(f"      {s}\n" for s in svgs)
             + f'      <b>{" ".join(LINES)}</b>\n'
             + "    </p>")
    return block, clock[0], ratios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="파일을 고치지 않고 결과만 봅니다")
    args = ap.parse_args()

    block, end, ratios = build()
    print(f"쓰기 {START_SEC}s 부터 {end:.2f}s 까지  ({WRITE_SEC}초 동안)")
    print(f"두 줄 크기를 맞추는 폭 비율 — 첫 줄 {ratios[0] / ratios[1] * 100:.1f}%  "
          f"(style.css 의 .cs--our)")
    print(f"마크업 {len(block) / 1024:.1f}KB")

    if args.dry:
        return

    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r'    <p class="cover-script">.*?\n    </p>', html, re.S)
    if not m:
        sys.exit("index.html 에서 .cover-script 문단을 찾지 못했습니다")
    INDEX.write_text(html[:m.start()] + block + html[m.end():], encoding="utf-8")
    print(f"\n{INDEX.name} 를 고쳤습니다. 이어서 tools/stamp-assets.py 를 돌리세요.")


if __name__ == "__main__":
    main()
