"""To:Day 게시 스크립트 — GitHub Actions에서 실행된다.

posts/<폴더>/post.json 과 01.jpg, 02.jpg ... 를 읽어
인스타그램(캐러셀)과 스레드(캐러셀)에 게시하고, 결과를 published.json 으로 남긴다.

환경변수: IG_TOKEN, THREADS_TOKEN, REPO(owner/name), SHA(커밋)
사용:  python scripts/publish.py check            # 토큰 확인만
       python scripts/publish.py post posts/20261028-sikhye
"""
import json, os, sys, time, glob
import urllib.request, urllib.parse, urllib.error

IG = "https://graph.instagram.com/v23.0"
TH = "https://graph.threads.net/v1.0"


def fail(msg):
    """GitHub 화면(annotations)에 오류가 보이도록 출력 후 종료. 토큰은 절대 출력하지 않는다."""
    for k in ("IG_TOKEN", "THREADS_TOKEN"):
        v = os.environ.get(k)
        if v:
            msg = msg.replace(v, "***")
    print("::error::" + msg.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))
    raise SystemExit(1)


def call(method, url, params):
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        # 토큰이 로그에 찍히지 않도록 오류 본문만 출력
        fail(f"API 오류 {e.code} @ {url.split('?')[0]}\n{body}")


def wait_ready(base, cid, token, field="status_code", ok=("FINISHED",), tries=20):
    for _ in range(tries):
        st = call("GET", f"{base}/{cid}", {"fields": field if base == IG else "status", "access_token": token})
        s = st.get(field) or st.get("status")
        if s in ok or s == "PUBLISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            fail(f"컨테이너 오류: {st}")
        time.sleep(3)
    fail(f"컨테이너 준비 시간 초과: {cid}")


def check():
    for k in ("IG_TOKEN", "THREADS_TOKEN"):
        v = os.environ.get(k, "")
        if not v:
            if k == "THREADS_TOKEN":
                print("스레드 토큰 없음 — 스레드 점검 건너뜀"); continue
            fail(f"{k} Secret이 비어 있음")
        if v != v.strip():
            fail(f"{k} 앞뒤에 공백/줄바꿈이 있음 — Secret을 다시 붙여넣어 주세요")
    ig = call("GET", f"{IG}/me", {"fields": "user_id,username,account_type", "access_token": os.environ["IG_TOKEN"]})
    print(f"::notice::인스타 OK: @{ig.get('username')} ({ig.get('account_type')})")
    lim = call("GET", f"{IG}/me/content_publishing_limit", {"fields": "quota_usage,config", "access_token": os.environ["IG_TOKEN"]})
    print("::notice::인스타 게시 한도: " + json.dumps(lim.get("data", lim), ensure_ascii=False))
    if not os.environ.get("THREADS_TOKEN"):
        return
    th = call("GET", f"{TH}/me", {"fields": "id,username", "access_token": os.environ["THREADS_TOKEN"]})
    print("스레드 OK:", th.get("username"))


def urls(folder):
    repo, sha = os.environ["REPO"], os.environ["SHA"]
    files = sorted(glob.glob(os.path.join(folder, "[0-9][0-9].jpg")))
    if not 2 <= len(files) <= 10:
        fail(f"이미지는 2~10장이어야 함 (현재 {len(files)}장)")
    return [f"https://raw.githubusercontent.com/{repo}/{sha}/{f}" for f in files]


def post_instagram(imgs, caption):
    t = os.environ["IG_TOKEN"]
    kids = []
    for u in imgs:
        r = call("POST", f"{IG}/me/media", {"image_url": u, "is_carousel_item": "true", "access_token": t})
        kids.append(r["id"])
    for k in kids:
        wait_ready(IG, k, t)
    parent = call("POST", f"{IG}/me/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": caption, "access_token": t})
    wait_ready(IG, parent["id"], t)
    pub = call("POST", f"{IG}/me/media_publish", {"creation_id": parent["id"], "access_token": t})
    link = call("GET", f"{IG}/{pub['id']}", {"fields": "permalink", "access_token": t}).get("permalink")
    return {"id": pub["id"], "permalink": link}


def post_threads(imgs, text):
    t = os.environ["THREADS_TOKEN"]
    kids = []
    for u in imgs:
        r = call("POST", f"{TH}/me/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true", "access_token": t})
        kids.append(r["id"])
    time.sleep(10)
    parent = call("POST", f"{TH}/me/threads", {"media_type": "CAROUSEL", "children": ",".join(kids), "text": text[:500], "access_token": t})
    time.sleep(15)  # Meta 권장: 게시 전 대기
    pub = call("POST", f"{TH}/me/threads_publish", {"creation_id": parent["id"], "access_token": t})
    link = call("GET", f"{TH}/{pub['id']}", {"fields": "permalink", "access_token": t}).get("permalink")
    return {"id": pub["id"], "permalink": link}


def post(folder):
    meta = json.load(open(os.path.join(folder, "post.json"), encoding="utf-8"))
    done_path = os.path.join(folder, "published.json")
    done = json.load(open(done_path)) if os.path.exists(done_path) else {}
    if not meta.get("approved"):
        print("승인되지 않은 게시물 — 건너뜀:", folder); return
    imgs = urls(folder)
    targets = meta.get("platforms", ["instagram", "threads"])
    if "instagram" in targets and "instagram" not in done:
        done["instagram"] = post_instagram(imgs, meta["caption"]); print("인스타 게시 완료:", done["instagram"])
    if "threads" in targets and "threads" not in done:
        done["threads"] = post_threads(imgs, meta.get("threads_text", meta["caption"])); print("스레드 게시 완료:", done["threads"])
    done["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(done, open(done_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        check()
    elif cmd == "post":
        for f in sys.argv[2:]:
            post(f)
