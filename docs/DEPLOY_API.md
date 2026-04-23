# Deploying the HydroSense API

The ESP32 in Ust-Kamenogorsk and your laptop in Almaty are on different
Wi-Fi networks. For the ESP32 to POST readings to `api.py`, the API
needs a **public URL** the ESP32 can reach over the internet.

Two paths — **pick ngrok for demo day, Render for anything longer.**

---

## Option A — ngrok (recommended for the competition)

A temporary public tunnel to your laptop. The ESP32 thinks it's
talking to a server on the internet; really it's talking to your
laptop through ngrok's relay.

**Pros:** ~2 minutes to set up, free, nothing to deploy, no data loss.
**Cons:** URL changes each time ngrok restarts (get a free account for
a stable one). Your laptop has to be on + on the internet for data to
flow.

### 1. Install ngrok

```bash
brew install ngrok               # macOS with Homebrew
# or download from https://ngrok.com/download
```

### 2. Create a free account + authenticate (one-time)

1. Go to <https://dashboard.ngrok.com/signup>
2. Copy your auth token from <https://dashboard.ngrok.com/get-started/your-authtoken>
3. In Terminal:
   ```bash
   ngrok config add-authtoken YOUR_TOKEN_HERE
   ```

### 3. Start the API + ngrok tunnel

Open **two** Terminal windows.

**Window 1** — the API:
```bash
cd "/Users/alanmusahitov/Desktop/sft stuff"
python api.py
```
Leave it running. You should see `Running on http://0.0.0.0:5001`.

**Window 2** — the tunnel:
```bash
ngrok http 5001
```
You'll see something like:
```
Forwarding  https://a1b2-203-0-113-42.ngrok-free.app -> http://localhost:5001
```

### 4. Paste that URL into the firmware

Open `firmware/sensor_node/sensor_node.ino`. Replace:
```c
const char* serverURL = "http://YOUR_BACKEND_HOST:5001/api/data";
```
with:
```c
const char* serverURL = "https://a1b2-203-0-113-42.ngrok-free.app/api/data";
```
(your actual ngrok URL). Flash the firmware once. The ESP32 will now
POST readings from anywhere with internet access.

### 5. Verify it works

From anywhere with a browser, visit:
```
https://a1b2-203-0-113-42.ngrok-free.app/api/health
```
You should see the JSON health response.

Then from a different machine / phone network:
```bash
curl -X POST https://YOUR-NGROK-URL/api/data \
  -H "Content-Type: application/json" \
  -d '{"node_id":"node_01","soil_moisture":40,"temperature_bmp":22,"temperature_dht":22,"humidity":50,"pressure":1010}'
```
You should get `{"status":"ok", ...}`. If yes, your ESP32 in the field
will work too.

### ngrok gotchas

- **URL resets on restart** — free ngrok gives a new random URL each
  time. If your laptop sleeps/restarts, you'll need to update the
  firmware with the new URL. Upgrade to a free-tier reserved domain to
  avoid this.
- **Laptop must be on** — if you close the lid, the tunnel dies and
  the ESP32 silently drops readings. For demo week, leave the laptop
  open and plugged in.
- **8h session limit on free tier** — the tunnel may expire overnight.
  Fine for a demo; annoying for a multi-day deploy.

---

## Option B — Render (persistent cloud deploy)

A real cloud deployment. The API runs on a server you don't maintain.
Free tier, minor caveats below.

**Pros:** always-on, stable URL, no laptop dependency.
**Cons:** ~15 min setup, free tier **spins down after 15 min of
inactivity** (takes ~30 s to wake on the next request — the ESP32
POSTs every 15 min, so each POST wakes it up, which is fine).

### 1. Push the project to GitHub

If you don't have a repo yet:
```bash
cd "/Users/alanmusahitov/Desktop/sft stuff"
git init
git add .
git commit -m "Initial commit"
# Create a new repo on github.com, then:
git remote add origin https://github.com/V1olent77/HydroSense.git
git push -u origin main
```

### 2. Add a Render config file

Save this as `render.yaml` at the project root:

```yaml
services:
  - type: web
    name: hydrosense-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt && python db/init_db.py
    startCommand: gunicorn api:app --bind 0.0.0.0:$PORT
    envVars:
      - key: PORT
        value: 10000
```

Commit + push:
```bash
git add render.yaml
git commit -m "Add Render deploy config"
git push
```

### 3. Connect Render to your repo

1. Sign up at <https://render.com/> (GitHub login is fine)
2. Dashboard → **New** → **Blueprint**
3. Point it at your GitHub repo
4. Render auto-detects `render.yaml` and creates the service
5. Wait ~3 min for the first build

Once it's deployed, Render gives you a URL like
`https://hydrosense-api.onrender.com`. Test it:
```bash
curl https://hydrosense-api.onrender.com/api/health
```

### 4. Paste that URL into the firmware (same as ngrok Step 4)

Use `https://hydrosense-api.onrender.com/api/data` for `serverURL`.

### Render gotchas

- **Ephemeral filesystem** — the free tier resets the disk on every
  redeploy. Your `hydrosense.db` starts empty after each push. For a
  few-day demo this is fine (readings persist until the next deploy).
  For real production, upgrade to a paid disk ($1/month) or switch to
  a managed Postgres.
- **Cold starts** — after 15 min idle the service sleeps. The first
  request wakes it up in ~30 s. ESP32 HTTPClient default timeout is
  longer than that, so POSTs will still succeed.
- **Secrets** — never commit Wi-Fi passwords or API keys to the repo.
  Use Render's **Environment** tab to set them instead.

---

## Which one should you use?

| Situation | Use |
|---|---|
| Competition week demo, laptop available | **ngrok** |
| Sensor deployed for 5+ days, no laptop babysitting | **Render** |
| Long-term research deployment | **Render** + paid disk, or Postgres |

For HydroSense in April 2026 — **ngrok is the right answer.** Render
adds operational complexity you don't need for a ~1-week demo.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| ESP32 logs "POST failed: connection refused" | API isn't running | Check that `python api.py` is active |
| ESP32 logs "POST failed: timeout" | DNS or network issue | Verify the URL works in a browser; check Wi-Fi SSID/password |
| Dashboard shows 0 readings despite ESP32 POSTing | ESP32 is hitting a different DB than the dashboard reads | Make sure both use the same `data/hydrosense.db` path |
| `ngrok: failed to start tunnel` | Not authenticated | Run `ngrok config add-authtoken …` with your token |
| Render deploy fails with "gunicorn: command not found" | Missing from requirements | Confirm `gunicorn>=21.2` is in `requirements.txt` |
