# -*- coding: utf-8 -*-
"""은행 거래내역 3개 계좌 통합 분석 -> data.json"""
import pandas as pd, json, re, sys, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\SCHOOL28\Documents\claude\2. runway\1. 은행 거래내역 데이터'

FILES = [
    ('NH농협 (계좌1)', '352-2019-****-**', '202605-202607_NH농협_은행_거래내역_계좌1_강의용.xlsx', 'nh', 16386),
    ('NH농협 (계좌2)', '352-1877-****-**', '202605-202607_NH농협_은행_거래내역_계좌2_강의용.xlsx', 'nh', 20377),
    ('우리은행',       '1002-938-******',  '202605-202607_우리_은행_거래내역_강의용.xlsx',        'woori', 124919),
]

rows = []
declared = {}   # 계좌 -> (신고 출금합계, 신고 입금합계)
for acct, num, fn, kind, opening in FILES:
    df = pd.read_excel(os.path.join(BASE, fn), header=None)
    # 헤더 행 찾기
    hdr = df.index[df[0].astype(str).str.strip().isin(['순번', 'No.'])][0]
    body = df.iloc[hdr + 1:].copy()
    tot = body[body[0].astype(str).str.strip() == '합계']
    if len(tot):
        t = tot.iloc[0]
        declared[acct] = (int(t[2]), int(t[3])) if kind == 'nh' else (int(t[4]), int(t[5]))
    body = body[~body[0].astype(str).str.strip().isin(['합계', 'nan'])]
    seq = []
    for _, r in body.iterrows():
        raw_dt = str(r[1]).strip()
        m = re.match(r'(\d{4})[/.](\d{2})[/.](\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?', raw_dt)
        if not m:
            continue
        y, mo, d, hh, mm, ss = m.groups()
        ts = f'{y}-{mo}-{d} {hh}:{mm}:{ss or "00"}'
        if kind == 'nh':
            out_, in_, bal = int(r[2]), int(r[3]), int(r[4])
            desc, memo = str(r[5]).strip(), ('' if pd.isna(r[6]) else str(r[6]).strip())
        else:
            desc, memo = str(r[2]).strip(), str(r[3]).strip()
            out_, in_, bal = int(r[4]), int(r[5]), int(r[6])
        rec = dict(account=acct, acct_no=num, ts=ts, date=f'{y}-{mo}-{d}',
                   month=f'{y}-{mo}', desc=desc, memo=memo,
                   out=out_, inn=in_, balance=bal, seq=int(r[0]), missing=False)
        rows.append(rec); seq.append(rec)

    # ── 누락 순번 복원 ────────────────────────────────────────────────
    # 명세는 순번 오름차순 = 시간 내림차순. 거래 i는 거래 i+1 직후에 발생하므로
    #   잔액후(i+1) == 잔액전(i) = 잔액후(i) + 출금(i) - 입금(i)
    # 순번이 건너뛴 구간은 이 연속성으로 순증감액을 역산한다.
    for a, b in zip(seq, seq[1:]):
        gap = b['seq'] - a['seq']
        if gap <= 1:
            continue
        bal_before_a = a['balance'] + a['out'] - a['inn']
        net = bal_before_a - b['balance']          # 누락 구간 전체의 순증감
        for k in range(1, gap):
            n = net if k == 1 else 0               # 복수 누락 시 첫 건에 합산
            rows.append(dict(account=acct, acct_no=num, ts=b['ts'], date=b['date'],
                             month=b['month'], desc='(원본 누락)', memo='미상',
                             out=max(0, -n), inn=max(0, n), balance=bal_before_a,
                             seq=a['seq'] + k, missing=True))

