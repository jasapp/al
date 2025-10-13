#!/bin/bash
# Install Al as a systemd service

cd "$(dirname "$0")"

echo "Installing Al systemd service..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Don't run this as root. It will use sudo when needed."
    exit 1
fi

# Check for venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✓ Virtual environment exists"
fi

# Check for .env
if [ ! -f ".env" ]; then
    echo "ERROR: No .env file found. Copy .env.example and configure it first."
    exit 1
fi
echo "✓ .env file exists"

# Create logs directory
mkdir -p logs
echo "✓ Logs directory ready"

# Copy service file to systemd
echo "Installing systemd service file..."
sudo cp al.service /etc/systemd/system/al.service

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable service (start on boot)
echo "Enabling Al service..."
sudo systemctl enable al.service

echo
echo "✓ Al service installed successfully!"
echo
echo "Commands:"
echo "  sudo systemctl start al      # Start Al"
echo "  sudo systemctl stop al       # Stop Al"
echo "  sudo systemctl restart al    # Restart Al"
echo "  sudo systemctl status al     # Check status"
echo "  journalctl -u al -f          # View logs (live)"
echo "  journalctl -u al -n 50       # View last 50 log lines"
echo
echo "Al will now start automatically on boot."
echo
echo "Start Al now? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    sudo systemctl start al
    sleep 2
    sudo systemctl status al
fi
