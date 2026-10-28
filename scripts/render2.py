"""To:Day 카드뉴스 렌더러 v2 — 에디토리얼(신문 매거진) 스타일
사용: python3 render2.py issue.json out_dir
원고 문법
  {글자}   : 형광펜 강조 (연청색 마커 + 진한 글씨)
  !줄      : 줄 전체를 청색 띠 위 흰 글씨로 (표지 반전 문구용)
  \n       : 줄바꿈
"""
import json, sys, os
from PIL import Image, ImageDraw, ImageFont

W, H, K = 1080, 1350, 2
NAVY, BLUE, MARK = "#0A2350", "#1E5BD8", "#CFE0FF"
INK, GRAY, LIGHT, LINE, PAPER = "#111418", "#6A7180", "#9AA1AD", "#E3E7ED", "#FFFFFF"
FD = "/usr/share/fonts/opentype/noto/"
SERIF_K = FD + "NotoSerifCJK-Black.ttc"
SERIF_B = FD + "NotoSerifCJK-Bold.ttc"
SANS = {w: FD + f"NotoSansCJK-{w}.ttc" for w in ("Regular", "Medium", "Bold", "Black")}
_fc = {}
M = 80  # 좌우 여백


def F(path, size):
    k = (path, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, int(size * K), index=1)
    return _fc[k]


class Card:
    def __init__(self, bg=PAPER):
        self.im = Image.new("RGB", (W * K, H * K), bg)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, b, fill, r=0):
        b = [v * K for v in b]
        self.d.rounded_rectangle(b, r * K, fill=fill) if r else self.d.rectangle(b, fill=fill)

    def circ(self, x, y, r, fill):
        self.d.ellipse([(x - r) * K, (y - r) * K, (x + r) * K, (y + r) * K], fill=fill)

    def tw(self, s, f):
        return self.d.textlength(s, font=f) / K

    def text(self, xy, s, f, fill, anchor="la"):
        self.d.text((xy[0] * K, xy[1] * K), s, font=f, fill=fill, anchor=anchor)

    def wrap(self, s, f, maxw):
        out = []
        for para in s.split("\n"):
            band = para.startswith("!")
            para = para[1:] if band else para
            cur = ""
            for w in para.split(" "):
                t = (cur + " " + w).strip()
                if self.tw(t.replace("{", "").replace("}", ""), f) > maxw and cur:
                    out.append((band, cur)); cur = w
                else:
                    cur = t
            out.append((band, cur))
        return out

    def rich(self, x, y, s, f, fill, maxw=W - 2 * M, lh=1.5, hi=NAVY, mark=MARK, band=BLUE):
        size = f.size / K
        on = False
        for i, (isband, ln) in enumerate(self.wrap(s, f, maxw)):
            ly = y + i * size * lh
            plain = ln.replace("{", "").replace("}", "")
            if isband:
                self.rect([x - size * .12, ly + size * .08, x + self.tw(plain, f) + size * .18, ly + size * 1.22], band)
            cx, buf = x, ""
            for ch in ln + "\0":
                if ch in "{}\0":
                    if buf:
                        w = self.tw(buf, f)
                        if on and not isband:
                            self.rect([cx - 2, ly + size * .62, cx + w + 2, ly + size * 1.2], mark)
                        col = "white" if isband else (hi if on else fill)
                        self.text((cx, ly), buf, f, col)
                        cx += w; buf = ""
                    on = (ch == "{") if ch in "{}" else on
                else:
                    buf += ch
        return y + len(self.wrap(s, f, maxw)) * size * lh

    def save(self, p):
        self.im.resize((W, H), Image.LANCZOS).save(p, optimize=True)


def logo(c, x, y, size, col=INK, colon=BLUE):
    f = F(SERIF_K, size)
    for part, cl in (("To", col), (":", colon), ("Day", col)):
        c.text((x, y), part, f, cl); x += c.tw(part, f) + (size * .03 if part == ":" or part == "To" else 0)
    return x


