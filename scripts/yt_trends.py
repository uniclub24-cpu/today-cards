"""유튜브 한국 인기 급상승 영상 + 인기 댓글을 모아 data/youtube/YYYYMMDD.json 으로 저장.
환경변수: YOUTUBE_API_KEY
사용: python scripts/yt_trends.py [최대개수=30] [댓글영상수=10]
"""
import json, os, sys, re, time, datetime
import urllib.request, urllib.parse, urllib.error

API = "https://www.googleapis.com/youtube/v3"
KEY = os.environ.get("YOUTUBE_API_KEY", "")


def note(msg, level="notice"):
    if KEY:
        msg = msg.replace(KEY, "***")
    print(f"::{level}::" + msg.replace("%", "%25").replace("\n", "%0A"))


def get(path, **p):
    p["key"] = KEY
    url = f"{API}/{path}?" + urllib.parse.urlencode(p)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode(errors="replace")[:500]}


def secs(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def main(n=30, ncomments=10):
    if not KEY:
        note("YOUTUBE_API_KEY Secret을 찾을 수 없음", "error"); sys.exit(1)
    cats = get("videoCategories", part="snippet", regionCode="KR", hl="ko_KR")
    if "_error" in cats:
        note(f"API 오류 {cats['_error']}: {cats['_body']}", "error"); sys.exit(1)
    catname = {c["id"]: c["snippet"]["title"] for c in cats.get("items", [])}
    res = get("videos", part="snippet,statistics,contentDetails", chart="mostPopular", regionCode="KR", maxResults=min(n, 50), hl="ko")
    if "_error" in res:
        note(f"API 오류 {res['_error']}: {res['_body']}", "error"); sys.exit(1)
    out = []
    for rank, v in enumerate(res.get("items", []), 1):
        sn, st = v["snippet"], v.get("statistics", {})
        dur = secs(v.get("contentDetails", {}).get("duration"))
        item = {
            "rank": rank, "id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}",
            "title": sn.get("title"), "channel": sn.get("channelTitle"), "published": sn.get("publishedAt"),
            "category": catname.get(sn.get("categoryId"), sn.get("categoryId")),
            "duration_sec": dur, "is_short": dur is not None and dur <= 180,
            "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)) if "likeCount" in st else None,
            "comments": int(st.get("commentCount", 0)) if "commentCount" in st else None,
            "tags": sn.get("tags", [])[:15], "description": (sn.get("description") or "")[:1500],
        }
        if rank <= ncomments and item["comments"]:
            c = get("commentThreads", part="snippet", videoId=v["id"], order="relevance", maxResults=8, textFormat="plainText")
            item["top_comments"] = [
                {"text": t["snippet"]["topLevelComment"]["snippet"]["textDisplay"][:300],
                 "likes": t["snippet"]["topLevelComment"]["snippet"].get("likeCount", 0)}
                for t in c.get("items", [])] if "_error" not in c else []
        out.append(item)
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    os.makedirs("data/youtube", exist_ok=True)
    path = f"data/youtube/{kst:%Y%m%d}.json"
    json.dump({"fetched_kst": f"{kst:%Y-%m-%d %H:%M}", "region": "KR", "chart": "mostPopular", "videos": out},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    note(f"인기 영상 {len(out)}개 저장 → {path} (쇼츠 길이 {sum(i['is_short'] for i in out)}개)")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 30, int(a[1]) if len(a) > 1 else 10)
