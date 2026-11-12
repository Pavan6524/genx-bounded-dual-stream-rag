import json

with open('workflows/live_exported_test_wf.json', 'r', encoding='utf-8') as f:
    live_wf = json.load(f)

with open('workflows/ingestion_firewall_runtime_test.json', 'r', encoding='utf-8') as f:
    local_wf = json.load(f)

with open('workflows/backups/ingestion_firewall_runtime_test_pre_parse_fix.json', 'r', encoding='utf-8') as f:
    backup_wf = json.load(f)

print('=== 1. ID & NAME ===')
print('Live ID:', live_wf.get('id'), '| Local ID:', local_wf.get('id'))
print('Live Name:', live_wf.get('name'), '| Local Name:', local_wf.get('name'))

print('\n=== 2. NODE COUNT ===')
print('Live nodes:', len(live_wf['nodes']), '| Local nodes:', len(local_wf['nodes']))

print('\n=== 3. COMPARE LIVE VS LOCAL ===')
live_nodes = {n['name']: n for n in live_wf['nodes']}
local_nodes = {n['name']: n for n in local_wf['nodes']}
print('Node names set identical:', set(live_nodes.keys()) == set(local_nodes.keys()))
print('Connections identical:', live_wf['connections'] == local_wf['connections'])

live_parse = live_nodes['Parse Transcripts Array']['parameters']['jsCode']
local_parse = local_nodes['Parse Transcripts Array']['parameters']['jsCode']
print('Parse Transcripts Array jsCode matches local:', live_parse.strip() == local_parse.strip())

print('\n=== 4. COMPARE LIVE VS PRE-FIX BACKUP ===')
backup_nodes = {n['name']: n for n in backup_wf['nodes']}
diff_nodes = []
for name, b_node in backup_nodes.items():
    l_node = live_nodes.get(name)
    if not l_node:
        diff_nodes.append((name, 'missing in live'))
        continue
    if b_node.get('parameters') != l_node.get('parameters'):
        diff_nodes.append((name, 'parameters differ'))

print('Nodes differing in parameters from backup:', diff_nodes)

print('\n=== 5. SPLIT IN BATCHES CONNECTIONS IN LIVE ===')
for sib in ['Process Sessions Sequentially', 'Sequential Framework Loop', 'Sequential Voice Loop']:
    conns = live_wf['connections'].get(sib, {})
    print(f'{sib}:')
    main_conns = conns.get('main', [])
    for idx, targets in enumerate(main_conns):
        target_names = [t['node'] for t in targets]
        print(f'  output[{idx}] -> {target_names}')

print('\n=== 6. POSTGRES CREDENTIALS & NODES IN LIVE ===')
for n in ['Atomic Vault Replacement Function', 'Transactional Archive Rejected']:
    node = live_nodes.get(n)
    if node:
        print(f"{n}: type={node.get('type')}, credentials={node.get('credentials')}")
