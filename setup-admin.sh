#!/usr/bin/env bash

curl 'https://download.ceph.com/keys/release.asc' | apt-key add -
echo deb https://download.ceph.com/debian-jewel/ $(lsb_release -sc) main | \
    tee /etc/apt/sources.list.d/ceph.list
apt-get install -y apt-transport-https
apt-get update
apt-get install ceph-deploy
