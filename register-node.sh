#!/usr/bin/env bash

echo "{{ NODE_IP }} {{ NODE_NAME }}" | sudo tee -a /etc/hosts

su ceph-deploy

echo "Host {{ NODE_NAME }}" >> ~/.ssh/config
echo "    Hostname {{ NODE_NAME }}" >> ~/.ssh/config
echo "    User ceph-deploy" >> ~/.ssh/config
