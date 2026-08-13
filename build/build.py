# -*- coding: utf-8 -*-
"""template.html + data.json -> dashboard.html (단일 파일, 외부 의존 없음)"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = r'C:\Users\SCHOOL28\Documents\claude\2. runway'

tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
data = open(os.path.join(DEST, 'data.json'), encoding='utf-8').read()

assert '__DATA__' in tpl, 'placeholder 없음'
# </script> 가 JSON 문자열 안에 있으면 스크립트가 조기 종료되므로 이스케이프
html = tpl.replace('__DATA__', data.replace('</', '<\\/'))

out = os.path.join(DEST, 'dashboard.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('생성:', out, f'{os.path.getsize(out):,} bytes')
