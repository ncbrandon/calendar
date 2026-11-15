# Install the server

The server is the one program that holds the calendar. Install it in **one** place. Pick the option that matches
your variant.

| Option | Use it for | Time |
|---|---|---|
| 1. Proxmox container | Variants A, C, D (recommended) | 20 min |
| 2. On the Raspberry Pi | Variant B | 15 min |
| 3. Docker | If you already run Docker somewhere | 10 min |

You need this repository on GitHub first (upload the folder as a new repository), or copy the folder over with
`scp` or a USB stick. The steps below use `git clone`; replace `YOUR-NAME` with your GitHub user name.

## Option 1: Proxmox container (LXC)

1. In the Proxmox web page, select your storage (usually `local`), open **CT Templates**, click **Templates**,
   and download `debian-13-standard`.
2. Click **Create CT**. Use these values and leave the rest alone:
   - Hostname: `opsboard`
   - Unprivileged container: checked
   - Template: the Debian 13 template from step 1
   - Disk: 8 GB (add more later if you upload a lot of video)
   - CPU: 1 core. Memory: 512 MB. Swap: 512 MB
   - Network: DHCP is fine for now
3. Start the container, open its **Console**, and log in as `root`.
4. Install git and fetch the program:

   ```bash
   apt-get update && apt-get install -y git
   ```

   ```bash
   git clone https://github.com/YOUR-NAME/opsboard.git /opt/opsboard-repo
   ```

5. Set the container's time zone so "work hours" are right (change the zone to yours):

   ```bash
   timedatectl set-timezone America/Chicago
   ```

6. Run the installer:

   ```bash
   bash /opt/opsboard-repo/deploy/install-server.sh
   ```

7. The installer prints the web address, a **password**, and a **screen token**. Write all three down.
8. In your router, give the container a fixed address (a "DHCP reservation") so the wall screens can always find it.
9. In Proxmox, select the container, open **Options**, and set **Start at boot** to Yes.
10. Test: open the web address from your PC and sign in with the password.

## Option 2: On the Raspberry Pi (Variant B)

Do the first five steps of [kiosk-setup.md](kiosk-setup.md) first, so the Pi has Raspberry Pi OS and is on the network. Then, in a terminal on the Pi:

1. Fetch the program:

   ```bash
   git clone https://github.com/YOUR-NAME/opsboard.git ~/opsboard-repo
   ```

2. Run the installer:

   ```bash
   sudo bash ~/opsboard-repo/deploy/install-server.sh
   ```

3. Write down the password and screen token it prints.
4. Test: on the Pi, open `http://localhost:8080` in the browser and sign in.

## Option 3: Docker

1. Copy `.env.example` to `.env` and edit the password, token, and time zone.
2. Start it:

   ```bash
   docker compose up -d --build
   ```

3. Open `http://SERVER-ADDRESS:8080`.

## After installing

### Where things are

| What | Where (options 1 and 2) |
|---|---|
| Password, screen token, API key | `/etc/opsboard.env` |
| Database and uploads | `/var/lib/opsboard/` |
| Program | `/opt/opsboard/` |
| Logs | `journalctl -u opsboard -e` |

After editing `/etc/opsboard.env`, restart: `systemctl restart opsboard`.

### Backups

- **Proxmox:** add the container to a scheduled backup job (Datacenter, Backup). That covers everything.
- **Anywhere:** `sudo bash deploy/backup.sh /path/to/backups` writes one dated file with the database and all
  uploads and keeps the newest 30. The top of the script shows how to run it every night.
- A Raspberry Pi SD card can fail without warning. If the server is on the Pi (Variant B), send the backups to
  another machine or a USB drive.

### Updating

```bash
cd /opt/opsboard-repo && git pull && bash deploy/install-server.sh
```

Your settings file and data are kept.

### Optional: let Claude read a permit PDF

Without this, you enter requirements by hand or with the spreadsheet template, which works fine.

1. Create an API key at https://console.anthropic.com. This is pay-as-you-go; reading one permit costs cents to a
   few dollars depending on its length.
2. Add the key to `/etc/opsboard.env` on the line `ANTHROPIC_API_KEY=` (remove the `#`).
3. Restart the server. "Read requirements" on the Sampling tab now works on PDFs.

The permit is sent to Anthropic's API to be read. If your utility has rules about that, use the spreadsheet instead.
