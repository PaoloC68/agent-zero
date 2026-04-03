# Agent Zero — Proxmox LXC Migration Runbook

**Target**: `helpa0.com` running on Proxmox LXC at `192.168.1.10`
**Stack**: Docker → Nginx → Cloudflare Tunnel → Cloudflare edge
**Local DNS**: OPNsense Unbound splits `helpa0.com` → `192.168.1.10`

---

## Current Status (as of Apr 3 2026)

| Component | Status | Notes |
|-----------|--------|-------|
| LXC 500 | ✅ running | Ubuntu 24.04, 8 cores, 16GB RAM |
| Docker | ✅ active | overlay2, apparmor=unconfined |
| Agent Zero | ✅ active | :8080, 18,940 files migrated from k8s |
| Nginx | ✅ active | HTTPS :443 with self-signed cert (replace with Let's Encrypt) |
| Cloudflare Tunnel | ✅ active | 4 QUIC connections to fra03/06/08/21 |
| External access | ✅ live | https://helpa0.com/login → 200 |
| OPNsense split DNS | ⏳ manual | helpa0.com → 192.168.1.10 (do Phase 6) |
| Let's Encrypt cert | ⏳ manual | Replace self-signed once CF API token available |

**Proxmox host fix**: gateway was wrongly set to `192.168.1.1` — corrected to `192.168.1.254` (OPNsense LAN IP) in `/etc/network/interfaces`.

---

## Phase 1 — Proxmox LXC Setup

All commands run on the **Proxmox host** (`192.168.1.5`) unless noted.

### 1.1 Download Ubuntu 24.04 template

```bash
pveam update
pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst
```

### 1.2 Create the LXC container

Container ID: **500**.

```bash
pct create 500 local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst \
  --arch amd64 \
  --cores 8 \
  --memory 16384 \
  --swap 4096 \
  --hostname agent-zero \
  --net0 name=eth0,bridge=vmbr0,firewall=1,gw=192.168.1.1,ip=192.168.1.10/24,type=veth \
  --rootfs local-lvm:100 \
  --unprivileged 1 \
  --features nesting=1,keyctl=1 \
  --ostype ubuntu \
  --start 0
```

### 1.3 Add Docker-specific LXC settings

```bash
cat >> /etc/pve/lxc/500.conf << 'EOF'
lxc.apparmor.profile: unconfined
lxc.cap.drop:
lxc.mount.auto: proc:rw sys:rw
EOF
```

### 1.4 Start the container

```bash
pct start 500
pct enter 500
```

### 1.5 Inside LXC: system update + Docker install

```bash
apt update && apt upgrade -y
apt install -y curl ca-certificates gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable --now docker
docker run --rm hello-world
```

---

## Phase 2 — Data Migration

Run from your **local machine** (needs `kubectl` + `ssh` access to Proxmox).

### 2.1 Create directory structure on Proxmox LXC

```bash
ssh root@192.168.1.5 "pct exec 500 -- bash -c '
  mkdir -p /opt/agent-zero/{data,conf,cloudflared}
  chmod 700 /opt/agent-zero
'"
```

### 2.2 Extract /a0/usr from k8s and transfer

```bash
chmod +x deploy/proxmox/migrate-data.sh
PROXMOX_HOST="root@192.168.1.5" ./deploy/proxmox/migrate-data.sh
```

> The script streams `/a0/usr` via tar through SSH directly to the Proxmox host.
> It skips `.git` (gitops sidecar artifacts) and verifies file counts.

### 2.3 Copy config files to Proxmox LXC

```bash
scp deploy/proxmox/model_providers.yaml root@192.168.1.5:/tmp/
ssh root@192.168.1.5 "pct push 500 /tmp/model_providers.yaml /opt/agent-zero/conf/model_providers.yaml"

scp deploy/proxmox/docker-compose.yml root@192.168.1.5:/tmp/
ssh root@192.168.1.5 "pct push 500 /tmp/docker-compose.yml /opt/agent-zero/docker-compose.yml"
```

### 2.4 Create .env file

```bash
ssh root@192.168.1.5 "pct enter 500"
# Inside LXC:
cp /path/to/deploy/proxmox/.env.template /opt/agent-zero/.env
nano /opt/agent-zero/.env   # fill in all values
chmod 600 /opt/agent-zero/.env
```

---

## Phase 3 — Agent Zero Container

All commands inside the **LXC** (`pct enter 500`).

### 3.1 Authenticate with GHCR

```bash
source /opt/agent-zero/.env
echo "$GHCR_PAT" | docker login ghcr.io -u PaoloC68 --password-stdin
```

### 3.2 Start Agent Zero

```bash
cd /opt/agent-zero
docker compose pull
docker compose up -d
```

### 3.3 Wait for first-boot code copy

On first start, `copy_A0.sh` copies the Agent Zero source from the image into `/opt/agent-zero/data/`.
This takes ~30 seconds. Watch progress:

```bash
docker logs -f agent-zero 2>&1 | head -20
```

Expected output: `Copying files from /git/agent-zero to /a0...` then startup logs.

### 3.4 Verify

```bash
curl -s http://localhost:8080/api/health
# Expected: {"status":"ok"} or HTTP 200
```

> If `/api/health` returns 404, try `/login` — both return 200 on a healthy instance.

---

## Phase 4 — Nginx + TLS

### 4.1 Install Nginx and Certbot

```bash
apt install -y nginx certbot python3-certbot-dns-cloudflare
```

### 4.2 Create Cloudflare API token

In Cloudflare dashboard:
1. **My Profile → API Tokens → Create Token**
2. Use template: **Edit zone DNS**
3. Zone Resources: Include → Specific zone → `helpa0.com`
4. Copy the token

```bash
cat > /etc/cloudflare.ini << 'EOF'
dns_cloudflare_api_token = <YOUR_CLOUDFLARE_API_TOKEN>
EOF
chmod 600 /etc/cloudflare.ini
```

### 4.3 Obtain Let's Encrypt certificate

```bash
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/cloudflare.ini \
  -d helpa0.com \
  --agree-tos \
  --non-interactive \
  --email your@email.com
```

Certificate lands at `/etc/letsencrypt/live/helpa0.com/`.

### 4.4 Install Nginx config

```bash
cp /path/to/deploy/proxmox/nginx/helpa0.conf /etc/nginx/sites-available/helpa0.conf
ln -s /etc/nginx/sites-available/helpa0.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### 4.5 Verify

```bash
curl -sk https://localhost/api/health
# Expected: HTTP 200
```

---

## Phase 5 — Cloudflare Tunnel

### 5.1 Install cloudflared

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
  > /etc/apt/sources.list.d/cloudflared.list
apt update && apt install -y cloudflared
```

### 5.2 Authenticate and create tunnel

```bash
cloudflared tunnel login
cloudflared tunnel create helpa0
```

Note the **Tunnel UUID** printed after creation.

### 5.3 Configure the tunnel

```bash
TUNNEL_UUID=$(cloudflared tunnel list | grep helpa0 | awk '{print $1}')
mkdir -p /etc/cloudflared

sed "s/<TUNNEL_UUID>/$TUNNEL_UUID/g" \
  /path/to/deploy/proxmox/cloudflared/config.yml \
  > /etc/cloudflared/config.yml

cp ~/.cloudflared/${TUNNEL_UUID}.json /etc/cloudflared/
```

### 5.4 Route DNS and install service

```bash
cloudflared tunnel route dns helpa0 helpa0.com
cloudflared service install
systemctl enable --now cloudflared
```

### 5.5 Verify external access

```bash
curl -s https://helpa0.com/api/health
# Expected: HTTP 200 from external network
```

> In Cloudflare dashboard: **helpa0.com → Network → WebSockets → ON**

---

## Phase 6 — OPNsense Split DNS  ← ONLY REMAINING MANUAL STEP

### 6.1 Add host override via GUI

**Services → Unbound DNS → Overrides → Host Overrides → Add**

| Field | Value |
|-------|-------|
| Host | `helpa0` |
| Domain | `com` |
| Type | `A` |
| IP | `192.168.1.10` |
| Description | `Agent Zero local` |

Save and Apply.

### 6.2 Alternative: raw config

If you prefer the config file approach, add to `/var/unbound/unbound.conf` (or via custom options):

```
local-zone: "helpa0.com." redirect
local-data: "helpa0.com. A 192.168.1.10"
```

### 6.3 Verify local resolution

From a LAN device:
```bash
dig helpa0.com @192.168.1.1
# Expected: 192.168.1.10

curl -s https://helpa0.com/api/health
# Expected: HTTP 200 (served by local Nginx, not Cloudflare)
```

---

## Phase 7 — Validation Checklist

Run from both **external network** and **LAN**:

- [ ] `curl https://helpa0.com/api/health` → 200
- [ ] Open `https://helpa0.com` in browser → login page loads
- [ ] Send a chat message → response streams correctly (WebSocket working)
- [ ] Check Agent Zero Settings → Update → self-update UI loads (confirms full `/a0` is persistent)
- [ ] Verify guard plugin: `docker exec agent-zero ls /a0/usr/plugins/guard-system`
- [ ] Verify settings: `docker exec agent-zero cat /a0/usr/settings.json | python3 -m json.tool | head -20`

---

## Phase 8 — Decommission Nebius K8s

After **48 hours** of stable operation:

```bash
kubectl delete namespace agent-zero
```

Cancel the Nebius cluster in the Nebius console.

---

## Phase 9 — Authentik SSO (deferred)

When ready to add SSO, see the Authentik setup guide.
The Nginx config already has placeholder comments for forward auth integration.
Authentik will run as a separate Docker Compose stack in the same LXC.

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Container won't start | `docker logs agent-zero` — check copy_A0.sh output |
| WebSocket disconnects | Nginx `proxy_read_timeout` — must be ≥ 86400s for `/socket.io/` |
| Cloudflare 502 | `systemctl status cloudflared` + `journalctl -u cloudflared -n 50` |
| Local DNS not resolving | OPNsense: check Unbound override is saved and applied |
| Self-update fails | Verify `/opt/agent-zero/data` is writable by Docker user |
| GHCR pull fails | Re-run `echo "$GHCR_PAT" \| docker login ghcr.io -u PaoloC68 --password-stdin` |
