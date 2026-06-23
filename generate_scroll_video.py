"""Generate Kling 3.0 video from scroll source still via Lovart API."""
import sys, os, time, json
sys.path.insert(0, "D:/Projects2026/lovart-skill/skills/lovart-skill")
os.chdir("D:/Projects2026/lovart-skill/skills/lovart-skill")

from agent_skill import AgentSkill

# Load env
env_path = r'C:\Users\joyne\AppData\Local\hermes\.env'
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        k, _, v = line.partition('=')
        os.environ[k.strip()] = v.strip()

c = AgentSkill(
    base_url='https://lgw.lovart.ai',
    access_key=os.environ.get('LOVART_ACCESS_KEY', ''),
    secret_key=os.environ.get('LOVART_SECRET_KEY', '')
)

# Step 1: Upload source image
source_path = r"D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-source-kemetopolis-market.png"
print("Uploading source image...")
url = c.upload_file(local_path=source_path)
print(f"Uploaded to: {url}")

# Step 2: Create project and send video generation
print("Sending Kling 3.0 video generation...")
PROMPT = (
    "A wide cinematic shot of a Kemetopolis transit market at golden hour. "
    "9:16 portrait aspect ratio for social video. "
    "Micro-drift motion: The camera holds the composition with a subtle handheld breath, "
    "barely perceptible micro-drift and gentle settling, as if the camera operator is standing and breathing. "
    "No push-in, no zoom, no dolly, no dramatic camera movement. "
    "Environmental motion: dust motes drift slowly in the warm amber light. "
    "Holographic glyphs pulse softly in the upper sky. "
    "People in the midground market move casually, shifting weight, adjusting stalls. "
    "Jade civic lanterns emit a slow breathing glow. "
    "A single floating transit hologram rotates gently in the midground. "
    "The light holds steady -- warm amber from the sun, teal bounce from the lanterns, "
    "deep indigo shadows in the colonnades. "
    "Cinematic, photorealistic, continuous motion. "
    "The frame holds the full composition for the entire clip -- no cropping, no drift off the scene."
)

pid = c.create_project()
print(f"Project ID: {pid}")

tid = c.send(
    prompt=PROMPT,
    project_id=pid,
    attachments=[url],
    prefer_models={'VIDEO': ['generate_video_kling_v3']}
)
print(f"Thread ID: {tid}")

# Step 3: Wait for pending_confirmation
print("Waiting for pending_confirmation...")
time.sleep(5)
confirmed = False
for i in range(15):
    try:
        rr = c.get_result(thread_id=tid)
        pc = rr.get('pending_confirmation')
        if pc:
            cost = pc['estimated_cost']
            dollars = cost * 0.0045
            print(f"Cost: {cost} credits (~${dollars:.2f})")
            print(f"Pending confirmation: {json.dumps(pc, indent=2)}")
            c.confirm(thread_id=tid)
            confirmed = True
            print("Confirmed.")
            break
        sr = c.get_status(thread_id=tid)
        print(f"  Status check {i+1}: {sr.get('final_status') or sr.get('status', 'unknown')}")
    except Exception as e:
        print(f"  Check {i+1}: {e}")
    time.sleep(3)

if not confirmed:
    print("WARNING: Could not get pending_confirmation. Check Lovart dashboard.")
    print(f"Thread ID for manual check: {tid}")

# Step 4: Poll until completed
print("\nPolling for completion...")
while True:
    sr = c.get_status(thread_id=tid)
    status = sr.get('final_status') or sr.get('status', '')
    print(f"  Status: {status}")
    if status in ('completed', 'done'):
        break
    if status in ('failed', 'error'):
        print(f"FAILED: {sr}")
        sys.exit(1)
    time.sleep(5)

# Step 5: Extract download URL
result = c.get_result(thread_id=tid)
print(f"\nFull result keys: {list(result.keys())}")

dl_url = None
for item in result.get('items', []):
    for art in item.get('artifacts', []):
        u = art.get('content', '') or art.get('url', '')
        if u and ('mp4' in u.lower() or 'video' in u.lower()):
            dl_url = u
            print(f"Found video artifact: {u}")
            break
    if dl_url:
        break

if not dl_url:
    # Dump all artifacts for inspection
    print("No MP4 found in artifacts. Dumping result...")
    print(json.dumps(result, indent=2)[:2000])
else:
    out_path = r"D:\Projects2026\mjm-web\scroll-video.mp4"
    print(f"\nDownloading to {out_path}...")
    import subprocess
    subprocess.run([
        'curl', '-L', '-o', out_path, dl_url
    ], check=True)
    print(f"Done! Video saved to {out_path}")
