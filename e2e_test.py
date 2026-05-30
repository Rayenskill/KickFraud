import urllib.request
import json
import time
import sys

print('Waiting for API to boot up...')
time.sleep(2)

base = 'http://localhost:8000'
try:
    # 1. Health check
    res = urllib.request.urlopen(f'{base}/health')
    health = json.loads(res.read())
    print('✅ Health Check:', health)
    assert health['status'] == 'ok'

    # 2. List Transactions
    res = urllib.request.urlopen(f'{base}/transactions?min_score=0.4')
    txns = json.loads(res.read())
    print('✅ Transactions Load:', txns['count'], 'flagged transactions found.')
    
    if txns['count'] > 0:
        target_tid = txns['results'][0]['transaction_id']
        
        # 3. Review a transaction
        data = json.dumps({"decision": "dismiss"}).encode('utf-8')
        req = urllib.request.Request(f'{base}/review/{target_tid}', method='POST', headers={'Content-Type': 'application/json'}, data=data)
        res = urllib.request.urlopen(req)
        review_data = json.loads(res.read())
        print(f'✅ Review Transaction ({target_tid} -> dismiss):', review_data['review_status'])
        
        # 4. Undo
        req = urllib.request.Request(f'{base}/undo', method='POST')
        res = urllib.request.urlopen(req)
        undo_data = json.loads(res.read())
        print('✅ Undo Review:', undo_data['undone'])
        
    # 5. Threshold
    data = json.dumps({"fp_cost": 1, "fn_cost": 10}).encode('utf-8')
    req = urllib.request.Request(f'{base}/threshold', method='POST', headers={'Content-Type': 'application/json'}, data=data)
    res = urllib.request.urlopen(req)
    thresh_data = json.loads(res.read())
    print('✅ Threshold Adjust (fn_cost=10):', thresh_data)

    # 6. Export CSV
    res = urllib.request.urlopen(f'{base}/export')
    csv_data = res.read().decode('utf-8')
    lines = csv_data.strip().split('\n')
    print('✅ CSV Export (first 3 lines):')
    for l in lines[:3]: 
        print('  ', l[:100] + '...')

    print('\n🎉 All API E2E Tests Passed Successfully!')
except Exception as e:
    print('❌ E2E Test Failed:', e)
    sys.exit(1)
