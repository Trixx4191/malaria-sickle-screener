#!/bin/sh
# Read-only host snapshot; safe to run locally or over SSH.
set -eu

printf '\nMachine and load\n'
uname -m
getconf _NPROCESSORS_ONLN
uptime

printf '\nMemory\n'
free -m

printf '\nDisk\n'
df -h / /var /tmp

printf '\nLargest processes (no command arguments)\n'
ps -eo pid,comm,rss,pcpu --sort=-rss | head -16

printf '\nListening TCP ports\n'
ss -ltn

printf '\nRunning services\n'
systemctl --no-pager --type=service --state=running || true

if command -v docker >/dev/null 2>&1; then
    printf '\nContainers\n'
    if docker info >/dev/null 2>&1; then
        docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
        docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
    elif sudo -n docker info >/dev/null 2>&1; then
        sudo -n docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
        sudo -n docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
    else
        printf 'Docker stats require access to the Docker socket.\n'
    fi
fi