# ── 계좌 간 내부이체 판정 ──────────────────────────────────────────────
def is_internal(t):
    if t['account'].startswith('우리'):
        if t['memo'] == '그여자' and t['inn'] > 0:      # 농협 -> 우리
            return '농협 → 우리'
        if t['memo'] == '농협그여자' and t['out'] > 0:  # 우리 -> 농협
            return '우리 → 농협'
    else:
        if t['memo'] == '그여자':
            if t['desc'] in ('폰우리은행',):  return '우리 → 농협'
            if t['desc'] in ('S-우리은행',):  return '농협 → 우리'
            if t['desc'] == '스마트당행':     return '농협 ↔ 농협'
    return None

# ── 카테고리 분류 ─────────────────────────────────────────────────────
#  (정규식, 카테고리, 설명, 대분류)
INCOME = [
    (r'임차인|새롬부동산|최동현',      '임대수입',    '건물 임대료 · 보증금',   '운영수입'),
    (r'그남자',                        '배우자 이체', '배우자 계좌에서 입금',   '가족지원'),
    (r'마루컴퍼니|윤재호',             '사업수입',    '외부 거래처 입금',       '운영수입'),
    (r'아동수당|유가보조|정부지원',    '정부지원금',  '아동수당 · 유가보조금',  '운영수입'),
    (r'우리카드 대출|대출금입금',      '대출 실행',   '신규 대출금 입금',       '재무활동'),
    (r'예금결산이자|예금이자',         '이자수입',    '예금 이자',              '운영수입'),
]
EXPENSE = [
    (r'대출원리금|대출금이자|대출일부이|원리금상환|보험약관대출이자',
                                       '대출 원리금·이자', '주택·사업자 대출 상환', '금융비용'),
    (r'하나캐피탈',                    '캐피탈 상환',  '하나캐피탈 정기 상환',   '금융비용'),
    (r'NH카드대금|현대카드|우리카드결제대금',
                                       '카드대금',     '신용카드 결제',          '운영지출'),
    (r'손해보험료|생명보험료|화재보험료', '보험료',    '손해 · 생명 · 화재보험', '운영지출'),
    (r'국세|지방소득세|지방세',        '세금',         '국세 · 지방세',          '운영지출'),
    (r'전기요금|상하수도',             '공과금',       '전기 · 상하수도',        '운영지출'),
    (r'청약',                          '저축·청약',    '청약저축 자동이체',      '운영지출'),
    (r'도어락',                        '시설유지비',   '건물 유지보수',          '운영지출'),
    (r'국민그여자|카카그남자|국민보험금', '타행 계좌 이체', '본인 · 가족 타행 계좌 송금', '재무활동'),
    (r'당근페이',                      '생활비',       '간편결제 · 생활 지출',   '운영지출'),
]

def classify(t):
    key = f"{t['memo']} {t['desc']}"
    table = INCOME if t['inn'] > 0 else EXPENSE
    for pat, cat, note, major in table:
        if re.search(pat, key):
            return cat, note, major
    return '기타', '분류되지 않은 거래', '기타'

tx = []
for t in rows:
    itype = is_internal(t)
    flow = '수입' if t['inn'] > 0 else '지출'
    amount = t['inn'] if t['inn'] > 0 else t['out']
    if t['missing']:
        cat, note, major = '미상 (원본 누락)', '명세서에서 순번이 빠진 거래 · 잔액으로 금액만 복원', '미상'
    elif itype:
        cat, note, major, flow = '계좌 간 이체', itype, '내부이체', '내부이체'
    else:
        cat, note, major = classify(t)
    tx.append(dict(account=t['account'], ts=t['ts'], date=t['date'], month=t['month'],
                   desc=t['desc'], memo=t['memo'], amount=amount, flow=flow,
                   category=cat, note=note, major=major, balance=t['balance'],
                   missing=t['missing']))

tx.sort(key=lambda x: x['ts'])

# ── 집계 ──────────────────────────────────────────────────────────────
months = sorted({t['month'] for t in tx})
def agg(flow):
    d = {}
    for t in tx:
        if t['flow'] != flow: continue
        c = d.setdefault(t['category'], dict(category=t['category'], major=t['major'],
                                             note=t['note'], total=0, count=0,
                                             months={m: 0 for m in months}))
        c['total'] += t['amount']; c['count'] += 1; c['months'][t['month']] += t['amount']
    return sorted(d.values(), key=lambda x: -x['total'])

