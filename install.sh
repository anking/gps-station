#!/bin/bash

# Check if Git is installed
if ! command -v git &> /dev/null
then
    echo "Git not found, installing..."
    sudo apt-get update
    sudo apt-get install git -y
else
    echo "Git is already installed."
fi

# Check if Node.js is installed, and install it if necessary
if ! command -v node &> /dev/null
then
    echo "Node.js not found, installing..."
    curl -sL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "Node.js is already installed."
fi

# Clone the repository if not already done
if [ ! -d "gps-station" ]; then
    echo "Cloning GPS Station repository..."
    git clone https://github.com/anking/gps-station.git
else
    echo "Repository already exists."
fi

# Compile driver artifacts instruction
echo "Compile driver artifacts and place them in ./f9p directory as per instructions from zedf9p-server README."

# Ask user for 32 or 64 bit ARM processor
echo "Determining system architecture..."

ARCH=$(uname -m)

# Set the ARTIFACT_URL based on the architecture
if [[ "$ARCH" == "aarch64" ]]; then
    echo "64-bit ARM processor detected."
    ARTIFACT_URL="https://github.com/anking/zedf9p-server/releases/latest/download/linux-arm64.zip"
elif [[ "$ARCH" == "armv7l" ]]; then
    echo "32-bit ARM processor detected."
    ARTIFACT_URL="https://github.com/anking/zedf9p-server/releases/latest/download/linux-arm.zip"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi


# Download the appropriate driver artifact
echo "Downloading driver artifact..."
mkdir -p ./gps-station/f9p
wget $ARTIFACT_URL -O ./gps-station/f9p/linux-arm64.zip

# Extract the zip file
echo "Extracting driver artifact..."
unzip ./gps-station/f9p/*.zip -d ./gps-station/f9p/

# Create logs directory
sudo mkdir -p /home/pi/gps-station/logs
sudo chown pi:pi /home/pi/gps-station/logs
sudo chmod 755 /home/pi/gps-station/logs

# Install dependencies
echo "Installing npm dependencies..."
cd gps-station
npm install

# Build the application
echo "Building the application..."
npm run build

# Make driver executable
sudo chown pi:pi /home/pi/gps-station/build/f9p/Zedf9p
sudo chmod 755 /home/pi/gps-station/build/f9p/Zedf9p

# Create a symbolic link for the service
echo "Creating symbolic link for the service..."
sudo ln -s /home/pi/gps-station/gpsstationweb.service /etc/systemd/system/gpsstationweb.service

# Reload system daemons
echo "Reloading system daemons..."
sudo systemctl daemon-reload

# Enable the service
echo "Enabling the service..."
sudo systemctl enable gpsstationweb

# Remind about .env file with creds
echo "Make sure to create the .env file. A sample configuration is available in .env.example."
read -p "Type 'y' to confirm that you understand you must create a .env file in the gps-station directory with your credentials: " env_ack

# Ask if the user wants to start the service automatically
read -p "Do you want to start the service now? (y/n): " start_service
if [ "$start_service" == "y" ]; then
    # Start the service if user wants to start it
    echo "Starting the service..."
    sudo systemctl start gpsstationweb
    echo "Service started."
else
    echo "Service created, but not started."
fi

# Offer option to restart the machine
read -p "Do you want to restart the Raspberry Pi now to start the service automatically on boot? (y/n): " restart
if [ "$restart" == "y" ]; then
    sudo reboot
else
    echo "You can manually restart later for the service to start automatically."
fi
