#!/bin/bash
# Task 2: Basic Linux administration (run these ONE BY ONE in the exam so you can show output)

whoami                      # current user
pwd                         # current directory
uname -a                    # OS info
df -h                       # disk usage
free -h                     # memory usage

mkdir -p ~/devops_lab       # create a directory
cd ~/devops_lab
ls -la                      # list with permissions

echo "DevOps lab file" > report.txt
ls -l report.txt            # default permissions (rw-r--r--)

chmod 640 report.txt        # owner: read/write, group: read, others: none
ls -l report.txt            # -rw-r----- ...

chmod u+x report.txt        # add execute for owner
ls -l report.txt

sudo chown ec2-user:ec2-user report.txt   # change owner (use 'ubuntu' on Ubuntu AMIs)
ls -l report.txt
