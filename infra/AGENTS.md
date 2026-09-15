# Infrastructure Instructions

These rules apply to infrastructure owned by the whole deployment under `infra/**`. Configuration
that belongs only to the backend must stay with that application; shared edge, network,
deployment, and cross-service infrastructure belongs here or in the root Docker Compose files.

## Edge And Network Boundaries

- Keep nginx as the public edge for TLS, public domains, `/api/*`, exact `/sitemap.xml` and
  `/robots.txt`, and the public MinIO object endpoint. VPN-only internal
  panels must remain bound to `VPN_BIND_ADDRESS`.
- Keep security headers and CSP at nginx. Add only the exact asset, external origin, Swagger/UI,
  upload-preview, or MinIO source required; do not use wildcard origins or broaden inline script or
  style allowances.
- Coarse anonymous public rate limiting belongs at nginx. Add backend rate limiting only for an
  explicitly designed identity-aware or business quota keyed by a user, account, API key, tenant,
  or subscription.

## Container Security

- Do not add public service ports, `network_mode: host`, `privileged: true`, Docker socket mounts,
  broad `cap_add`, or root runtime users unless the task explicitly requires them and documents the
  security tradeoff.
- Keep backend, PostgreSQL, Valkey, MinIO, and internal panels on private networks with
  only the intended nginx or VPN-bound entrypoint exposed.

## Agent Access Edge

- Expose the Agent REST contour only through the VPN-bound nginx mTLS listener at
  `https://agent.<APP_DOMAIN>:18083/internal/agent/v1`. Forward only the exact seven method/path
  pairs, return `404` for the internal path on public listeners, and strip caller-supplied
  `X-Agent-Client-Certificate` headers before proxying other backend routes.
- Treat the nginx-to-backend application network as a trusted contour: a service already on that
  network can forge the forwarded certificate header. Preserve network isolation, distinct client
  certificates, safe content-free logs, and certificate-scoped rate limiting.
- Keep the offline root off-server and the issuing CA in dedicated Compose secrets. Never add a
  public/plaintext Agent listener, shared certificate, bearer fallback, or remote MCP endpoint.
