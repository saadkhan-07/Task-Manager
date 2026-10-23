#!/bin/bash
# Task 3: Install Docker + Compose on Ubuntu EC2
set -e
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
echo "Done. Log out and log back in (or run: newgrp docker), then test: docker --version"
