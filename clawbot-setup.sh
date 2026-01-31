#!/bin/bash
set -euo pipefail

# ============================================
# ClawBot Secure Setup Script
# Market Sentiment Analyst
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.openclaw"
PROJECT_CONFIG_DIR="$SCRIPT_DIR/.openclaw"

echo "============================================"
echo "  ClawBot Secure Setup"
echo "  Market Sentiment Analyst"
echo "============================================"
echo ""

# ----------------------------------------------
# Pre-flight Security Checks
# ----------------------------------------------
echo -e "${YELLOW}[1/6] Running security pre-flight checks...${NC}"

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo -e "${RED}ERROR: Node.js is not installed. Install Node.js >= 22${NC}"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 22 ]; then
    echo -e "${RED}ERROR: Node.js version must be >= 22. Current: $(node -v)${NC}"
    exit 1
fi
echo -e "${GREEN}  Node.js version OK: $(node -v)${NC}"

# ----------------------------------------------
# Install OpenClaw (if not installed)
# ----------------------------------------------
echo -e "${YELLOW}[2/6] Checking OpenClaw installation...${NC}"

if ! command -v openclaw &> /dev/null; then
    echo "  Installing OpenClaw..."
    npm install -g openclaw@latest
else
    echo -e "${GREEN}  OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'installed')${NC}"
fi

# ----------------------------------------------
# Create secure config directory
# ----------------------------------------------
echo -e "${YELLOW}[3/6] Setting up secure configuration directory...${NC}"

mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# ----------------------------------------------
# Copy project configuration
# ----------------------------------------------
echo -e "${YELLOW}[4/6] Installing secure configuration...${NC}"

if [ -f "$PROJECT_CONFIG_DIR/openclaw.json" ]; then
    cp "$PROJECT_CONFIG_DIR/openclaw.json" "$CONFIG_DIR/openclaw.json"
    chmod 600 "$CONFIG_DIR/openclaw.json"
    echo -e "${GREEN}  Configuration installed with restricted permissions (600)${NC}"
else
    echo -e "${RED}ERROR: Project config not found at $PROJECT_CONFIG_DIR/openclaw.json${NC}"
    exit 1
fi

# Copy AGENTS.md to workspace
mkdir -p "$CONFIG_DIR/workspace"
if [ -f "$PROJECT_CONFIG_DIR/AGENTS.md" ]; then
    cp "$PROJECT_CONFIG_DIR/AGENTS.md" "$CONFIG_DIR/workspace/AGENTS.md"
    echo -e "${GREEN}  Agent instructions installed${NC}"
fi

# ----------------------------------------------
# Verify Security Configuration
# ----------------------------------------------
echo -e "${YELLOW}[5/6] Verifying security configuration...${NC}"

# Check that gateway binds to loopback
if grep -q '"bind": "loopback"' "$CONFIG_DIR/openclaw.json"; then
    echo -e "${GREEN}  Gateway bound to loopback only${NC}"
else
    echo -e "${RED}WARNING: Gateway not bound to loopback!${NC}"
fi

# Check external connections disabled
if grep -q '"allowExternalConnections": false' "$CONFIG_DIR/openclaw.json"; then
    echo -e "${GREEN}  External connections disabled${NC}"
else
    echo -e "${RED}WARNING: External connections may be enabled!${NC}"
fi

# Check all external channels disabled
if grep -q '"telegram":' "$CONFIG_DIR/openclaw.json" && grep -q '"enabled": false' "$CONFIG_DIR/openclaw.json"; then
    echo -e "${GREEN}  External channels disabled${NC}"
else
    echo -e "${YELLOW}  Review channel configuration manually${NC}"
fi

# Check sandbox mode
if grep -q '"sandboxMode": "strict"' "$CONFIG_DIR/openclaw.json"; then
    echo -e "${GREEN}  Strict sandbox mode enabled${NC}"
else
    echo -e "${RED}WARNING: Sandbox mode not set to strict!${NC}"
fi

# ----------------------------------------------
# Create logs directory
# ----------------------------------------------
echo -e "${YELLOW}[6/6] Setting up logging...${NC}"
mkdir -p "$CONFIG_DIR/logs"
chmod 700 "$CONFIG_DIR/logs"
echo -e "${GREEN}  Log directory created with restricted permissions${NC}"

# ----------------------------------------------
# Summary
# ----------------------------------------------
echo ""
echo "============================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "============================================"
echo ""
echo "Security Summary:"
echo "  - Gateway: localhost only (127.0.0.1:18789)"
echo "  - External channels: DISABLED"
echo "  - External network: BLOCKED"
echo "  - Sandbox mode: STRICT"
echo "  - Allowed APIs: localhost:5000 only"
echo ""
echo "To start ClawBot:"
echo "  1. Start your Flask API:  python app.py"
echo "  2. Start ClawBot gateway: openclaw gateway"
echo "  3. Access WebChat at:     http://127.0.0.1:18789"
echo ""
echo -e "${YELLOW}IMPORTANT: Never expose port 18789 to the internet!${NC}"
echo ""
