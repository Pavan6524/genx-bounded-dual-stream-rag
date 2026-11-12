import subprocess
import json

cmd = ['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', '--id=IlBw4RRELuh02Akm']
res = subprocess.run(cmd, capture_output=True, text=True, check=True)
stdout = res.stdout.strip()
idx = stdout.find('{')
if idx == -1:
    idx = stdout.find('[')

decoder = json.JSONDecoder()
json_data, end_idx = decoder.raw_decode(stdout[idx:])
if isinstance(json_data, list):
    json_data = json_data[0]

print("Keys in exported workflow:", list(json_data.keys()))
print("Project ID / Owner / Meta:")
for k in ['id', 'name', 'active', 'projectId', 'meta', 'tags', 'versionId']:
    print(f"  {k}: {json_data.get(k)}")

# Also inspect n8n database project table or user table if needed
