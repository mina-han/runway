# -*- coding: utf-8 -*-
"""잔액·반복 스케줄을 비밀번호로 암호화해서 Firestore 에 올린다.

거래내역 원본은 올리지 않는다 — 클라우드로 나가는 건 잔액과 스케줄뿐이고,
그마저도 암호문이라 비밀번호 없이는 읽을 수 없다.

암호 방식 (브라우저 WebCrypto 와 호환)
    PBKDF2-HMAC-SHA256, 310,000회, salt 16바이트 → AES-256-GCM 키
    AES-GCM, IV 12바이트, 인증태그 16바이트가 암호문 뒤에 붙는다
Firestore 에는 salt/iv/ct 를 base64 로 저장한다. 평문은 올라가지 않는다.

사전 준비
  pip install firebase-admin cryptography

  # .env 에 값을 넣어두면 자동으로 읽는다 (python-dotenv 없어도 동작)
  GOOGLE_APPLICATION_CREDENTIALS=...adminsdk....json
  RUNWAY_PASSWORD=<대시보드를 여는 비밀번호>
  RUNWAY_DB=runway

실행
  python build/seed_firestore.py
"""
import base64, json, os, sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.dirname(HERE)

ITERATIONS = 310_000


def load_env():
    """.env 를 읽어 환경변수에 채운다 (이미 설정된 값이 우선)."""
    p = os.path.join(DEST, '.env')
    if not os.path.exists(p):
        return
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

KEY   = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '').strip('"')
PW    = os.environ.get('RUNWAY_PASSWORD', '')
DB_ID = os.environ.get('RUNWAY_DB', 'runway').strip()

if not KEY or not os.path.exists(KEY):
    sys.exit('GOOGLE_APPLICATION_CREDENTIALS 에 service account 키 경로를 지정하세요.\n'
             f'  현재 값: {KEY or "(없음)"}')
if not PW:
    sys.exit('RUNWAY_PASSWORD 를 .env 에 지정하세요. 대시보드 로그인에 쓸 비밀번호입니다.')

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    sys.exit('firebase-admin 이 없습니다.  pip install firebase-admin')
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit('cryptography 가 없습니다.  pip install cryptography')

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

plaintext = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
salt = os.urandom(16)
iv   = os.urandom(12)
key  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                  iterations=ITERATIONS).derive(PW.encode())
ct   = AESGCM(key).encrypt(iv, plaintext, None)

b64 = lambda b: base64.b64encode(b).decode()
doc = {'v': 1, 'iterations': ITERATIONS,
       'salt': b64(salt), 'iv': b64(iv), 'ct': b64(ct)}

firebase_admin.initialize_app(credentials.Certificate(KEY))
try:
    db = firestore.client(database_id=DB_ID)
except TypeError:                      # 구버전 SDK: 기본 데이터베이스만 지원
    if DB_ID not in ('', '(default)'):
        sys.exit('설치된 firebase-admin 이 이름 있는 데이터베이스를 지원하지 않습니다.\n'
                 '  pip install -U firebase-admin  후 다시 실행하세요.')
    db = firestore.client()

db.collection('runway').document('state').set(doc)

out = sum(r['amount'] for r in payload['schedule'] if r['flow'] == '지출')
inn = sum(r['amount'] for r in payload['schedule'] if r['flow'] == '수입')
print(f'업로드 완료  →  runway/state   (database: {DB_ID})')
print(f'  반복 항목  {len(payload["schedule"])}건  (월 지출 {out:,}원 / 월 수입 {inn:,}원)')
print(f'  잔액      {sum(payload["balances"].values()):,}원  ({payload["asOf"]} 기준)')
print(f'  암호문    {len(doc["ct"])}자  (평문 {len(plaintext)}바이트)')
print(f'  비밀번호  {len(PW)}자')
if len(PW) < 10:
    print(f'\n  ⚠ 비밀번호가 {len(PW)}자입니다. 암호문을 가져간 사람이 짧은 비밀번호는')
    print('    금방 뚫습니다. 긴 문구로 바꾸고 이 스크립트를 다시 실행하면')
    print('    코드 수정 없이 그대로 강해집니다.')
print('\n거래내역 원본은 올리지 않았습니다.')
