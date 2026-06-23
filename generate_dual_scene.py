"""Upload two stills and generate Seedance 2.0 videos for both."""
import sys, os, time, json, subprocess

sys.path.insert(0, "D:/Projects2026/lovart-skill/skills/lovart-skill")
os.chdir("D:/Projects2026/lovart-skill/skills/lovart-skill")

env_path = r'C:\Users\joyne\AppData\Local\hermes\.env'
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        k, _, v = line.partition('=')
        os.environ[k.strip()] = v.strip()

from agent_skill import AgentSkill

c = AgentSkill(
    base_url='https://lgw.lovart.ai',
    access_key=os.environ['LOVART_ACCESS_KEY'],
    secret_key=os.environ['LOVART_SECRET_KEY']
)

# ── Still paths ──
scene_a = r"D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-source-kemetopolis-market.png"
scene_b = r"D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-source-archive-vault.png"

# ── Upload both ──
print("=== UPLOADING STILLS ===")
url_a = c.upload_file(local_path=scene_a)
print(f"Scene A (Market): {url_a}")
url_b = c.upload_file(local_path=scene_b)
print(f"Scene B (Archive): {url_b}")

# ── Seedance 2.0 prompts ──
prompt_a = (
    "A wide cinematic shot of a Kemetopolis transit market at golden hour. "
    "Slow, steady micro-drift. The camera holds the composition with a barely perceptible "
    "handheld breath. Environmental motion: dust drifts in warm light, people in the market "
    "move casually, holographic glyphs pulse gently in the upper sky, "
    "jade civic lanterns breathe slowly. Warm amber light, teal bounce, "
    "deep indigo shadows. Cinematic, photorealistic, continuous motion."
)

prompt_b = (
    "A wide cinematic interior shot of a Kemetopolis archive vault. "
    "Slow, steady micro-drift. The camera holds the composition with a gentle settling motion. "
    "Environmental motion: dust motes float in warm amber lamplight, "
    "teal holographic catalog data streams pulse softly above the shelves, "
    "the archivist's sleeve shifts slightly as they reach for a scroll, "
    "warm amber light from the desk lamp, teal data glow, "
    "deep warm shadows in the shelving aisles. Cinematic, photorealistic, continuous motion."
)

def run_seedance(prompt, image_url, label):
    """Full Seedance 2.0 generation flow."""
    print(f"\n=== {label}: Starting Seedance 2.0 generation ===")
    pid = c.create_project()
    print(f"  Project: {pid}")
    tid = c.send(
        prompt=prompt,
        project_id=pid,
        attachments=[image_url],
        prefer_models={'VIDEO': ['generate_video_seedance_v2_0']}
    )
    print(f"  Thread: {tid}")

    # Wait for confirmation
    print(f"  Waiting for confirmation gate...")
    time.sleep(8)
    confirmed = False
    for i in range(30):
        try:
            rr = c.get_result(thread_id=tid)
            pc = rr.get('pending_confirmation')
            if pc:
                cost = pc['estimated_cost']
                dollars = cost * 0.0045
                print(f"  Cost: {cost} credits (~${dollars:.2f})")
                c.confirm(thread_id=tid)
                confirmed = True
                print(f"  Confirmed!")
                break
            sr = c.get_status(thread_id=tid)
            print(f"  [{i+1}] {sr.get('final_status') or sr.get('status', '?')}")
        except Exception as e:
            print(f"  [{i+1}] {e}")
        time.sleep(4)

    if not confirmed:
        print(f"  WARNING: No confirmation gate for {label}")
        return None

    # Poll for completion
    print(f"  Rendering...")
    while True:
        sr = c.get_status(thread_id=tid)
        status = sr.get('final_status') or sr.get('status', '')
        print(f"    Status: {status}")
        if status in ('completed', 'done'):
            break
        if status in ('failed', 'error'):
            print(f"  FAILED: {sr}")
            return None
        time.sleep(5)

    # Get download URL
    result = c.get_result(thread_id=tid)
    dl_url = None
    for item in result.get('items', []):
        for art in item.get('artifacts', []):
            u = art.get('content', '') or art.get('url', '')
            if u and 'mp4' in u.lower():
                dl_url = u
                break
        if dl_url:
            break

    if not dl_url:
        # Try any artifact
        for item in result.get('items', []):
            for art in item.get('artifacts', []):
                u = art.get('content', '') or art.get('url', '')
                if u:
                    dl_url = u
                    break
            if dl_url:
                break

    if dl_url:
        out = f"D:/Projects2026/mjm-web/seedance_{label.lower().replace(' ','_')}.mp4"
        print(f"  Downloading to {out}...")
        subprocess.run(['curl', '-L', '-o', out, dl_url], check=True)
        size = os.path.getsize(out)
        print(f"  Done! {size} bytes")
        return out
    else:
        print(f"  No download URL found for {label}")
        print(json.dumps(result, indent=2)[:1000])
        return None

# Run Scene A first, wait, then Scene B (sequential to avoid rate issues)
result_a = run_seedance(prompt_a, url_a, "SCENE_A_MARKET")
result_b = run_seedance(prompt_b, url_b, "SCENE_B_ARCHIVE")

print(f"\n{'='*40}")
print(f"SCENE A (Market): {result_a or 'FAILED'}")
print(f"SCENE B (Archive): {result_b or 'FAILED'}")

if result_a and result_b:
    print("\nBoth clips downloaded. Ready for FFmpeg stitch.")
