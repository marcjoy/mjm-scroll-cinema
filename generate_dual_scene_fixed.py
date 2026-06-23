"""Regenerate both Seedance 2.0 clips with FIXED confirmation handling.
    
BUG FIXED: The old script returned None when pending_confirmation
didn't appear within the polling window. Lovart auto-confirms jobs
after a timeout, so we must KEEP POLLING even without explicit confirmation.
"""
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

scene_a = r"D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-source-kemetopolis-market.png"
scene_b = r"D:\Projects2026\Design\Lanes\MJM\Mockups\scroll-source-archive-vault.png"

print("=== UPLOADING STILLS ===")
url_a = c.upload_file(local_path=scene_a)
print(f"A: {url_a}")
url_b = c.upload_file(local_path=scene_b)
print(f"B: {url_b}")

prompt_a = (
    "A wide cinematic shot of a Kemetopolis transit market at golden hour. "
    "Slow micro-drift motion. Dust drifts, people move casually, "
    "holographic glyphs pulse gently. Warm amber light, teal bounce, "
    "deep indigo shadows. Cinematic, photorealistic, continuous motion."
)
prompt_b = (
    "A wide cinematic interior shot of a Kemetopolis archive vault. "
    "Slow micro-drift motion. Dust motes float in warm amber lamplight, "
    "teal holographic data streams pulse, an archivist reaches for a scroll. "
    "Warm amber light, teal data glow, deep shadows. "
    "Cinematic, photorealistic, continuous motion."
)

def gen(pid, prompt, url, label):
    print(f"\n=== {label}: Sending ===")
    tid = c.send(prompt=prompt, project_id=pid, attachments=[url],
                 prefer_models={'VIDEO': ['generate_video_seedance_v2_0']})
    print(f"  Thread: {tid}")

    # Wait for pending_confirmation - but DON'T return None if not found
    print(f"  Waiting for confirmation (up to 2 min)...")
    confirmed = False
    for i in range(30):
        try:
            rr = c.get_result(thread_id=tid)
            pc = rr.get('pending_confirmation')
            if pc:
                cost = pc['estimated_cost']
                dollars = cost * 0.0045
                print(f"  CONFIRMED: {cost} credits (~${dollars:.2f})")
                c.confirm(thread_id=tid)
                confirmed = True
                break
            sr = c.get_status(thread_id=tid)
            print(f"  [{i+1}] {sr.get('final_status') or sr.get('status','?')}")
        except Exception as e:
            print(f"  [{i+1}] {e}")
        time.sleep(4)

    if not confirmed:
        print(f"  No confirmation gate within window. Job may auto-confirm. Continuing to poll...")

    # Poll until completion - THIS is where the old bug was (returning None above)
    print(f"  Rendering (polling for completion)...")
    poll_count = 0
    while True:
        sr = c.get_status(thread_id=tid)
        st = sr.get('final_status') or sr.get('status', '')
        if st in ('completed', 'done'):
            print(f"  COMPLETED!")
            break
        if st in ('failed', 'error'):
            print(f"  STATUS: {st} - might be a transient state, continuing...")
        poll_count += 1
        if poll_count > 120:  # 10 minute max
            print(f"  TIMEOUT after 10 min")
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
        # Fallback: any artifact
        for item in result.get('items', []):
            for art in item.get('artifacts', []):
                u = art.get('content', '') or art.get('url', '')
                if u:
                    dl_url = u
                    break
            if dl_url:
                break

    if dl_url:
        out = f"D:/Projects2026/mjm-web/seedance_{label}.mp4"
        print(f"  Downloading to {out}...")
        subprocess.run(['curl', '-L', '-o', out, dl_url], check=True)
        sz = os.path.getsize(out)
        dur = subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',out],
                           capture_output=True, text=True).stdout.strip()
        print(f"  Saved: {sz/1024/1024:.1f}MB, {dur}s")
        return out
    else:
        print(f"  No download URL found")
        print(json.dumps(result, indent=2)[:1000])
        return None

# Run both sequentially
r_a = gen(c.create_project(), prompt_a, url_a, "market")
r_b = gen(c.create_project(), prompt_b, url_b, "archive")

print(f"\n{'='*50}")
print(f"MARKET: {r_a or 'FAILED'}")
print(f"ARCHIVE: {r_b or 'FAILED'}")

if r_a and r_b:
    print("\nBoth clips ready. Now stitching with FFmpeg xfade...")
    # Get first clip duration for offset calculation
    dur_a = float(subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',r_a],
                                capture_output=True, text=True).stdout.strip())
    offset = dur_a - 2.0  # 2s crossfade
    stitch_cmd = [
        'ffmpeg', '-y',
        '-i', r_a, '-i', r_b,
        '-filter_complex',
        f'[0:v][1:v]xfade=transition=fade:duration=2.0:offset={offset:.2f}[vout];'
        f'[0:a][1:a]acrossfade=d=2.0:c1=tri:c2=tri[aout]',
        '-map', '[vout]', '-map', '[aout]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        'D:/Projects2026/mjm-web/scroll-dual.mp4'
    ]
    subprocess.run(stitch_cmd, check=True)
    total_dur = float(subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',
                                     'D:/Projects2026/mjm-web/scroll-dual.mp4'],
                                    capture_output=True, text=True).stdout.strip())
    print(f"\nSTITCHED: D:/Projects2026/mjm-web/scroll-dual.mp4")
    print(f"Total duration: {total_dur:.2f}s")
    print("\nDone. The scroll-cinema page is ready.")
