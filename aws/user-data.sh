#!/bin/bash
# EC2 Launch Template "User data" (Ubuntu 22.04/24.04 AMI).
# Each new instance created by the Auto Scaling Group runs this on first boot.
# 1) Push this project to YOUR OWN GitHub repo
# 2) Replace REPO_URL below
set -e
REPO_URL="https://github.com/YOUR_USERNAME/taskmanager.git"

apt-get update -y
apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker

git clone "$REPO_URL" /opt/taskmanager
cd /opt/taskmanager
docker compose up -d --build
