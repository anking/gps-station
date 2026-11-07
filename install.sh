#!/usr/bin/env bash
# Sets up the base station on a Raspberry Pi. Safe to run again to update.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/gps-station}"
REPO_URL="https://github.com/anking/gps-station.git"
DRIVER_BASE_URL="https://github.com/anking/zedf9p-server/releases/latest/download"

case "$(uname -m)" in
    aarch64)
        DRIVER_ZIP="linux-arm64.zip"
        NODE_MAJOR=24
        ;;
    armv7l)
        # Node 24 has no 32-bit ARM build
        DRIVER_ZIP="linux-arm.zip"
        NODE_MAJOR=22
        ;;
    *)
        echo "Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

echo "Installing packages..."
sudo apt-get update
sudo apt-get install -y git unzip curl openssl

current_node_major() {
    command -v node > /dev/null 2>&1 && node -p "process.versions.node.split('.')[0]" || echo 0
}

if [ "$(current_node_major)" -lt 22 ]; then
    echo "Installing Node.js ${NODE_MAJOR}..."
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "Node.js $(node -v) is already installed."
fi

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating $INSTALL_DIR..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "Cloning into $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

echo "Downloading the F9P driver..."
tmp_zip="$(mktemp --suffix=.zip)"
curl -fL "$DRIVER_BASE_URL/$DRIVER_ZIP" -o "$tmp_zip"
rm -rf f9p
mkdir -p f9p
unzip -q "$tmp_zip" -d f9p
rm -f "$tmp_zip"
chmod 755 f9p/Zedf9p

echo "Installing npm dependencies and building..."
npm install --no-fund --no-audit
npm run build

mkdir -p logs data

if [ ! -f .env ]; then
    cp .env.example .env

    read -r -p "NTRIP mountpoint: " mountpoint
    read -r -s -p "NTRIP mountpoint password: " ntrip_password
    echo
    ui_password="$(openssl rand -base64 18)"

    sed -i \
        -e "s|^NTRIP_MOUNTPOINT=.*|NTRIP_MOUNTPOINT=${mountpoint}|" \
        -e "s|^NTRIP_PASSWORD=.*|NTRIP_PASSWORD=${ntrip_password}|" \
        -e "s|^UI_PASSWORD=.*|UI_PASSWORD=${ui_password}|" \
        .env

    echo "Generated a web UI password, also saved in $INSTALL_DIR/.env:"
    echo "    ${ui_password}"
fi
chmod 600 .env

echo "Installing the service..."
sed -e "s|__USER__|$(id -un)|" -e "s|__DIR__|$INSTALL_DIR|" -e "s|__NODE__|$(command -v node)|" gpsstationweb.service \
    | sudo tee /etc/systemd/system/gpsstationweb.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable gpsstationweb
sudo systemctl restart gpsstationweb

echo "Done. Check it with: sudo systemctl status gpsstationweb"
