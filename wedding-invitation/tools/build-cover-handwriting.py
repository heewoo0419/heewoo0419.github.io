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
PEN_W = 46            # 마스크 선 두께. 글자 획(약 15)보다 넉넉해야 다 덮습니다
WRITE_SEC = 1.45      # 쓰는 시간. 앞 지연 0.3초는 START_SEC
START_SEC = 0.30
GAP_SEC = 0.0         # 글자 사이 쉼. 필기체는 붙어 흐르므로 0
SIMPLIFY_TOL = 1.4

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


_pen_cache = {}


def pen_strokes(ch):
    """글자 하나의 궤적을 폰트 좌표(y 위로)로. REVERSE/SPLIT/ORDER 를 적용합니다."""
    if ch in _pen_cache:
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
    items, x = [], 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = names[info.codepoint]
        p = SVGPathPen(gs)
        gs[name].draw(p)
        d = p.getCommands()
        ch = text[info.cluster] if info.cluster < len(text) else "?"
        if d:
            items.append({"ch": ch, "name": name, "d": d,
                          "x": x + pos.x_offset, "pen": pen_strokes(ch)})
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

    masks, glyphs = [], []
    for n, it in enumerate(items):
        segs = []
        for st in it["pen"]:
            if len(st) < 2:
                continue
            # 마스크는 글자 path 의 좌표계로 해석됩니다 — x 를 또 더하면 두 번 밀립니다
            pts = " ".join(f"{px:.0f},{py:.0f}" for px, py in st)
            L = seg_len(st)
            dur = L / clock[1]
            segs.append(f'<polyline points="{pts}" style="--l:{L:.0f};'
                        f'--d:{dur:.3f}s;--t:{clock[0]:.3f}s"/>')
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