def masthead(c, meta, tag):
    logo(c, M, 58, 38)
    f = F(SANS["Bold"], 22)
    c.text((W - M, 66), f'{tag}  |  {meta["date"]}', f, GRAY, anchor="ra")
    c.rect([M, 118, W - M, 121], INK)


def footer(c, src, page, total):
    if src:
        c.text((M, H - 74), src, F(SANS["Regular"], 21), LIGHT)
    # 페이지 점
    x = W - M
    for i in range(total, 0, -1):
        r = 7 if i == page else 5
        c.circ(x - r, H - 62, r, BLUE if i == page else LINE)
        x -= 26


# ---------- 슬라이드 타입 ----------
def s_cover(c, s, meta, n, total, dy=0):
    logo(c, M, 64, 44)
    c.text((W - M, 78), meta["date"], F(SANS["Bold"], 24), GRAY, anchor="ra")
    c.rect([M, 136, W - M, 140], INK)
    c.rect([M, 146, W - M, 147], INK)
    y = 250 + dy
    c.text((M, y), s["kicker"], F(SANS["Black"], 34), BLUE)
    c.rect([M, y + 60, M + 60, y + 66], BLUE)
    y = c.rich(M, y + 120, s["headline"], F(SERIF_K, s.get("size", 118)), INK, lh=1.24)
    if s.get("sub"):
        y = c.rich(M, y + 40, s["sub"], F(SANS["Medium"], 40), GRAY, lh=1.55)
    end = y
    c.rect([M, H - 150, W - M, H - 149], INK)
    c.text((M, H - 118), s.get("tagline", "오늘 꼭 알아야 할 이야기, 투데이"), F(SANS["Medium"], 24), GRAY)
    c.text((W - M, H - 118), "넘겨서 보기  →", F(SANS["Black"], 26), INK, anchor="ra")
    return end


def s_post(c, s, meta, n, total, dy=0):  # 커뮤니티 글 / 본문 서술형
    masthead(c, meta, s.get("tag", meta["tag"]))
    y = 190 + dy
    if s.get("label"):
        c.circ(M + 24, y + 24, 24, NAVY)
        c.text((M + 24, y + 24), s.get("icon", "글"), F(SANS["Black"], 22), "white", anchor="mm")
        c.text((M + 64, y + 4), s["label"], F(SANS["Bold"], 26), INK)
        if s.get("label_sub"):
            c.text((M + 64, y + 40), s["label_sub"], F(SANS["Regular"], 22), GRAY)
        y += 110
    if s.get("title"):
        y = c.rich(M, y, s["title"], F(SERIF_K, 72), INK, lh=1.3) + 50
    y = c.rich(M, y, s["body"], F(SANS["Regular"], 48), INK, lh=1.7)
    footer(c, s.get("source", meta.get("source")), n, total)
    return y


def s_big(c, s, meta, n, total, dy=0):  # 한 문장을 크게
    masthead(c, meta, s.get("tag", meta["tag"]))
    y = 190 + dy
    if s.get("label"):
        c.text((M, y), s["label"], F(SANS["Black"], 32), BLUE)
        c.rect([M, y + 58, M + 60, y + 64], BLUE)
        y += 110
    y = c.rich(M, y, s["text"], F(SERIF_K, 80), INK, lh=1.38)
    if s.get("sub"):
        y = c.rich(M, y + 50, s["sub"], F(SANS["Regular"], 40), GRAY, lh=1.6)
    footer(c, s.get("source", meta.get("source")), n, total)
    return y


