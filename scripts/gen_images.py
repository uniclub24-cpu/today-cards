"""Gemini로 카드뉴스 배경 사진을 만들고, render3로 글자를 합성해 01.jpg~ 를 만든다.
GitHub Actions에서 실행. 환경변수: GEMINI_API_KEY
사용: python scripts/gen_images.py posts/20261028-car [--force]
"""
import json, os, sys, base64, io, time, subprocess
import urllib.request, urllib.error
from PIL import Image, ImageOps

API = "https://generativelanguage.googleapis.com/v1beta"
TAIL = ", photorealistic, natural film grain, vertical 4:5 composition, no text, no letters, no logos, no watermark, no recognizable faces"


def note(msg, level="notice"):
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        msg = msg.replace(key, "***")
    print(f"::{level}::" + msg.replace("%", "%25").replace("\n", "%0A"))


def req(method, url, body=None):
    r = urllib.request.Request(url, method=method, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
                               data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(r, timeout=180) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode(errors="replace")[:600]}


def pick_model():
    want = os.environ.get("GEMINI_IMAGE_MODEL")
    if want:
        return want
    res = req("GET", f"{API}/models?pageSize=200")
    if "_error" in res:
        note(f"모델 목록 조회 실패 {res['_error']}: {res['_body']}", "error"); sys.exit(1)
    names = [m["name"].split("/")[-1] for m in res.get("models", [])
             if "image" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
    pref = sorted(names, key=lambda n: (("flash" not in n), ("preview" in n), -len(n)))
    if not pref:
        note("이미지 생성 가능한 Gemini 모델이 없음. 사용 가능 모델: " + ", ".join(m["name"] for m in res.get("models", [])[:30]), "error"); sys.exit(1)
    return pref[0]


def generate(model, prompt):
    body = {"contents": [{"parts": [{"text": prompt + TAIL}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:5"}}}
    for attempt in range(3):
        res = req("POST", f"{API}/models/{model}:generateContent", body)
        if "_error" in res and res["_error"] == 400 and "imageConfig" in body["generationConfig"]:
            body["generationConfig"].pop("imageConfig"); continue  # 비율 옵션 미지원 모델이면 빼고 재시도
        if "_error" in res:
            if res["_error"] in (429, 500, 503):
                note(f"[{model}] 재시도 {attempt + 1}: 오류 {res['_error']} {res['_body'][:400]}", "warning")
                time.sleep(15 * (attempt + 1)); continue
            note(f"이미지 생성 오류 {res['_error']}: {res['_body']}", "error"); sys.exit(1)
        for c in res.get("candidates", []):
            for p in c.get("content", {}).get("parts", []):
                d = p.get("inlineData") or p.get("inline_data")
                if d:
                    return Image.open(io.BytesIO(base64.b64decode(d["data"]))).convert("RGB")
        note(f"이미지가 반환되지 않음: {json.dumps(res, ensure_ascii=False)[:400]}", "warning")
        time.sleep(5)
    note("이미지 생성 3회 실패: " + prompt[:60], "error"); sys.exit(1)


def main(folder, force=False):
    if not os.environ.get("GEMINI_API_KEY"):
        note("GEMINI_API_KEY Secret을 찾을 수 없음 (이름 확인 필요)", "error"); sys.exit(1)
    issue = json.load(open(os.path.join(folder, "issue.json"), encoding="utf-8"))
    raw = os.path.join(folder, "raw"); os.makedirs(raw, exist_ok=True)
    model = None
    made = 0
    for i, s in enumerate(issue["slides"], 1):
        name = s.get("img") or f"{i:02d}.jpg"; s["img"] = name
        path = os.path.join(raw, name)
        if os.path.exists(path) and not force:
            continue
        if not s.get("prompt"):
            continue
        if not model:
            model = pick_model(); note(f"사용 모델: {model}")
        im = generate(model, s["prompt"])
        ImageOps.fit(im, (1080, 1350), Image.LANCZOS).save(path, quality=92)
        made += 1
        time.sleep(2)
    note(f"사진 {made}장 생성 (모델: {model or '생성 안 함'})")
    # 글자 합성
    tmp = os.path.join(folder, "_render")
    subprocess.run([sys.executable, "scripts/render3.py", os.path.join(folder, "issue.json"), tmp, raw], check=True)
    for f in sorted(os.listdir(tmp)):
        Image.open(os.path.join(tmp, f)).convert("RGB").save(os.path.join(folder, f.replace(".png", ".jpg")), quality=92)
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    note(f"카드 {len(issue['slides'])}장 합성 완료: {folder}")


if __name__ == "__main__":
    main(sys.argv[1], "--force" in sys.argv)