income, expense = agg('수입'), agg('지출')
internal_total = sum(t['amount'] for t in tx if t['flow'] == '내부이체')
ti, te = sum(c['total'] for c in income), sum(c['total'] for c in expense)

S = lambda f: sum(t['amount'] for t in tx if f(t))
monthly = []
for m in months:
    inm  = S(lambda t: t['month'] == m and t['flow'] == '수입')
    exm  = S(lambda t: t['month'] == m and t['flow'] == '지출')
    monthly.append(dict(
        month=m, income=inm, expense=exm, net=inm - exm,
        internal=S(lambda t: t['month'] == m and t['flow'] == '내부이체'),
        op_income=S(lambda t: t['month'] == m and t['major'] == '운영수입'),
        family=S(lambda t: t['month'] == m and t['major'] == '가족지원'),
        fin_in=S(lambda t: t['month'] == m and t['major'] == '재무활동' and t['flow'] == '수입'),
        op_expense=S(lambda t: t['month'] == m and t['major'] == '운영지출'),
        fin_cost=S(lambda t: t['month'] == m and t['major'] == '금융비용'),
        fin_out=S(lambda t: t['month'] == m and t['major'] == '재무활동' and t['flow'] == '지출'),
    ))

# 대분류 요약
majors = []
for name, flow in [('운영수입', '수입'), ('가족지원', '수입'), ('재무활동', '수입'),
                   ('운영지출', '지출'), ('금융비용', '지출'), ('재무활동', '지출')]:
    majors.append(dict(name=name, flow=flow,
                       total=S(lambda t: t['major'] == name and t['flow'] == flow),
                       count=len([t for t in tx if t['major'] == name and t['flow'] == flow])))

# 계좌별 요약
accounts = []
for acct, num, fn, kind, opening in FILES:
    at = [t for t in tx if t['account'] == acct]
    accounts.append(dict(name=acct, no=num, opening=opening, count=len(at),
                         inflow=sum(t['amount'] for t in at if t['amount'] and
                                    next(r for r in rows if r['ts'] == t['ts'] and r['account'] == acct)['inn'] > 0),
                         outflow=0, closing=at[-1]['balance'] if at else opening))
for a, (acct, *_ ) in zip(accounts, FILES):
    src = [r for r in rows if r['account'] == acct]
    a['inflow'] = sum(r['inn'] for r in src)
    a['outflow'] = sum(r['out'] for r in src)

# 잔액 추이 (계좌별 일자별 마지막 잔액) + 합산
bal_series = {}
for acct, *_ in FILES:
    ser = {}
    for r in sorted([r for r in rows if r['account'] == acct], key=lambda x: x['ts']):
        ser[r['date']] = r['balance']
    bal_series[acct] = ser
all_dates = sorted({r['date'] for r in rows})
balance_trend = []
last = {a: op for (a, _, _, _, op) in FILES}
for d in all_dates:
    for a in last:
        if d in bal_series[a]: last[a] = bal_series[a][d]
    balance_trend.append(dict(date=d, total=sum(last.values()), **{a: last[a] for a in last}))

# 고정비 (매월 반복 발생 항목)
fixed = {}
for t in tx:
    if t['flow'] != '지출' or t['missing']: continue
    k = t['memo'] or t['desc']
    f = fixed.setdefault(k, dict(name=k, category=t['category'], months=set(), total=0, count=0))
    f['months'].add(t['month']); f['total'] += t['amount']; f['count'] += 1
fixed_costs = sorted([dict(name=v['name'], category=v['category'], months=len(v['months']),
                           total=v['total'], count=v['count'], avg=round(v['total'] / len(v['months'])))
                      for v in fixed.values() if len(v['months']) == len(months)],
                     key=lambda x: -x['total'])

# 상위 거래
top_tx = sorted([t for t in tx if t['flow'] != '내부이체'], key=lambda x: -x['amount'])[:12]

