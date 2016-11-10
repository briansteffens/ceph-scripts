#!/usr/bin/env bash

su ceph-deploy
mkdir -p ~/.ssh
echo "{{ ID_RSA }}" > ~/.ssh/id_rsa
echo "{{ ID_RSA_PUB }}" > ~/.ssh/id_rsa.pub
