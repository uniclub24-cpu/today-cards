"""To:Day 카드뉴스 렌더러 v3 — 실사형(풀블리드 사진 + 하단 그라데이션 + 큰 흰 글씨)
사용: python3 render3.py issue.json out_dir [이미지폴더]
- 각 슬라이드의 "img": 이미지 파일명 (이미지폴더 안). 없으면 '이미지 자리' 플레이스홀더를 그림
- {글자}: 하늘색 강조, !줄: 청색 띠 반전, \n 줄바꿈
"""
import json, sys, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

W, H, K = 1080, 1350, 2
NAVY, BLUE, SKY = "#0A2350", "#1E5BD8", "#8DB6FF"
FD = "/usr/share/fonts/opentype/noto/"
SERIF_K = FD + "NotoSerifCJK-Black.ttc"
SANS = {w: FD + f"NotoSansCJK-{w}.ttc" for w in ("Regular", "Medium", "Bold", "Black")}
M = 72
_fc = {}


def F(p, s):
    k = (p, s)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(p, int(s * K), index=1)
    return _fc[k]


def placeholder(prompt, seed):
    random.seed(seed)
    im = Image.new("RGB", (W * K, H * K), "#1a2230")
    d = ImageDraw.Draw(im)
    for i in range(H * K):  # 세로 그라데이션
        t = i / (H * K)
        c = (int(38 - 20 * t), int(48 - 22 * t), int(66 - 26 * t))
        d.line([(0, i), (W * K, i)], fill=c)
    for _ in range(14):  # 흐린 빛번짐(보케)
        x, y, r = random.randint(0, W * K), random.randint(0, int(H * K * .6)), random.randint(60, 220)
        d.ellipse([x - r, y - r, x + r, y + r], fill=random.choice(["#3a4f73", "#5a4630", "#2f5a6a", "#6a5a3a"]))
    im = im.filter(ImageFilter.GaussianBlur(60))
    d = ImageDraw.Draw(im)
    f = F(SANS["Bold"], 30); f2 = F(SANS["Regular"], 24)
    d.rounded_rectangle([M * K, 170 * K, (W - M) * K, 330 * K], 18 * K, outline="#8DB6FF", width=3 * K)
    d.text((W / 2 * K, 215 * K), "AI 이미지 자리", font=f, fill="#8DB6FF", anchor="mm")
    d.text((W / 2 * K, 270 * K), prompt[:46] + ("…" if len(prompt) > 46 else ""), font=f2, fill="#C9D6EE", anchor="mm")
    return im


def load_bg(s, imgdir, i):
    p = os.path.join(imgdir or "", s.get("img", "")) if s.get("img") else None
    if p and os.path.exists(p):
        im = ImageOps.fit(Image.open(p).convert("RGB"), (W * K, H * K), Image.LANCZOS, centering=(0.5, s.get("focus", 0.4)))
        return im
    return placeholder(s.get("prompt", ""), i)


def gradient(im, start=0.38, strength=0.92):
    g = Image.new("L", (1, H * K))
    for y in range(H * K):
        t = max(0, (y / (H * K) - start) / (1 - start))
        g.putpixel((0, y), int(255 * min(1, (t ** 1.3) * strength + (0.25 if y < 260 * K else 0) * (1 - y / (260 * K)))))
    g = g.resize((W * K, H * K))
    dark = Image.new("RGB", (W * K, H * K), "#05080F")
    return Image.composite(dark, im, g)


class C:
    def __init__(self, im):
        self.im = im; self.d = ImageDraw.Draw(im)

    def tw(self, s, f):
        return self.d.textlength(s, font=f) / K

    def rect(self, b, fill, r=0):
        b = [v * K for v in b]
        self.d.rounded_rectangle(b, r * K, fill=fill) if r else self.d.rectangle(b, fill=fill)

    def text(self, xy, s, f, fill, anchor="la", shadow=True):
        if shadow:
            self.d.text((xy[0] * K + 3, xy[1] * K + 4), s, font=f, fill="#00000088", anchor=anchor)
        self.d.text((xy[0] * K, xy[1] * K), s, font=f, fill=fill, anchor=anchor)

    def lines(self, s, f, maxw):
        out = []
        for para in s.split("\n"):
            band = para.startswith("!"); para = para[1:] if band else para
            cur = ""
            for w in para.split(" "):
                t = (cur + " " + w).strip()
                if self.tw(t.replace("{", "").replace("}", ""), f) > maxw and cur:
                    out.append((band, cur)); cur = w
                else:
                    cur = t
            out.append((band, cur))
        return out

    def height(self, s, f, lh, maxw=W - 2 * M):
        return len(self.lines(s, f, maxw)) * f.size / K * lh

    def rich(self, x, y, s, f, fill="white", lh=1.32, maxw=W - 2 * M, hi=SKY):
        size = f.size / K; on = False
        L = self.lines(s, f, maxw)
        for i, (band, ln) in enumerate(L):
            ly = y + i * size * lh
            plain = ln.replace("{", "").replace("}", "")
            if band:
                self.rect([x - size * .14, ly + size * .1, x + self.tw(plain, f) + size * .2, ly + size * 1.25], BLUE)
            cx, buf = x, ""
            for ch in ln + "\0":
                if ch in "{}\0":
                    if buf:
                        self.text((cx, ly), buf, f, "white" if band else (hi if on else fill), shadow=not band)
                        cx += self.tw(buf, f); buf = ""
                    if ch in "{}":
                        on = ch == "{"
                else:
                    buf += ch
        return y + len(L) * size * lh


