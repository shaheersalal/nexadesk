# Oracle Cloud Always Free — backup/alternative to Railway

This is a second deploy target, not a replacement for the documented Railway
flow in `../../DEPLOYMENT.md`. Use it if Railway costs become a problem, or as
a warm standby. Unlike Railway, this is a real VM you administer yourself —
no Nixpacks, no managed TLS, no auto-restart-on-crash unless you set it up
(covered below).

Three things Railway did for you that you now own:
- **TLS termination** (Caddy, config included, auto-renews via Let's Encrypt)
- **Process supervision / restart on crash** (systemd unit, included)
- **Idle-reclaim risk.** Oracle can reclaim an Always Free instance if CPU,
  network, *and* memory all stay under 20% (95th percentile) for 7 straight
  days. A low-traffic receptionist bot can plausibly look that idle. See
  "Keeping the instance alive" below — the reliable fix is converting to
  Pay-As-You-Go (still $0 as long as you stay under Always Free limits), a
  keep-alive timer is only a partial mitigation.

## 1. Sign up (browser — nothing here can do this for you)

1. Go to oracle.com/cloud/free and start signup. A **credit card is
   required** for identity verification — you are not charged unless you
   explicitly upgrade to a paid account; expect a small temporary
   authorization hold that clears in 3-5 days.
2. **Pick your home region carefully.** You cannot change it later, and
   Always Free compute/DB can only be provisioned in your home region. Pick
   whichever is geographically closest to your users (or to you, since this
   is inbound Twilio traffic from wherever your customers call from).
3. Wait for account activation (usually minutes, sometimes longer).

## 2. Create the VM

In the OCI Console: **Compute → Instances → Create Instance**.

- **Name:** `nexadesk-api`
- **Image:** Canonical Ubuntu **24.04** (matches the Python 3.12 pin in
  `nixpacks.toml` — Ubuntu 24.04 ships Python 3.12 by default)
- **Shape:** click "Change shape" → Ampere → **VM.Standard.A1.Flex** → set
  **2 OCPUs / 12 GB memory** (the full Always Free allotment — don't split it
  across multiple instances, this app wants it in one place)
- **Networking:** default VCN is fine; make sure "Assign a public IPv4
  address" is checked
- **SSH keys:** upload your public key (or generate one in-console and save
  the private key — you only get it once)

If you hit **"Out of host capacity"** creating the A1 shape: this is a known,
widely-reported Always Free issue, not something specific to your account.
Retry over the next few hours/days, or try creating it via a different
availability domain in the same region if your region has more than one.

## 3. Open the firewall — two layers, both required

OCI blocks inbound traffic at **both** the cloud-level Security List **and**
the VM's own iptables/netfilter. Missing either one means "it's not working"
with no obvious error.

**Security List** (Console → your VCN → Security Lists → default → Add
Ingress Rules): add rules for `0.0.0.0/0` → TCP destination port `80` and
`443` (that's all — the app itself is only reachable through Caddy on
localhost).

**On the VM itself**, Ubuntu's default iptables persists rules that block
everything not already allowed. Run once after first boot:

```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 4. Provision the box

Copy `provision.sh` to the VM and run it — it installs Python 3.12, ffmpeg,
Caddy, clones the repo, creates the venv, and bakes the tiktoken cache (same
reason `nixpacks.toml` does it: avoids a first-request dependency on Azure
blob storage).

```bash
scp deploy/oracle/provision.sh ubuntu@<VM_PUBLIC_IP>:~/
ssh ubuntu@<VM_PUBLIC_IP>
chmod +x provision.sh && ./provision.sh
```

Then create `/opt/nexadesk/app/.env` on the VM with every variable from
`.env.example`, filled in the same way you filled Railway's Variables tab
(same secrets — Qdrant, Upstash, Supabase, Twilio, `APP_ENV=production`,
`APP_SECRET_KEY`, etc.). `TRUST_PROXY_HEADERS` stays `false` here too: Caddy
runs on the same box and does not overwrite forwarded-for headers from a
spoofable external source, but if you later put Cloudflare in front, revisit
this exactly as the Railway notes describe.

## 5. Install the systemd service and Caddy config

```bash
sudo cp deploy/oracle/nexadesk-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nexadesk-api

sudo cp deploy/oracle/Caddyfile /etc/caddy/Caddyfile
# edit the domain in that file first if it's not api.nexadesk.site
sudo systemctl restart caddy
```

Point `api.nexadesk.site`'s DNS at the VM's public IP (A record). Keep
Cloudflare **Gray Cloud (DNS only)**, same as the Railway note — Caddy needs
to see the real client for its own Let's Encrypt HTTP-01 challenge and to
terminate TLS itself; an orange-cloud proxy in front adds a second WebSocket
hop that isn't worth debugging unless you specifically want Cloudflare's
edge protection later.

Caddy gets you free auto-renewing TLS and proxies WebSocket upgrades
transparently — no special config needed for the Twilio media stream or the
Deepgram-facing side, `reverse_proxy` handles the upgrade itself.

## 6. Keeping the instance alive

Install the keep-alive timer:

```bash
sudo cp deploy/oracle/keepalive.sh /opt/nexadesk/keepalive.sh
sudo chmod +x /opt/nexadesk/keepalive.sh
sudo cp deploy/oracle/nexadesk-keepalive.service /etc/systemd/system/
sudo cp deploy/oracle/nexadesk-keepalive.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nexadesk-keepalive.timer
```

This is a **partial mitigation**, not a guarantee — Oracle's reclaim policy
is stated in terms of CPU/network/memory utilization, and a cheap HTTP ping
mostly moves the network needle, not CPU or memory. If this project is meant
to stay up reliably (portfolio demos, actual customers), the dependable fix
is converting the account to Pay-As-You-Go in the OCI console: Always Free
resources stay free as long as you're under the limits above, and PAYG
accounts are not subject to the idle-reclaim sweep the way free-trial-only
accounts are.

## 7. Verify

```bash
curl https://api.nexadesk.site/health
```

Then point one Twilio number's voice webhook at the Oracle URL temporarily
and place a real test call before cutting DNS over for real — same as you'd
verify any deploy target change.

## Redeploying after a code change

No CI/CD wired up here yet (Railway's git-push-to-deploy doesn't exist on a
bare VM). Manual pull + restart:

```bash
ssh ubuntu@<VM_PUBLIC_IP>
cd /opt/nexadesk/app
git pull
source /opt/nexadesk/venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart nexadesk-api
```

Worth scripting as a GitHub Actions SSH deploy step if this becomes the
primary target — not set up yet.
