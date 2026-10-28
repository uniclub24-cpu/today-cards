# To:Day 카드뉴스 자동 게시

- `posts/<날짜-제목>/` : 01.jpg~10.jpg + post.json
- post.json의 `approved`가 `true`로 커밋되면 GitHub Actions가 인스타그램·스레드에 자동 게시
- 토큰은 저장소 Secrets(`IG_TOKEN`, `THREADS_TOKEN`)에만 보관
- `Check tokens` 워크플로: 토큰 상태 점검 (매주 월요일 자동)