def chrome(c, meta, n, total, s):
    f = F(SERIF_K, 40)
    x = M
    for part, col in (("To", "white"), (":", SKY), ("Day", "white")):
        c.text((x, 64), part, f, col); x += c.tw(part, f) + 2
    tag = s.get("tag", meta["tag"])
    ft = F(SANS["Bold"], 22)
    w = c.tw(tag, ft) + 32
    c.rect([W - M - w, 70, W - M, 112], "#1B2A48", r=21)
    c.text((W - M - w / 2, 91), tag, ft, "white", anchor="mm", shadow=False)
    # 하단: AI 이미지 표기 + 출처 + 페이지
    fs = F(SANS["Regular"], 20)
    note = "AI 생성 이미지(연출)" + ("  ·  " + s.get("source", meta.get("source", "")) if s.get("source", meta.get("source")) else "")
    c.text((M, H - 62), note, fs, "#AEB8C8", shadow=False)
    c.text((W - M, H - 62), f"{n} / {total}", F(SANS["Bold"], 22), "white", anchor="ra", shadow=False)


def slide(s, meta, n, total, imgdir):
    im = gradient(load_bg(s, imgdir, n), start=s.get("grad", 0.34))
    c = C(im)
    chrome(c, meta, n, total, s)
    typ = s.get("type", "story")
    bottom = H - 120
    if typ == "cover":
        fh = F(SERIF_K, s.get("size", 96)); fk = F(SANS["Black"], 30); fs = F(SANS["Medium"], 36)
        h = c.height(s["headline"], fh, 1.26) + (c.height(s["sub"], fs, 1.5) + 34 if s.get("sub") else 0)
        y = bottom - h - 20
        c.rect([M, y - 78, M + c.tw(s["kicker"], fk) + 36, y - 26], BLUE)
        c.text((M + 18, y - 52), s["kicker"], fk, "white", anchor="lm", shadow=False)
        y = c.rich(M, y, s["headline"], fh, lh=1.26)
        if s.get("sub"):
            c.rich(M, y + 34, s["sub"], fs, fill="#D5DDEA", lh=1.5)
    elif typ == "quote":
        fq = F(SERIF_K, 64); fb = F(SANS["Medium"], 36)
        h = c.height(s["quote"], fq, 1.35) + (c.height(s["body"], fb, 1.6) + 50 if s.get("body") else 0)
        y = bottom - h
        c.text((M - 6, y - 150), "“", F(SERIF_K, 200), SKY, shadow=False)
        y = c.rich(M, y, s["quote"], fq, lh=1.35)
        if s.get("body"):
            c.rect([M, y + 22, M + 50, y + 27], SKY)
            c.rich(M, y + 50, s["body"], fb, fill="#D5DDEA", lh=1.6)
    elif typ == "info":
        ft = F(SERIF_K, 62); fh = F(SANS["Bold"], 36); fd = F(SANS["Regular"], 30)
        items = s["items"]
        h = c.height(s["title"], ft, 1.3) + 50 + sum(c.height(i["head"], fh, 1.4, W - 2 * M - 90) + (c.height(i.get("desc", ""), fd, 1.5, W - 2 * M - 90) if i.get("desc") else 0) + 40 for i in items)
        y = bottom - h
        y = c.rich(M, y, s["title"], ft, lh=1.3) + 50
        for k, it in enumerate(items, 1):
            c.text((M, y - 4), f"{k:02d}", F(SERIF_K, 44), SKY)
            y = c.rich(M + 90, y, it["head"], fh, lh=1.4, maxw=W - 2 * M - 90)
            if it.get("desc"):
                y = c.rich(M + 90, y, it["desc"], fd, fill="#C9D3E2", lh=1.5, maxw=W - 2 * M - 90)
            y += 40
    elif typ == "ask":
        ft = F(SERIF_K, 76); fo = F(SANS["Bold"], 36)
        y = bottom - c.height(s["title"], ft, 1.3) - 2 * 120 - 90
        y = c.rich(M, y, s["title"], ft, lh=1.3) + 40
        for k, o in enumerate(s["options"]):
            c.rect([M, y, W - M, y + 100], "#14213D", r=16)
            c.text((M + 34, y + 50), "AB"[k], F(SERIF_K, 48), SKY, anchor="lm")
            c.text((M + 100, y + 50), o, fo, "white", anchor="lm")
            y += 120
        c.text((M, y + 14), s.get("cta", "댓글로 A / B 남겨주세요  ·  팔로우하면 매일 받아봐요"), F(SANS["Bold"], 28), SKY)
    else:  # story
        fk = F(SANS["Black"], 30); ft = F(SERIF_K, s.get("size", 74)); fb = F(SANS["Medium"], 38)
        h = c.height(s["title"], ft, 1.3) + (c.height(s["body"], fb, 1.6) + 40 if s.get("body") else 0)
        y = bottom - h
        if s.get("kicker"):
            c.text((M, y - 60), s["kicker"], fk, SKY)
        y = c.rich(M, y, s["title"], ft, lh=1.3)
        if s.get("body"):
            c.rich(M, y + 40, s["body"], fb, fill="#D5DDEA", lh=1.6)
    return im.resize((W, H), Image.LANCZOS)


if __name__ == "__main__":
    issue = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]; imgdir = sys.argv[3] if len(sys.argv) > 3 else None
    os.makedirs(out, exist_ok=True)
    S = issue["slides"]
    for i, s in enumerate(S, 1):
        p = os.path.join(out, f"{i:02d}.png")
        slide(s, issue["meta"], i, len(S), imgdir).save(p, optimize=True)
        print(p)
