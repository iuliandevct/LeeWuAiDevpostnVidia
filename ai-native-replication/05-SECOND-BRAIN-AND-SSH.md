# Second Brain and SSH integration

## SSH between Macs

On the destination Mac, enable:

```text
System Settings → General → Sharing → Remote Login
```

Generate a dedicated key on every client:

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519_other_mac
```

Verify the server fingerprint before installing the key:

```bash
ssh-keyscan -T 3 -t ed25519 SERVER_IP | ssh-keygen -lf -
```

Copy only the public key:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_other_mac.pub USER@SERVER_IP
```

Example SSH alias:

```sshconfig
Host other-mac
    HostName SERVER_IP
    User REMOTE_USER
    IdentityFile ~/.ssh/id_ed25519_other_mac
    IdentitiesOnly yes
    StrictHostKeyChecking yes
```

Never copy the private key to another machine.

## Second Brain architecture

The reference deployment has:

```text
MacBook Second Brain website :8090
MacBook Graph API            :8091
Native Mac Graph API         :8091
Native Mac Grafana           :3000
```

The Second Brain website combines:

1. its local Docker Graph API at `http://localhost:8091/status`;
2. the authorized native Mac Graph API over the LAN.

The native Graph API publishes two metadata-only services:

```text
Jay Mac Pro · Grafana
Jay Mac Pro · Hermes
```

Grafana health uses `/api/health`. Hermes health checks the supervised gateway
process. The website refreshes approximately every five seconds and makes
services with a URL clickable.

## Durable networking

Hardcoded DHCP addresses can change. For the other three computers, use one of:

- router DHCP reservations;
- Bonjour `.local` hostnames;
- Tailscale;
- a private Cloudflare Tunnel with access controls.

Do not expose ports 3000, 8090, 8091, or agent gateways through public router
port forwarding.

## Backups

Before replacing the Second Brain page, save the current `index.html` outside
the container and record its checksum. If the Nginx mount is read-only, update
the persistent host source through a temporary authorized helper mount, then
reload Nginx.
