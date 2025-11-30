#!/bin/bash
set -e


echo "===Creating necessary dirs and adding permission==="

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIRS="$BASE_DIR/media $BASE_DIR/processing $BASE_DIR/backup"

for DIR in $DIRS; do
    mkdir -p "$DIR"
    echo "$DIR has been created."
    chmod -R 755 "$DIR"
    echo "assigend permission for $DIR"
done


echo "=== Starting VPS setup ==="

# -------------------------------
# Update system once
# -------------------------------
echo "Updating system..."
sudo apt update -y
sudo apt upgrade -y

# -------------------------------
# Install essential packages once
# -------------------------------
echo "Installing essential tools..."
sudo apt install -y \
    curl \
    git \
    ca-certificates \
    software-properties-common \
    lsb-release \
    gnupg \
    python3-venv \
    python3-pip

# -------------------------------
# Check & install Python 3.12 if needed
# -------------------------------
PYTHON_BIN=$(command -v python3 || true)
if [ -z "$PYTHON_BIN" ]; then
    echo "Python3 not found. Installing Python 3.12..."
    sudo apt install -y python3.12 python3.12-venv python3-pip
    PYTHON_BIN=python3.12
else
    echo "Python found: $($PYTHON_BIN --version)"
fi

# -------------------------------
# Create virtual environment if not exists
# -------------------------------
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    $PYTHON_BIN -m venv venv
else
    echo "Virtual environment already exists."
fi

# -------------------------------
# Activate venv and install Python dependencies
# -------------------------------
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements if file exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "No requirements.txt found, skipping Python dependencies installation."
fi

# -------------------------------
# Install Docker + Docker Compose v2
# -------------------------------
echo "=== Docker + Docker Compose Setup ==="

if command -v docker &>/dev/null; then
    echo "Docker is already installed: $(docker --version)"
else
    echo "Installing Docker..."

    # If old files still available, docker will fail to install...
    # Remove old Docker versions if present
    sudo apt remove -y docker docker-engine docker.io containerd runc || true

    # Remove ALL old Docker repository configurations
    sudo rm -f /etc/apt/sources.list.d/docker.list
    sudo rm -f /etc/apt/sources.list.d/docker.sources
    sudo rm -f /etc/apt/keyrings/docker.asc
    sudo rm -f /etc/apt/keyrings/docker.gpg
    sudo rm -f /etc/apt/trusted.gpg.d/docker.gpg
    # Remove any Docker entries from main sources.list
    sudo sed -i '/download.docker.com/d' /etc/apt/sources.list

    # Add Docker's GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add Docker repository (deb822 format)
    sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

    # Update package lists
    sudo apt update -y

    # Install Docker Engine + plugins
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    echo "Docker installed successfully: $(docker --version)"
fi

# Verify Docker Compose v2
if command -v docker &>/dev/null; then
    echo "=== Docker Compose version ==="
    docker compose version
fi

# -------------------------------
# Final message
# -------------------------------
echo "=== VPS initialization completed! ==="
echo "Activate virtual environment (source venv/bin/activate) to run Python scripts."