# ── 반복 거래 스케줄 (런웨이 예측용) ──────────────────────────────────
#   결제일 = 월별 첫 발생일의 중앙값,  금액 = 월 합계의 평균
#   한 달에 여러 건으로 쪼개져 나가는 대출이자 등은 월 단위로 먼저 합산한다.
import statistics
from datetime import date, timedelta

def cycle_key(ds):
    """청구 주기 버킷. 1일 결제분은 전월 주기가 늦게 빠져나간 것이므로
       날짜를 2일 당겨서 월에 배정한다 (6/1 결제 = 5월분)."""
    y, m, d = map(int, ds.split('-'))
    return (date(y, m, d) - timedelta(days=2)).strftime('%Y-%m')

def norm_name(n):
    """'아동수당5월', '유가보조3월'처럼 월 이름이 붙는 항목을 한 항목으로 묶는다."""
    return re.sub(r'\s*\d{1,2}월$', '', n).strip() or n

def build_schedule():
    g = {}
    for t in tx:
        if t['flow'] == '내부이체' or t['missing']:
            continue
        nm = norm_name(t['memo'] or t['desc'])
        k = (t['flow'], nm)
        e = g.setdefault(k, dict(name=nm, flow=t['flow'],
                                 category=t['category'], major=t['major'],
                                 account=t['account'], months={}))
        ck = cycle_key(t['date'])
        m = e['months'].setdefault(ck, dict(total=0, day=31, n=0))
        m['total'] += t['amount']; m['n'] += 1
        m['day'] = min(m['day'], int(t['date'][8:]))

    sched, irregular = [], []
    for e in g.values():
        mv = dict(sorted(e['months'].items()))
        totals = [v['total'] for v in mv.values()]
        days = [v['day'] for v in mv.values()]
        row = dict(name=e['name'], flow=e['flow'], category=e['category'], major=e['major'],
                   account=e['account'], n_months=len(mv),
                   day=int(statistics.median(days)),
                   amount=round(sum(totals) / len(totals)),
                   lo=min(totals), hi=max(totals),
                   last=totals[-1], total=sum(totals),
                   # 최저/최고가 3배 이상 벌어지면 '변동 큼'으로 표시한다
                   volatile=(min(totals) > 0 and max(totals) / min(totals) >= 3),
                   by_month={m: v['total'] for m, v in mv.items()})
        (sched if len(mv) >= 2 else irregular).append(row)

    sched.sort(key=lambda r: (r['flow'] != '지출', r['day']))
    irregular.sort(key=lambda r: -r['total'])
    return sched, irregular

schedule, irregular = build_schedule()

# ── 정합성 검증: 파싱 결과 vs 명세서 '합계' 행 vs 잔액 연속성 ────────────
recon = dict(accounts=[], missing=[t for t in tx if t['missing']])
for acct, num, fn, kind, opening in FILES:
    src = [r for r in rows if r['account'] == acct]
    d_out, d_in = declared[acct]
    closing = sorted(src, key=lambda x: x['ts'])[-1]['balance']
    recon['accounts'].append(dict(
        name=acct, opening=opening, declared_in=d_in, declared_out=d_out,
        parsed_in=sum(r['inn'] for r in src), parsed_out=sum(r['out'] for r in src),
        closing=closing, expected=opening + d_in - d_out,
        n_missing=len([r for r in src if r['missing']]),
        ok=(sum(r['inn'] for r in src) == d_in and sum(r['out'] for r in src) == d_out
            and opening + d_in - d_out == closing)))
recon['all_ok'] = all(a['ok'] for a in recon['accounts'])

fin_cost   = S(lambda t: t['major'] == '금융비용')
op_income  = S(lambda t: t['major'] == '운영수입')
op_expense = S(lambda t: t['major'] == '운영지출')
family     = S(lambda t: t['major'] == '가족지원')
rent = next((c['total'] for c in income if c['category'] == '임대수입'), 0)

