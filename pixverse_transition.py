"""Generate a PixVerse V6 transition between the baobab day and night stills."""
import os, sys, time, json, uuid, subprocess, requests

# Load PixVerse API key
env_path = r'C:\Users\joyne\AppData\Local\hermes\.env'
api_key = None
with open(env_path) as f:
    for line in f:
        if line.startswith('PIXVERSE_API='):
            api_key = line.strip().split('=', 1)[1]
            break

if not api_key:
    print("ERROR: PIXVERSE_API not found in .env")
    sys.exit(1)

BASE = 'https://app-api.pixverse.ai'

def upload(path):
    """Upload image to PixVerse, return img_id."""
    trace_id = str(uuid.uuid4())
    headers = {'API-KEY': api_key, 'Ai-trace-id': trace_id}
    with open(path, 'rb') as f:
        r = requests.post(f'{BASE}/openapi/v2/image/upload',
                          headers=headers,
                          files={'image': (os.path.basename(path), f, 'image/png')})
    data = r.json()
    if data.get('ErrCode') != 0:
        print(f"Upload failed: {data}")
        return None
    img_id = data['Resp']['img_id']
    print(f"  Uploaded {os.path.basename(path)} -> img_id {img_id}")
    return img_id

def generate_transition(first_id, last_id):
    """Generate a transition video between two images. Returns video_id."""
    trace_id = str(uuid.uuid4())
    headers = {'API-KEY': api_key, 'Ai-trace-id': trace_id, 'Content-Type': 'application/json'}
    body = {
        'prompt': 'A single ancient baobab tree transforms from golden hour daylight to night. The daytime warm amber and coral sky dissolves into deep indigo night sky with stars. Green leaves fade as teal and jade bioluminescent veins glow along the trunk and branches. Warm golden grass becomes dark indigo earth. A soft amber light appears at the base of the tree. The tree stays centered, the composition holds perfectly still. Cinematic, smooth morph, continuous.',
        'model': 'v6',
        'duration': 8,
        'quality': '720p',
        'first_frame_img': first_id,
        'last_frame_img': last_id
    }
    r = requests.post(f'{BASE}/openapi/v2/video/transition/generate',
                      headers=headers, json=body)
    data = r.json()
    print(f"  Transition response: {json.dumps(data, indent=2)[:300]}")
    if data.get('ErrCode') != 0:
        print(f"  Generation failed: {data}")
        return None
    video_id = data['Resp']['video_id']
    print(f"  Video ID: {video_id}")
    return video_id

def poll(video_id):
    """Poll until generation completes. Returns download URL."""
    trace_id = str(uuid.uuid4())
    headers = {'API-KEY': api_key, 'Ai-trace-id': trace_id}
    print(f"  Polling for completion...")
    for i in range(120):
        r = requests.get(f'{BASE}/openapi/v2/video/result/{video_id}', headers=headers)
        data = r.json()
        status = data.get('Resp', {}).get('status', 0)
        if status == 1:
            url = data['Resp']['url']
            print(f"  Complete! URL: {url[:80]}...")
            return url
        elif status == 5:
            if i % 10 == 0:
                print(f"  [{i}] Processing...")
        elif status == 7:
            print(f"  Content moderation failed")
            return None
        elif status == 8:
            print(f"  Generation failed: {data}")
            return None
        else:
            print(f"  Status {status}: {data}")
        time.sleep(3)
    print("  Timeout")
    return None

# ── Main ──
print("=== PixVerse Baobab Transition ===\n")

print("Uploading images...")
day_id = upload(r'D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-baobab-day.png')
if not day_id: sys.exit(1)

night_id = upload(r'D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-baobab-night.png')
if not night_id: sys.exit(1)

print(f"\nGenerating transition (day -> night)...")
video_id = generate_transition(day_id, night_id)
if not video_id: sys.exit(1)

url = poll(video_id)
if not url: sys.exit(1)

# Download
out = r'D:\Projects2026\mjm-web\scroll-baobab.mp4'
print(f"\nDownloading to {out}...")
r = requests.get(url, stream=True)
with open(out, 'wb') as f:
    for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)

sz = os.path.getsize(out)
dur = subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',out],
                    capture_output=True,text=True).stdout.strip()
print(f"Saved: {sz/1024/1024:.1f}MB, {dur}s")

# Also check resolution
res = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_streams',out],
                    capture_output=True,text=True)
import json as j
d = j.loads(res.stdout)
for s in d.get('streams',[]):
    if s['codec_type']=='video':
        print(f"Resolution: {s['width']}x{s['height']}, {s['codec_name']}")
