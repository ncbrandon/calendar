# Reaching the web page from outside the plant

The web page works on your plant network as soon as the server is installed. To reach it from home or your phone,
use one of these. **Do not forward a port on your router to OpsBoard.** It is a small program with a single shared
password and was not built to face the open internet.

## Recommended: Tailscale (free for this use)

Tailscale makes a private, encrypted link between your devices. Nothing is exposed to the internet.

1. Create an account at https://tailscale.com.
2. On the server (Proxmox container console, or the Pi):

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   ```

   ```bash
   tailscale up
   ```

3. Open the link it prints and approve the server. If `tailscale up` complains about TUN (common in an
   unprivileged Proxmox container), follow Tailscale's guide "Tailscale in LXC containers". It is two lines added
   to the container's config file on the Proxmox host, then a container restart.
4. Install the Tailscale app on your phone and PC and sign in with the same account.
5. Open `http://opsboard:8080` (or the 100.x.y.z address shown in the Tailscale app) from anywhere.
6. In the Tailscale admin page, turn off key expiry for the server so it does not drop off in six months.

## Alternative: Cloudflare Tunnel with Cloudflare Access

Gives you a normal web address such as `https://calendar.yourdomain.com` with a login page in front of it.
Needs a domain name on Cloudflare. Use this if several people without Tailscale need access. Always put
Cloudflare Access in front; never publish the tunnel without it.

## Either way

- Keep the OpsBoard password set (`OPSBOARD_PASSWORD` in `/etc/opsboard.env`).
- The wall screens use the screen token, not the password. If the token ever leaks, change it in the server's
  settings file and in each wall-screen computer's `kiosk.env`.
