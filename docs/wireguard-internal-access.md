# WireGuard Internal Access

This project uses host-level WireGuard to reach maintainer-only web panels without
publishing those panels on public HTTPS subdomains.

## Runtime Contract

Public ingress:

- `80/tcp` and `443/tcp` for the edge nginx public site, API, sitemap, robots.txt,
  and public MinIO object endpoint.
- One chosen WireGuard UDP port on the host, for example `51820/udp`.

VPN-only ingress:

- MinIO Console: `http://<VPN_BIND_ADDRESS>:18081`
- Databasus: `http://<VPN_BIND_ADDRESS>:18082`
- Agent API: `https://agent.<APP_DOMAIN>:18083/internal/agent/v1` with a trusted client certificate.

The production value of `VPN_BIND_ADDRESS` must be the server address on `wg0`,
for example `10.77.0.1`. The `.env.example` value uses `127.0.0.1` so local
development remains safe when WireGuard is not configured.

The seven Agent routes are mounted in the main Litestar application and reuse its settings, Dishka
container, request session factory, database role, process, secrets, and availability boundary.
They are not exposed by the public listener: `/internal/agent/v1` returns `404`, and
caller-supplied `X-Agent-Client-Certificate` headers are stripped before ordinary public backend
proxying. WireGuard, the separate nginx mTLS listener, its exact REST allowlist, scopes,
transport/core validation, and operation-specific storages constrain supported agent requests.

There is no separate process or database-role containment. Backend compromise, SQL injection, or
erroneous arbitrary SQL has the main backend role's database blast radius and can expose unrelated
backend secrets or affect public/admin availability. A compromised service that can reach the
backend on the private application network can forge the forwarded certificate header, so private
network isolation and the nginx-to-backend trust assumption are required controls.

PostgreSQL, Valkey, backend, MinIO, and Databasus must not publish
their own Docker ports. nginx remains the only compose service with public port
mappings.

## Host Setup

Install WireGuard on the production host:

```bash
sudo apt update
sudo apt install wireguard
```

Generate keys on the host. Keep private keys out of the repository and out of
logs:

```bash
umask 077
wg genkey | tee server.private | wg pubkey > server.public
wg genkey | tee maintainer-laptop.private | wg pubkey > maintainer-laptop.public
```

Create `/etc/wireguard/wg0.conf` on the server:

```ini
[Interface]
Address = 10.77.0.1/24
ListenPort = 51820
PrivateKey = <server private key>
SaveConfig = false

[Peer]
PublicKey = <maintainer laptop public key>
AllowedIPs = 10.77.0.2/32
```

Protect the server config and start WireGuard:

```bash
sudo chown root:root /etc/wireguard/wg0.conf
sudo chmod 600 /etc/wireguard/wg0.conf
sudo systemctl enable --now wg-quick@wg0
sudo wg show
```

Create the maintainer client config on the maintainer device:

```ini
[Interface]
Address = 10.77.0.2/32
PrivateKey = <maintainer laptop private key>

[Peer]
PublicKey = <server public key>
Endpoint = <server public IP or domain>:51820
AllowedIPs = 10.77.0.1/32
PersistentKeepalive = 25
```

`AllowedIPs` intentionally includes only the server VPN address. Do not route
the maintainer's full internet traffic, Docker subnet, PostgreSQL, or Valkey
through this VPN.

## Agent API Hostname Resolution

Keep `agent.<APP_DOMAIN>` in public DNS so Let's Encrypt HTTP-01 can issue and renew the nginx
certificate. Public DNS may point at the public server address, but trusted devices must resolve the
same hostname to `VPN_BIND_ADDRESS` while connected to WireGuard. Use managed split DNS or, for a
single workstation, an `/etc/hosts` entry such as:

```text
10.77.0.1 agent.<APP_DOMAIN>
```

Do not connect by raw VPN IP in normal use: TLS hostname verification must continue to validate the
Let's Encrypt certificate for `agent.<APP_DOMAIN>`. Split DNS changes routing only; it does not replace
mTLS client authentication.

## Firewall Baseline

