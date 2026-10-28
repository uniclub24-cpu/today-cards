"""무료 사진 불러오기: Pixabay → Openverse → 위키미디어 커먼즈 순서로 검색해 raw/NN.jpg 저장.
슬라이드에 "photo": {"q": "night street car", "commons": "ILLIT"} 처럼 적는다.
  q        : 영어 키워드 (Pixabay/Openverse)
  commons  : 실제 인물·행사 사진이 필요할 때 위키미디어 검색어 (우선 시도)
출처는 raw/credits.json 에 저장되고 카드 하단에 자동 표기된다.
환경변수: PIXABAY_API_KEY (없으면 Openverse/커먼즈만 사용)
"""
import json, os, sys, io, re, html
import urllib.request, urllib.parse, urllib.error
from PIL import Image, ImageOps

UA = {"User-Agent": "ToDayCardNews/1.0 (https://github.com/uniclub24-cpu/today-cards)"}
KEY = os.environ.get("PIXABAY_API_KEY", "")


def note(msg, level="notice"):
    if KEY:
        msg = msg.replace(KEY, "***")
    print(f"::{level}::" + msg.replace("%", "%25").replace("\n", "%0A"))


def get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            return json.load(r)
    except Exception as e:
        note(f"요청 실패 {url.split('?')[0]}: {e}", "warning")
        return {}


def download(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def score(w, h):
    # 세로 4:5에 가까울수록, 클수록 우선
    return -abs(w / max(h, 1) - 0.8) * 3 + min(w * h, 4e6) / 4e6


def pixabay(q, used):
    if not KEY:
        return None
    for orient in ("vertical", "all"):
        p = {"key": KEY, "q": q, "image_type": "photo", "safesearch": "true", "per_page": 30, "orientation": orient, "order": "popular"}
        hits = get_json("https://pixabay.com/api/?" + urllib.parse.urlencode(p)).get("hits", [])
        hits = [h for h in hits if h["largeImageURL"] not in used]
        if hits:
            h = max(hits, key=lambda h: score(h["imageWidth"], h["imageHeight"]) + h.get("likes", 0) / 5000)
            return h["largeImageURL"], f"사진: {h.get('user', 'Pixabay')} · Pixabay", h.get("pageURL", "")
    return None


def openverse(q, used):
    p = {"q": q, "license_type": "commercial,modification", "page_size": 30, "mature": "false"}
    res = get_json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(p)).get("results", [])
    res = [r for r in res if r.get("url") not in used and (r.get("width") or 0) >= 800]
    if not res:
        return None
    r = max(res, key=lambda r: score(r.get("width") or 1, r.get("height") or 1))
    lic = f"CC {r.get('license', '').upper()} {r.get('license_version', '')}".strip()
    return r["url"], f"사진: {r.get('creator') or '작가 미상'} · {lic}", r.get("foreign_landing_url", "")


def commons(q, used):
    p = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{q} filetype:bitmap",
         "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1400}
    pages = get_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)).get("query", {}).get("pages", {})
    cands = []
    for pg in pages.values():
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not re.search(r"CC BY|CC0|Public domain", lic, re.I) or "NC" in lic or "ND" in lic:
            continue
        url = ii.get("thumburl") or ii.get("url")
        if not url or url in used or (ii.get("width") or 0) < 800:
            continue
        artist = re.sub("<[^>]+>", "", html.unescape(md.get("Artist", {}).get("value", ""))).strip()[:40] or "작가 미상"
        cands.append((score(ii["width"], ii["height"]), url, f"사진: {artist} · {lic} · Wikimedia Commons", pg.get("title", "")))
    if not cands:
        return None
    _, url, credit, title = max(cands)
    return url, credit, "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_")


def thumb(im):
    return list(ImageOps.fit(im, (16, 20)).convert("L").getdata())


def is_dup(im, others):
    t = thumb(im)
    return any(sum(abs(a - b) for a, b in zip(t, o)) / len(t) < 12 for o in others)


def main(folder, force=False):
    issue = json.load(open(os.path.join(folder, "issue.json"), encoding="utf-8"))
    raw = os.path.join(folder, "raw"); os.makedirs(raw, exist_ok=True)
    cpath = os.path.join(raw, "credits.json")
    credits = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
    used, got, miss = set(), 0, []
    spath = os.path.join(raw, "sources.json")
    srcs = json.load(open(spath, encoding="utf-8")) if os.path.exists(spath) else {}
    for i, s in enumerate(issue["slides"], 1):
        ph = s.get("photo")
        if not ph:
            continue
        name = s.setdefault("img", f"{i:02d}.jpg")
        path = os.path.join(raw, name)
        if os.path.exists(path) and not force:
            continue
        others = [thumb(Image.open(os.path.join(raw, f))) for f in os.listdir(raw)
                  if f.endswith(".jpg") and f != name]
        found = img = None
        for attempt in range(5):  # 같은 게시물 안에서 중복 사진 피하기
            found = None
            if ph.get("commons"):
                found = commons(ph["commons"], used)
            for q in [ph.get("q")] + ph.get("alt", []):
                if found or not q:
                    break
                found = pixabay(q, used) or openverse(q, used)
            if not found:
                break
            try:
                img = download(found[0])
            except Exception as e:
                note(f"{i}번 사진 다운로드 실패: {e}", "warning"); used.add(found[0]); found = None; continue
            if is_dup(img, others):
                used.add(found[0]); found = None; continue
            break
        if not found:
            miss.append(i); continue
        url, credit, page = found
        ImageOps.fit(img, (1080, 1350), Image.LANCZOS, centering=(0.5, ph.get("focus", 0.45))).save(path, quality=92)
        used.add(url); credits[str(i)] = credit; got += 1
        srcs[str(i)] = {"query": ph, "page": page, "image": url}
    json.dump(credits, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(srcs, open(spath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    note(f"무료 사진 {got}장 확보" + (f", 못 찾은 장: {miss} (글 카드로 대체)" if miss else ""))
    return miss


if __name__ == "__main__":
    main(sys.argv[1], "--force" in sys.argv)
