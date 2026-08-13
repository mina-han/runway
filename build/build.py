# -*- coding: utf-8 -*-
"""템플릿 + data.json -> 결과물 2종

  dashboard.html      로컬 전용. 전체 거래내역과 5~7월 실적 분석 포함.
                      데이터가 파일에 인라인되므로 인터넷에 올리지 않는다.
  public/index.html   Vercel 배포용. 데이터가 들어 있지 않고,
                      로그인 후 Firestore 에서 잔액·스케줄만 받아 온다.

두 파일 모두 런웨이 로직(runway-core.js)과 스타일을 공유한다.
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.dirname(HERE)

read = lambda *p: open(os.path.join(*p), encoding='utf-8').read()

tpl_local = read(HERE, 'template.html')
tpl_web   = read(HERE, 'template_web.html')
core      = read(HERE, 'runway-core.js')
data      = read(DEST, 'data.json')

for name, tpl in (('template.html', tpl_local), ('template_web.html', tpl_web)):
    assert '/*__RUNWAY_CORE__*/' in tpl, f'{name}: 코어 자리표시자 없음'

# 스타일은 로컬 템플릿 한 곳에서만 관리하고 배포판에 주입한다
style = re.search(r'<style>\n(.*?)\n</style>', tpl_local, re.S)
assert style, 'template.html 에서 <style> 를 찾지 못함'
assert '/*__STYLE__*/' in tpl_web, 'template_web.html: 스타일 자리표시자 없음'

# </script> 가 JSON 문자열 안에 있으면 스크립트가 조기 종료되므로 이스케이프
data_js = data.replace('</', '<\\/')


def emit(tpl, path, *, with_data):
    html = tpl.replace('/*__RUNWAY_CORE__*/', core)
    html = html.replace('/*__STYLE__*/', style.group(1))
    if with_data:
        assert '__DATA__' in html, '데이터 자리표시자 없음'
        html = html.replace('__DATA__', data_js)
    else:
        assert '__DATA__' not in html, \
            f'{path}: 배포판에 데이터 자리표시자가 남아 있음 — 유출 위험'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return len(html)


local_path = os.path.join(DEST, 'dashboard.html')
web_path   = os.path.join(DEST, 'public', 'index.html')
n1 = emit(tpl_local, local_path, with_data=True)
n2 = emit(tpl_web,   web_path,   with_data=False)

# 배포판에 민감 데이터가 섞여 들어가지 않았는지 확인한다
web_html = read(web_path)
leaks = []
for probe in ('거래기록사항', '임차인', '하나캐피탈', '계좌번호', 'balance_trend', '"tx"'):
    if probe in web_html:
        leaks.append(probe)
if leaks:
    sys.exit(f'중단: 배포판에 데이터가 섞였습니다 -> {leaks}')

print(f'로컬  {local_path}  {n1:,}자')
print(f'배포  {web_path}  {n2:,}자  (데이터 없음 확인)')