def s_comments(c, s, meta, n, total, dy=0):
    masthead(c, meta, s.get("tag", meta["tag"]))
    y = c.rich(M, 190 + dy, s["title"], F(SERIF_K, 66), INK, lh=1.3)
    if s.get("lead"):
        y = c.rich(M, y + 10, s["lead"], F(SANS["Regular"], 28), GRAY)
    y += 40
    for i, it in enumerate(s["items"]):
        c.rect([M, y, W - M, y + 1], LINE)
        y += 34
        c.circ(M + 26, y + 26, 26, ["#D9E4F7", "#E4E8EE", "#DCE9F2", "#E8E4F0"][i % 4])
        c.text((M + 26, y + 26), it.get("who", "익명")[-1], F(SANS["Bold"], 22), NAVY, anchor="mm")
        c.text((M + 70, y + 8), it.get("who", "누리꾼"), F(SANS["Bold"], 26), GRAY)
        y = c.rich(M + 70, y + 52, it["text"], F(SANS["Medium"], 40), INK, maxw=W - 2 * M - 70, lh=1.55) + 26
    c.rect([M, y, W - M, y + 1], LINE)
    footer(c, s.get("source", meta.get("source")), n, total)
    return y


def s_check(c, s, meta, n, total, dy=0):  # 저장용 체크리스트
    masthead(c, meta, s.get("tag", meta["tag"]))
    y = c.rich(M, 190 + dy, s["title"], F(SERIF_K, 66), INK, lh=1.3) + 60
    for i, it in enumerate(s["items"], 1):
        c.text((M, y - 6), f"{i:02d}", F(SERIF_K, 56), BLUE)
        y2 = c.rich(M + 110, y, it["head"], F(SANS["Bold"], 40), INK, maxw=W - 2 * M - 110, lh=1.4)
        if it.get("desc"):
            y2 = c.rich(M + 110, y2 + 4, it["desc"], F(SANS["Regular"], 32), GRAY, maxw=W - 2 * M - 110, lh=1.5)
        y = y2 + 56
    footer(c, s.get("source", meta.get("source")), n, total)
    return y


def s_ask(c, s, meta, n, total, dy=0):  # 댓글 유도 + 팔로우
    masthead(c, meta, s.get("tag", meta["tag"]))
    y = c.rich(M, 220, s["title"], F(SERIF_K, 80), INK, lh=1.3) + 50
    for i, opt in enumerate(s["options"]):
        c.rect([M, y, W - M, y + 130], "white")
        c.rect([M, y, W - M, y + 2], INK); c.rect([M, y + 128, W - M, y + 130], INK)
        c.text((M + 10, y + 65), "AB"[i], F(SERIF_K, 64), BLUE, anchor="lm")
        c.rich(M + 90, y + 38, opt, F(SANS["Bold"], 38), INK, maxw=W - 2 * M - 100)
        y += 160
    c.text((M, y + 20), s.get("cta", "댓글로 A / B 남겨주세요"), F(SANS["Bold"], 32), BLUE)
    c.rect([0, H - 230, W, H], NAVY)
    x = logo(c, M, H - 196, 52, col="white", colon="#7FA8F5")
    c.text((M, H - 110), "팔로우하면 매일 오늘의 이야기를 받아볼 수 있어요", F(SANS["Medium"], 28), "#B9CBEA")
    return None


TYPES = {"cover": s_cover, "post": s_post, "big": s_big, "comments": s_comments, "check": s_check, "ask": s_ask}


def render(issue, out):
    os.makedirs(out, exist_ok=True)
    meta, slides = issue["meta"], issue["slides"]
    paths = []
    for i, s in enumerate(slides, 1):
        fn = TYPES[s["type"]]
        end = fn(Card(), s, meta, i, len(slides))  # 1차: 높이 측정
        dy = 0
        if end is not None:
            free = (H - (190 if s["type"] == "cover" else 150)) - end
            dy = max(0, free * (0.55 if s["type"] == "cover" else 0.42))
        c = Card()
        fn(c, s, meta, i, len(slides), dy)
        p = os.path.join(out, f"{i:02d}.png"); c.save(p); paths.append(p)
    return paths


if __name__ == "__main__":
    print("\n".join(render(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])))
