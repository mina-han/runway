# -*- coding: utf-8 -*-
"""로컬 .env 값을 Vercel 프로젝트 환경변수로 밀어 넣는다.

값은 stdin 으로 vercel CLI 에 넘긴다 — 명령행 인자로 주면 셸 히스토리와
프로세스 목록에 비밀이 남기 때문이다.

    python build/sync_vercel_env.py --list          올릴 후보와 현재 상태만 확인
    python build/sync_vercel_env.py --only RUNWAY_DB,ANTHROPIC_API_KEY
    python build/sync_vercel_env.py --all           .env 의 모든 값 (경로형 제외)
    python build/sync_vercel_env.py --all --env preview,development

주의
  이 저장소의 배포판은 정적 파일이라 서버에서 환경변수를 읽는 코드가 없다.
  서버리스 함수(api/)를 추가하기 전에는 여기 올린 값이 쓰이지 않는다.
  쓰이지도 않는 곳에 비밀을 복사하지 않도록, 기본값은 아무것도 올리지 않는
  --list 이고 올릴 항목을 직접 골라야 한다.
"""
import argparse, os, shutil, subprocess, sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENV_PATH = os.path.join(ROOT, '.env')

# 로컬 경로라 Vercel 에서 의미가 없는 값 — 실수로 올리지 않게 기본 제외
LOCAL_ONLY = {'GOOGLE_APPLICATION_CREDENTIALS'}
# 비밀로 취급해 값을 절대 출력하지 않을 이름
SECRETISH = ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL')


def mask(name, value):
    if not value:
        return '(비어 있음)'
    if any(s in name.upper() for s in SECRETISH):
        return f'{value[:6]}…{value[-4:]} ({len(value)}자)' if len(value) > 14 else f'({len(value)}자)'
    return value


def read_env(path):
    if not os.path.exists(path):
        sys.exit(f'.env 가 없습니다: {path}')
    out = {}
    for raw in open(path, encoding='utf-8'):
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def vercel_bin():
    exe = shutil.which('vercel') or shutil.which('vercel.cmd')
    if not exe:
        sys.exit('vercel CLI 를 찾을 수 없습니다.\n'
                 '  npm i -g vercel   설치 후 다시 실행하세요.')
    return exe


def run(args, stdin=None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--list', action='store_true', help='올릴 후보만 보여주고 끝낸다')
    g.add_argument('--only', help='쉼표로 구분한 변수 이름만 올린다')
    g.add_argument('--all', action='store_true', help='.env 의 모든 값을 올린다')
    ap.add_argument('--env', default='production',
                    help='대상 환경 (production,preview,development 중 쉼표 구분)')
    ap.add_argument('--yes', action='store_true', help='확인 없이 진행')
    a = ap.parse_args()

    env = read_env(ENV_PATH)
    targets = [t.strip() for t in a.env.split(',') if t.strip()]

    if a.only:
        names = [n.strip() for n in a.only.split(',') if n.strip()]
        missing = [n for n in names if n not in env]
        if missing:
            sys.exit(f'.env 에 없는 변수: {", ".join(missing)}')
    elif a.all:
        names = [k for k in env if k not in LOCAL_ONLY]
    else:
        names = []

    print(f'.env  {ENV_PATH}')
    print(f'{"변수":34s} {"값":28s} 비고')
    print('─' * 78)
    for k, v in env.items():
        note = ('로컬 전용 — 올리지 않음' if k in LOCAL_ONLY else
                '올림' if k in names else '건너뜀')
        print(f'{k:34s} {mask(k, v):28s} {note}')

    if not names:
        print('\n올릴 항목이 없습니다. --only 또는 --all 로 지정하세요.')
        print('\n참고: 이 저장소의 배포판은 정적 파일이라, 서버리스 함수를 추가하기')
        print('      전에는 Vercel 환경변수를 읽는 코드가 없습니다.')
        return

    vercel = vercel_bin()
    print(f'\n대상 환경: {", ".join(targets)}')
    if not a.yes:
        if input(f'{len(names)}개 변수를 올립니다. 계속할까요? [y/N] ').strip().lower() != 'y':
            print('취소했습니다.')
            return

    ok = fail = 0
    for name in names:
        value = env[name]
        if not value:
            print(f'  건너뜀  {name}  (값이 비어 있음)')
            continue
        for target in targets:
            # 이미 있으면 지우고 다시 넣는다 (vercel env add 는 덮어쓰지 않는다)
            run([vercel, 'env', 'rm', name, target, '--yes'])
            # 값은 stdin 으로만 전달한다
            r = run([vercel, 'env', 'add', name, target], stdin=value + '\n')
            if r.returncode == 0:
                print(f'  올림    {name}  →  {target}')
                ok += 1
            else:
                msg = (r.stderr or r.stdout).strip().splitlines()
                print(f'  실패    {name}  →  {target}: {msg[-1] if msg else "원인 미상"}')
                fail += 1

    print(f'\n완료: 성공 {ok}건, 실패 {fail}건')
    if ok:
        print('값을 바꿨으면 재배포해야 반영됩니다:  vercel deploy --prod')
    if fail:
        sys.exit(1)


if __name__ == '__main__':
    main()
