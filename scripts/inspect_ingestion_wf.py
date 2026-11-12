import json

with open('workflows/ingestion_firewall.json', 'r', encoding='utf-8') as f:
    wf = json.load(f)

print(f"Total nodes in ingestion workflow: {len(wf['nodes'])}")
for n in wf['nodes']:
    name = n['name']
    ntype = n['type']
    print(f"\n--- Node: {name} ({ntype}) ---")
    params = n.get('parameters', {})
    if 'file' in name.lower() or 'read' in name.lower():
        print(f"  Parameters: {params}")
    if 'postgres' in ntype:
        print(f"  Operation: {params.get('operation')}")
        print(f"  Query: {params.get('query')}")
        print(f"  QueryReplacement: {params.get('options', {}).get('queryReplacement')}")
    if 'split' in ntype.lower():
        print(f"  Batch size: {params.get('batchSize')}")
    if 'code' in ntype.lower():
        code = params.get('jsCode', '')
        lines = code.split('\n')
        print(f"  Code snippet (first 5 lines):\n    " + '\n    '.join(lines[:5]))

print("\n--- DAG Connections ---")
for src, targets in wf['connections'].items():
    print(f"  {src} -> {targets}")
