# -*- coding: utf-8 -*-
"""data.json 의 잔액·반복 스케줄을 Firestore 에 올린다.

배포판(public/index.html)은 이 문서를 읽어 런웨이를 그린다.
거래내역 원본은 올리지 않는다 — 클라우드로 나가는 건 잔액과 스케줄뿐이다.

이 스크립트는 로컬에서만 돌리며, service account 키는 이 PC를 벗어나지 않는다.

사전 준비
  pip install firebase-admin

  # 키 경로 (다운로드 폴더의 firebase-adminsdk-*.json)
  set GOOGLE_APPLICATION_CREDENTIALS=C:\\Users\\...\\claude-...-adminsdk-....json
  # 로그인에 쓸 계정 (Firebase 콘솔 Authentication 에 미리 등록해 둘 것)
  set RUNWAY_EMAIL=you@example.com
  # Firestore 데이터베이스 이름 (기본이면 생략)
  set RUNWAY_DB=runway

실행
  python build/seed_firestore.py
"""
import json, os, sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.dirname(HERE)

KEY   = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '').strip('"')
EMAIL = os.environ.get('RUNWAY_EMAIL', '').strip()
DB_ID = os.environ.get('RUNWAY_DB', 'runway').strip()

if not KEY or not os.path.exists(KEY):
    sys.exit('GOOGLE_APPLICATION_CREDENTIALS 에 service account 키 경로를 지정하세요.\n'
             f'  현재 값: {KEY or "(없음)"}')
if not EMAIL:
    sys.exit('RUNWAY_EMAIL 에 로그인할 계정 이메일을 지정하세요.')

try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
except ImportError:
    sys.exit('firebase-admin 이 없습니다.  pip install firebase-admin')

data = json.load(open(os.path.join(DEST, 'data.json'), encoding='utf-8'))

# 배포판이 쓰는 필드만 추린다. 거래내역(tx)·잔액추이는 의도적으로 제외한다.
KEEP = ('name', 'flow', 'category', 'day', 'amount', 'lo', 'hi',
        'last', 'volatile', 'n_months')
payload = {
    'schedule':  [{k: r[k] for k in KEEP} for r in data['schedule']],
    'balances':  data['start']['balances'],
    'startDate': data['start']['date'],
    'asOf':      data['start']['as_of'],
}

firebase_admin.initialize_app(credentials.Certificate(KEY))
try:
    uid = auth.get_user_by_email(EMAIL).uid
except auth.UserNotFoundError:
    sys.exit(f'{EMAIL} 계정이 없습니다.\n'
             'Firebase 콘솔 → Authentication → Users → 사용자 추가 로 먼저 만드세요.')

try:
    db = firestore.client(database_id=DB_ID)
except TypeError:                      # 구버전 SDK: 기본 데이터베이스만 지원
    if DB_ID not in ('', '(default)'):
        sys.exit('설치된 firebase-admin 이 이름 있는 데이터베이스를 지원하지 않습니다.\n'
                 '  pip install -U firebase-admin  후 다시 실행하세요.')
    db = firestore.client()

ref = db.collection('users').document(uid).collection('runway').document('state')
ref.set(payload, merge=True)

out = sum(r['amount'] for r in payload['schedule'] if r['flow'] == '지출')
inn = sum(r['amount'] for r in payload['schedule'] if r['flow'] == '수입')
print(f'업로드 완료  →  users/{uid}/runway/state   (database: {DB_ID})')
print(f'  계정      {EMAIL}')
print(f'  반복 항목  {len(payload["schedule"])}건  (월 지출 {out:,}원 / 월 수입 {inn:,}원)')
print(f'  잔액      {sum(payload["balances"].values()):,}원  ({payload["asOf"]} 기준)')
print(f'  기준일    {payload["startDate"]}')
print('\n거래내역 원본은 올리지 않았습니다.')
