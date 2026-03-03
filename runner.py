import os, time, json, re
import httpx

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
QUEUE_CHANNEL_ID = os.environ["QUEUE_CHANNEL_ID"]  # e.g. C07ABC1234
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "20"))

HEADERS = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

def slack_api(method: str, payload: dict):
    r = httpx.post(f"https://slack.com/api/{method}", headers=HEADERS, json=payload, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data}")
    return data

def fetch_recent_messages(limit=50):
    return slack_api("conversations.history", {"channel": QUEUE_CHANNEL_ID, "limit": limit}).get("messages", [])

def has_done_reaction(msg: dict) -> bool:
    for rxn in msg.get("reactions", []) or []:
        if rxn.get("name") == "white_check_mark":
            return True
    return False

def extract_request(msg_text: str):
    if "LP_REQUEST NEW" not in msg_text:
        return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", msg_text, re.S)
    if not m:
        return None
    return json.loads(m.group(1))

def build_prompt(req: dict) -> str:
    return f"""You are the SEM Landing Page Agent.

Create a landing page outline + first-draft copy for:
Search term (exact): "{req.get('search_term')}"
Primary CTA: "{req.get('primary_cta')}"
Intent: "{req.get('intent','')}"
Audience persona: "{req.get('audience_persona','')}"
Offer: "{req.get('offer','')}"
Must include: "{req.get('must_include','')}"
Must not say: "{req.get('must_not_say','')}"

Requirements:
- Title tag includes the search term verbatim.
- H1 includes the search term verbatim.
- Search term appears within first 100 words and at least one H2.
- CTA above the fold and repeated.
- Scannable formatting + bullets.
- 3–6 FAQs.
- Visual plan with placement notes.

Output sections:
1) Angle (2 sentences)
2) SEO: title tag, meta description, slug
3) Outline (H1/H2s with bullets)
4) Draft hero + 3 key sections
5) FAQs
6) Visual plan
"""

def reply_in_thread(channel: str, thread_ts: str, text: str):
    slack_api("chat.postMessage", {"channel": channel, "thread_ts": thread_ts, "text": text})  # thread_ts replies :contentReference[oaicite:6]{index=6}

def add_done_reaction(channel: str, ts: str):
    slack_api("reactions.add", {"channel": channel, "timestamp": ts, "name": "white_check_mark"})

def main():
    print("Runner started. Watching queue channel:", QUEUE_CHANNEL_ID)
    while True:
        try:
            msgs = fetch_recent_messages()
            for msg in msgs:
                if has_done_reaction(msg):
                    continue
                req = extract_request(msg.get("text",""))
                if not req:
                    continue

                ts = msg["ts"]
                print("\n=== NEW REQUEST ===")
                print("Request ID:", req.get("request_id"))
                print("\n--- Paste this into Claude Project ---\n")
                print(build_prompt(req))
                print("\n--- Paste Claude output below, then Ctrl+D ---\n")

                import sys
                output = sys.stdin.read().strip()
                if not output:
                    print("No output pasted; skipping.")
                    continue

                # Post result in thread (truncate for Slack)
                max_len = 3500
                out = output if len(output) <= max_len else output[:max_len] + "\n\n…(truncated)"
                reply_in_thread(QUEUE_CHANNEL_ID, ts, f"✅ Draft ready for *{req.get('request_id')}*:\n```{out}```")
                add_done_reaction(QUEUE_CHANNEL_ID, ts)
                print("Posted + marked DONE.")
        except Exception as e:
            print("Error:", e)

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
