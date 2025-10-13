#!/bin/bash
# Uninstall Al systemd service

echo "Uninstalling Al systemd service..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Don't run this as root. It will use sudo when needed."
    exit 1
fi

# Stop service if running
echo "Stopping Al service..."
sudo systemctl stop al.service 2>/dev/null || true

# Disable service
echo "Disabling Al service..."
sudo systemctl disable al.service 2>/dev/null || true

# Remove service file
echo "Removing service file..."
sudo rm -f /etc/systemd/system/al.service

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo
echo "✓ Al service uninstalled successfully!"
echo
echo "Note: This does not delete the Al code or logs."
echo "The bot is just no longer a system service."
echo
echo "You can still run Al manually with ./start.sh"
