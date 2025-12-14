#!/bin/bash
# Integration test for Motion 5.0 hot-reload on Pi 5

set -e

PI_HOST="${1:-192.168.1.176}"
PI_USER="${2:-admin}"

echo "Testing hot-reload integration on $PI_HOST"
echo "=========================================="

# Check Motion is running
echo -n "Checking Motion status... "
ssh $PI_USER@$PI_HOST "pgrep -x motion > /dev/null" && echo "OK" || { echo "FAILED - Motion not running"; exit 1; }

# Check Motion version
echo -n "Checking Motion version... "
VERSION=$(ssh $PI_USER@$PI_HOST "motion -h 2>&1 | grep -oP 'Version \K[0-9.]+'")
echo "$VERSION"

if [[ ! "$VERSION" =~ ^5\. ]]; then
    echo "ERROR: Motion 5.0+ required, found $VERSION"
    exit 1
fi

# Test hot-reload API endpoint
echo -n "Testing hot-reload API... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?threshold=1500'" 2>/dev/null)
if echo "$RESPONSE" | grep -q "status"; then
    echo "OK"
else
    echo "FAILED - Response: $RESPONSE"
    exit 1
fi

# Test threshold change
echo -n "Testing threshold hot-reload... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?threshold=2000'")
if echo "$RESPONSE" | grep -q '"hot_reload": true\|"hot_reload":true'; then
    echo "OK"
else
    echo "WARNING - Response: $RESPONSE"
fi

# Test width change (should fail/require restart)
echo -n "Testing width (should require restart)... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?width=1280'")
if echo "$RESPONSE" | grep -q '"hot_reload": false\|"hot_reload":false\|requires\|restart'; then
    echo "OK (correctly rejected)"
else
    echo "WARNING - Response: $RESPONSE"
fi

# Test text_left (should be hot-reloadable)
echo -n "Testing text_left hot-reload... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?text_left=TestCamera'")
if echo "$RESPONSE" | grep -q '"hot_reload": true\|"hot_reload":true\|status.*ok'; then
    echo "OK"
else
    echo "WARNING - Response: $RESPONSE"
fi

# Test stream_quality (should be hot-reloadable)
echo -n "Testing stream_quality hot-reload... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?stream_quality=75'")
if echo "$RESPONSE" | grep -q '"hot_reload": true\|"hot_reload":true\|status.*ok'; then
    echo "OK"
else
    echo "WARNING - Response: $RESPONSE"
fi

# Reset threshold
ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?threshold=1500'" > /dev/null

echo ""
echo "=========================================="
echo "Integration tests completed"
