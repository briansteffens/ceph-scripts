#!/usr/bin/env bash

su ceph-deploy
mkdir -p ~/.ssh
echo "{{ AUTHORIZED_KEY }}" > ~/.ssh/authorized_keys
