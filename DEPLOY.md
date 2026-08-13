# 배포 가이드

Vercel + Firebase 로 런웨이 대시보드를 올리는 순서입니다. 위에서부터 그대로 따라가면 됩니다.

## 무엇이 어디에 올라가는가

| | 로컬 `dashboard.html` | 배포판 `public/index.html` |
|---|---|---|
| 거래내역 168건 | 파일에 포함 | **없음** |
| 계좌번호 · 실명 | 파일에 포함 | **없음** |
| 5~7월 실적 분석 | 포함 | 없음 |
| 반복 스케줄 · 잔액 | 파일에 포함 | Firestore 에서 로그인 후 로드 |
| 로그인 | 없음 | Firebase 이메일/비밀번호 |

> **왜 나눴나**
> 정적 파일에 로그인 화면만 씌우는 건 보호가 아닙니다. 데이터가 파일 안에 있으면
> 로그인 없이 파일만 받아도 다 읽힙니다. 그래서 배포판에는 데이터를 아예 넣지 않고,
> 로그인한 뒤 Firestore 에서 받아오게 했습니다. `build.py` 는 빌드할 때마다
> 배포판에 데이터가 섞이지 않았는지 검사하고, 섞였으면 빌드를 중단합니다.

---

## 1. Firebase 웹 앱 등록

Firebase 콘솔 → **프로젝트 설정(⚙)** → **일반** → 내 앱 → **웹(`</>`)** 추가.
호스팅 설정은 체크하지 않아도 됩니다. 나온 `firebaseConfig` 값을 복사합니다.

```bash
cp public/firebase-config.example.js public/firebase-config.js
```

`public/firebase-config.js` 를 열어 복사한 값을 채우고, `DATABASE_ID` 를
데이터베이스 이름(`runway`, 기본이면 `(default)`)에 맞춥니다.

> 이 파일의 `apiKey` 는 비밀이 아닙니다. Firebase 웹 키는 공개되도록 설계됐고
> 실제 보호는 로그인 + 보안 규칙이 합니다. 그래서 **커밋해야 합니다** (배포에 필요).
>
> ⚠ 다운로드하신 `firebase-adminsdk-*.json` 은 여기에 절대 넣지 마세요. 그건 서버 전용
> 관리자 키로 보안 규칙을 전부 우회합니다. `.gitignore` 로 커밋도 막아 뒀습니다.

## 2. 로그인 계정 만들기

콘솔 → **Authentication** → 시작하기 → **이메일/비밀번호** 사용 설정 →
**Users** 탭 → **사용자 추가** 로 본인 계정을 만듭니다.

가입 화면은 만들지 않았습니다. 콘솔에서 만든 계정만 로그인할 수 있어,
URL 이 새어 나가도 남이 계정을 만들 수 없습니다.

## 3. 보안 규칙 게시

콘솔 → **Firestore Database** → **규칙** 에 `firestore.rules` 내용을 붙여넣고 **게시**.

본인 문서만 읽고 쓸 수 있으며, 웹에서는 `balances` 만 수정 가능합니다.
스케줄 위조는 막혀 있고, 스케줄 갱신은 4번의 씨딩으로만 됩니다.

## 4. 데이터 올리기 (씨딩)

```bash
pip install firebase-admin
```

Windows PowerShell:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\SCHOOL28\Downloads\claude-d9bc1-firebase-adminsdk-fbsvc-74728a485d.json"
$env:RUNWAY_EMAIL="2번에서 만든 이메일"
$env:RUNWAY_DB="runway"
python build/seed_firestore.py
```

관리자 키는 이 PC를 벗어나지 않습니다. 잔액과 반복 스케줄만 올라가고
거래내역 원본은 올라가지 않습니다.

## 5. Vercel 연결

Node 가 설치돼 있지 않으므로 CLI 대신 **GitHub 연동**을 씁니다 (더 편하기도 합니다).

1. 먼저 커밋 & 푸시

   ```bash
   git add -A && git commit -m "Vercel 배포 설정" && git push
   ```

2. [vercel.com](https://vercel.com) 에 GitHub 계정으로 로그인
3. **Add New… → Project** → `mina-han/runway` **Import**
4. 설정은 건드리지 마세요. `vercel.json` 이 `public/` 을 배포하도록 이미 지정합니다
5. **Deploy**

이후 `main` 에 푸시할 때마다 자동 배포됩니다.

## 6. 확인

배포 URL 을 열어 2번 계정으로 로그인합니다. 소진일과 잔고 흐름이 보이면 성공입니다.
잔액을 고치면 우상단에 "저장됨"이 뜨고, 다른 기기에서 열어도 같은 값이 보입니다.

---

## 갱신

**새 명세서가 생겼을 때** — 스케줄까지 다시 계산합니다.

```bash
python build/analyze.py && python build/build.py && python build/seed_firestore.py
git add -A && git commit -m "8월 거래내역 반영" && git push
```

**잔액만 바뀌었을 때** — 배포된 사이트에서 직접 고치면 됩니다. 아무것도 실행할 필요 없습니다.

---

## 남는 위험

- **URL 은 누구나 접근 가능합니다.** 로그인 화면까지는 열립니다. 데이터는 Firestore
  규칙이 막으므로 로그인 없이는 아무것도 못 봅니다.
- **비밀번호를 길게 쓰세요.** 이 계정 하나가 유일한 방어선입니다.
  콘솔에서 다단계 인증을 켜면 더 좋습니다.
- **`public/` 에 다른 파일을 넣지 마세요.** 그 폴더는 전부 공개됩니다.
  `data.json` 이나 `dashboard.html` 을 실수로 넣으면 데이터가 그대로 노출됩니다.
- 검색엔진 색인은 `robots.txt` 와 `X-Robots-Tag` 헤더로 막아 뒀습니다.
