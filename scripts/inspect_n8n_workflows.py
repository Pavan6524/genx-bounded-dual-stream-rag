import subprocess
import json

def inspect_n8n():
    cmd = ['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', '--all']
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    # n8n output may have leading logs or warnings, find the JSON array
    stdout = res.stdout.strip()
    idx = stdout.find('[')
    if idx == -1:
        print("No JSON array found in output:", stdout[:300])
        return []
    
    json_text = stdout[idx:]
    workflows = json.loads(json_text)
    print(f"Total workflows exported from n8n: {len(workflows)}")
    for wf in workflows:
        print(f"ID: {wf.get('id')} | Name: '{wf.get('name')}' | Active: {wf.get('active')} | Nodes: {len(wf.get('nodes', []))}")
        
    return workflows

if __name__ == '__main__':
    inspect_n8n()
