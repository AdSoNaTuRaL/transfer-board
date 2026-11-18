# Transfer board

This is a local-only web page for moving URLs and text between devices on your own network.

## Run from WSL

```bash
cd /projects/transfer-board
TRANSFER_PIN='choose-a-private-pin' python3 app.py
```

Open the address printed by the app on an iPhone or iPad connected to the same Wi-Fi, then enter the PIN you chose.

If it works on the PC but not the phone, run this once from an Administrator PowerShell window on Windows to permit the local port through the firewall:

```powershell
New-NetFirewallRule -DisplayName "Transfer board" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8787 -Profile Private
```

Only use it on a trusted home or work network. Stop the app with `Ctrl+C` when finished; all entries are erased at that time.