For a UFW-managed host, keep public ingress narrow and replace `51820` with the
chosen WireGuard UDP port. Before enabling UFW, keep an SSH rule that matches
the current server access policy, or run the change from a provider console:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <trusted admin IP> to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 51820/udp
sudo ufw allow in on wg0 to 10.77.0.1 port 18081 proto tcp
sudo ufw allow in on wg0 to 10.77.0.1 port 18082 proto tcp
sudo ufw allow in on wg0 to 10.77.0.1 port 18083 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Do not allow `18081/tcp`, `18082/tcp`, or `18083/tcp` on the public interface. Docker also
binds those ports to `VPN_BIND_ADDRESS`, so they should not listen on the
server's public IP.

Because Docker publishes ports by adding host firewall/NAT rules, host-level
firewall policy remains part of the security boundary. On hosts with IPv4
forwarding enabled, verify from a network that is not connected to WireGuard
that `18081/tcp`, `18082/tcp`, and `18083/tcp` fail to connect on the public address. If they
connect, add explicit public-interface drops in the host firewall before the
Docker accept path, for example through UFW rules that deny those ports on the
public interface or equivalent `DOCKER-USER` chain rules managed by the host.
Keep SSH restricted to trusted admin source addresses or move it behind a
separate access path; a globally reachable `22/tcp` does not satisfy the
public-ingress contract above.

## Deployment

Set the GitHub Actions Environment `production` variable `VPN_BIND_ADDRESS` to
the server's WireGuard address, for example `10.77.0.1`. The deploy job runs
only from the manual **Deploy to production** workflow on `main`. It waits for
`production` environment approval before rendering `VPN_BIND_ADDRESS` into the
runtime `.env` from the environment manifest and restarting Docker Compose.

After deployment, inspect the nginx bindings on the host:

```bash
docker compose ps nginx
sudo ss -lntp | grep -E ':(80|443|18081|18082|18083)\b'
```

Expected result:

- `80` and `443` are reachable on the public address.
- `18081`, `18082`, and `18083` are bound only to `VPN_BIND_ADDRESS`.
- `18083` requires mTLS and forwards only the seven fixed `/internal/agent/v1` REST operations to
  the backend on the private Compose network; the public agent hostname remains a `404` sink
  outside ACME and the public application listener strips the trusted certificate header.

## Peer Revocation

To revoke a maintainer device:

1. Remove that peer block from `/etc/wireguard/wg0.conf`.
2. Remove it from the live interface:

   ```bash
   sudo wg set wg0 peer <revoked peer public key> remove
   sudo wg show
   ```

3. Verify the revoked device can no longer reach:

   ```bash
   curl --connect-timeout 3 http://10.77.0.1:18081
   curl --connect-timeout 3 http://10.77.0.1:18082
   curl --connect-timeout 3 https://10.77.0.1:18083/internal/agent/v1/matrix/authoring-context
   ```

## Acceptance Checks

From a public network without WireGuard:

```bash
curl --connect-timeout 3 http://<server public IP>:18081
curl --connect-timeout 3 http://<server public IP>:18082
curl --connect-timeout 3 https://<server public IP>:18083/internal/agent/v1/matrix/authoring-context
curl -kI https://s3-panel.<domain>
curl -kI https://backup.<domain>
curl -I https://agent.<domain>/internal/agent/v1/matrix/authoring-context
```

The first three commands must fail to connect. The old `s3-panel` and `backup`
subdomains must not display MinIO Console or Databasus, and public agent HTTPS must return `404`.

From the maintainer device while connected to WireGuard:

```bash
curl -I http://10.77.0.1:18081
curl -I http://10.77.0.1:18082
curl --cert <client-certificate-with-agent-chain> \
  --key <client-private-key> \
  https://agent.<domain>:18083/internal/agent/v1/matrix/authoring-context
```

The first two endpoints should reach their web services. The Agent API request should complete an
mTLS handshake and reach the private Agent route contour in the main backend; without a
certificate, it must fail at nginx.
The default system CA bundle validates nginx's Let's Encrypt server certificate; the agent CA chain
inside `--cert` authenticates the client in the opposite TLS direction.

WireGuard peer revocation and agent client revocation are separate controls. When a client device is
lost or compromised, revoke both. Never restore access by publishing `18083`, disabling mTLS, or
accepting a direct client-supplied certificate header.

## References

- WireGuard Quick Start: https://www.wireguard.com/quickstart/
- Docker port publishing: https://docs.docker.com/engine/network/port-publishing/
- UFW documentation: https://help.ubuntu.com/community/UFW
- Agent lifecycle and Codex setup: [agent-access.md](agent-access.md)
