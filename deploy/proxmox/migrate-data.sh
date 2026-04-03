#!/bin/bash
set -euo pipefail

NAMESPACE="agent-zero"
PROXMOX_HOST="${PROXMOX_HOST:-root@192.168.1.5}"
DEST_PATH="/opt/agent-zero/data"

POD=$(kubectl -n "$NAMESPACE" get pods -o jsonpath='{.items[0].metadata.name}')
echo "Source pod: $POD"

echo "Streaming /a0/usr from pod to $PROXMOX_HOST:$DEST_PATH/usr ..."
kubectl -n "$NAMESPACE" exec "$POD" -c agent-zero -- \
    tar czf - -C /a0 usr --exclude='usr/.git' \
    | ssh "$PROXMOX_HOST" "mkdir -p $DEST_PATH && tar xzf - -C $DEST_PATH"

echo "Verifying file count..."
LOCAL=$(kubectl -n "$NAMESPACE" exec "$POD" -c agent-zero -- find /a0/usr -type f | wc -l)
REMOTE=$(ssh "$PROXMOX_HOST" "find $DEST_PATH/usr -type f | wc -l")
echo "  Pod:    $LOCAL files"
echo "  Remote: $REMOTE files"

echo "Done."