out = dict(
    meta=dict(period='2026-05-01 ~ 2026-07-31', months=months, accounts=len(FILES),
              tx_count=len(tx), generated=datetime.now().strftime('%Y-%m-%d')),
    kpi=dict(income=ti, expense=te, net=ti - te, internal=internal_total,
             fin_cost=fin_cost, op_income=op_income, op_expense=op_expense, family=family,
             op_net=op_income - op_expense - fin_cost,
             fin_ratio=round(fin_cost / op_income * 100, 1) if op_income else 0,
             rent=rent, rent_vs_fin=rent - fin_cost,
             months=len(months),
             opening=sum(f[4] for f in FILES),
             closing=balance_trend[-1]['total'] if balance_trend else 0),
    majors=majors, income=income, expense=expense, monthly=monthly,
    accounts_summary=accounts, balance_trend=balance_trend,
    fixed_costs=fixed_costs, top_tx=top_tx, tx=tx,
    recon=recon, schedule=schedule, irregular=irregular,
    start=dict(date='2026-08-01',
               balances={a['name']: a['closing'] for a in accounts},
               as_of=max(t['date'] for t in tx)),
)

DEST = r'C:\Users\SCHOOL28\Documents\claude\2. runway'
with open(os.path.join(DEST, 'data.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

print('거래 건수:', len(tx))
print('총수입 %s / 총지출 %s / 순현금흐름 %s' % (f'{ti:,}', f'{te:,}', f'{ti-te:,}'))
print('계좌간 내부이체:', f'{internal_total:,}')
print('운영수입 %s / 운영지출 %s / 금융비용 %s / 가족지원 %s' %
      (f'{op_income:,}', f'{op_expense:,}', f'{fin_cost:,}', f'{family:,}'))
print('금융비용/운영수입 = %s%%' % out['kpi']['fin_ratio'])
print('\n[수입]'); [print(' ', c['major'], c['category'], f"{c['total']:,}", c['count']) for c in income]
print('\n[지출]'); [print(' ', c['major'], c['category'], f"{c['total']:,}", c['count']) for c in expense]
print('\n[미분류]'); [print(' ', t['ts'], t['desc'], t['memo'], t['amount']) for t in tx if t['category'] == '기타']
print('\n[정합성 검증]  전체 통과:', recon['all_ok'])
for a in recon['accounts']:
    print(f"  {a['name']:16s} 입금 {a['parsed_in']:>12,}/{a['declared_in']:>12,}  "
          f"출금 {a['parsed_out']:>12,}/{a['declared_out']:>12,}  "
          f"기말 {a['closing']:>10,} (기대 {a['expected']:>10,})  누락복원 {a['n_missing']}건  {'OK' if a['ok'] else 'NG'}")
print('\n[복원된 누락 거래]')
for t in recon['missing']:
    print(f"  {t['ts']}  {t['account']}  {'입금' if t['flow']=='수입' else '출금'} {t['amount']:>10,}")
print('\n[고정비]'); [print(' ', f["name"], f'{f["avg"]:,}/월') for f in fixed_costs]
print('\n[반복 스케줄]  (결제일 = 월별 첫 발생일 중앙값, 금액 = 월 합계 평균)')
for r in schedule:
    print(f"  {r['day']:>2d}일 {r['flow']:2s} {r['name'][:16]:16s} {r['amount']:>10,}"
          f"  ({r['n_months']}/3개월, {r['lo']:,}~{r['hi']:,})  {r['category']}")
out_m = sum(r['amount'] for r in schedule if r['flow'] == '지출')
in_m  = sum(r['amount'] for r in schedule if r['flow'] == '수입')
print(f"  → 월 정기지출 {out_m:,} / 월 정기수입 {in_m:,} / 차액 {in_m-out_m:,}")
print('\n[비정기 (1회성, 예측 제외)]')
for r in irregular[:10]:
    print(f"  {r['flow']:2s} {r['name'][:18]:18s} {r['total']:>12,}  {r['category']}")
