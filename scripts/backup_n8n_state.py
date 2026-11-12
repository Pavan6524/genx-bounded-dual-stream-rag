import subprocess
import json
import os
from datetime import datetime

def backup_n8n_state():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"workflows/backups/n8n_state_backup_pre_stage6_2a_{timestamp}.json"
    os.makedirs("workflows/backups", exist_ok=True)
    
    cmd = ['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', '--all']
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    stdout = res.stdout.strip()
    idx = stdout.find('[')
    assert idx != -1, "No JSON array found in export:workflow output"
    
    decoder = json.JSONDecoder()
    workflows, _ = decoder.raw_decode(stdout[idx:])
    
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(workflows, f, indent=2)
        
    print(f"PASS: Backed up {len(workflows)} workflow(s) to {backup_file}")
    
    # Also verify the existing runtime ingestion workflow is intact in backup
    ingestion_wf = next((wf for wf in workflows if wf.get('id') == 'IlBw4RRELuh02Akm'), None)
    assert ingestion_wf is not None, "Workflow IlBw4RRELuh02Akm not found in backup!"
    print(f"PASS: Verified runtime ingestion workflow '{ingestion_wf.get('name')}' (ID: {ingestion_wf.get('id')}) with {len(ingestion_wf.get('nodes', []))} nodes preserved.")
    return backup_file

if __name__ == '__main__':
    backup_n8n_state()
