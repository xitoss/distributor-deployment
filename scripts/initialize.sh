#!/bin/bash
set -e

echo "=== Starting VPS setup ==="

# -------------------------------
# Update system
# -------------------------------
echo "Updating system..."
sudo apt update -y
sudo apt upgrade -y

# -------------------------------
# Install essential tools
# -------------------------------
echo "Installing essential tools..."
sudo apt install -y curl git ca-certificates software-properties-common lsb-release gnupg

# -------------------------------
# Check & install Python
# -------------------------------
if command -v python3 &>/dev/null; then
    PYTHON_BIN=$(command -v python3)
    echo "Python found: $($PYTHON_BIN --version)"
else
    echo "Python3 not found. Installing Python 3.12..."
    sudo apt install -y python3.12 python3.12-venv python3-pip
    PYTHON_BIN=python3.12
fi

# Ensure venv package is installed
sudo apt install -y python3-venv

# -------------------------------
# Create venv if not exists
# -------------------------------
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_BIN -m venv venv
else
    echo "Virtual environment already exists."
fi

# -------------------------------
# Activate venv and install Python dependencies
# -------------------------------
echo "Activating venv..."
source venv/bin/activate

# Check pip
if ! command -v pip &>/dev/null; then
    echo "pip not found. Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | python
fi

echo "Upgrading pip..."
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "No requirements.txt found, skipping pip install."
fi

# -------------------------------
# Install Docker + Docker Compose v2
# -------------------------------
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    # Remove old versions
    sudo apt remove -y docker docker-engine docker.io containerd runc || true

    # Add Docker GPG key & repo
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.gpg >/dev/null
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt update -y
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

else
    echo "Docker already installed: $(docker --version)"
fi

echo "=== Docker Compose version ==="
docker compose version

# -------------------------------
# Final message
# -------------------------------
echo "VPS initialyzation is completed!"
echo "Activate (venv) to run preflight.py which will setup prequisites for the application."
