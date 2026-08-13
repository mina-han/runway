/* Firebase 웹 앱 설정 — 이 파일을 firebase-config.js 로 복사해서 값을 채우세요.
 *
 * 값은 Firebase 콘솔에서 가져옵니다:
 *   프로젝트 설정(⚙) → 일반 → 내 앱 → 웹 앱 추가(</>) → 'firebaseConfig' 복사
 *
 * ⚠ 다운로드하신 firebase-adminsdk-*.json 은 여기에 쓰지 마세요.
 *   그건 서버 전용 관리자 키라 브라우저 코드에 들어가면 프로젝트가 통째로 뚫립니다.
 *   (씨딩 스크립트 build/seed_firestore.py 에서만 로컬로 씁니다.)
 *
 * 아래 apiKey 는 비밀이 아닙니다. Firebase 웹 키는 공개되도록 설계돼 있고,
 * 실제 보호는 Authentication 로그인 + Firestore 보안 규칙이 담당합니다.
 * 그래서 이 파일은 저장소에 커밋해도 됩니다 (배포에 필요합니다).
 */

export const FIREBASE_CONFIG = {
  apiKey:            "여기에-붙여넣기",
  authDomain:        "claude-d9bc1.firebaseapp.com",
  projectId:         "claude-d9bc1",
  storageBucket:     "claude-d9bc1.firebasestorage.app",
  messagingSenderId: "여기에-붙여넣기",
  appId:             "여기에-붙여넣기",
};

/* Firestore 데이터베이스 이름.
 * 기본 데이터베이스면 '(default)', 'runway' 라는 이름으로 만들었으면 'runway'. */
export const DATABASE_ID = 'runway';
