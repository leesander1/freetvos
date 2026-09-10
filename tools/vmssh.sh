#!/usr/bin/env bash
# Run a command on the development VM. -n matters: without it a backgrounded
# process on the far end inherits the channel and ssh never returns.
exec ssh -n -p 2222 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR -o ConnectTimeout=15 root@localhost "$@"
