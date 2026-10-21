#!/bin/sh
# Bluetooth adapter power: toggle (no args) or query status (arg "status")
if [ "$1" = "status" ]; then
    bluetoothctl show 2>/dev/null | grep -m1 'Powered:' | grep -q yes && echo on || echo off
    exit 0
fi

if bluetoothctl show 2>/dev/null | grep -q 'Powered: yes'; then
    bluetoothctl power off
else
    bluetoothctl power on
fi
