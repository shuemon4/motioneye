#!/usr/bin/env python3
"""
Test script to validate v2 signature implementation matches between Python and JavaScript.

This script generates test signatures using the Python implementation and provides
the JavaScript equivalent to verify they match.
"""

import hashlib
import hmac
import urllib.parse
import time


def compute_signature_v2(method, path, body, key, timestamp):
    """
    Python implementation from motioneye/utils/__init__.py
    """
    _SIGNATURE_REGEX_PATTERN = r'[^a-zA-Z0-9/?_.=&{}\[\]":, -]'
    import re
    _SIGNATURE_REGEX = re.compile(_SIGNATURE_REGEX_PATTERN)

    parts = list(urllib.parse.urlsplit(path))
    query = [
        q
        for q in urllib.parse.parse_qsl(parts[3], keep_blank_values=True)
        if (q[0] != '_signature' and q[0] != '_timestamp' and q[0] != '_csrf')
    ]
    query.sort(key=lambda q: q[0])
    query = [(n, urllib.parse.quote(v, safe="!'()*~")) for (n, v) in query]
    query = '&'.join([(q[0] + '=' + q[1]) for q in query])
    parts[0] = parts[1] = ''
    parts[3] = query
    path = urllib.parse.urlunsplit(parts)
    path = _SIGNATURE_REGEX.sub('-', path)

    try:
        body_str = body.decode('utf-8')
    except:
        body_str = None

    if body_str and body_str.startswith('---'):
        body_str = None  # file attachment

    body_str = body_str and _SIGNATURE_REGEX.sub('-', body_str)

    # Include timestamp in the message for replay protection
    message = f'{method}:{path}:{timestamp}:{body_str or ""}'

    # Use HMAC-SHA256 with the key (password hash)
    return hmac.new(
        key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().lower()


def test_signature(method, url, password, timestamp=None):
    """
    Test signature generation for a given request.
    """
    if timestamp is None:
        timestamp = int(time.time())

    # Compute password hash (SHA1 of password)
    password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()

    # Compute v2 signature
    signature = compute_signature_v2(method, url, b'', password_hash, timestamp)
    full_signature = f'v2:{signature}'

    print(f"\n{'='*70}")
    print(f"Test Case: {method} {url}")
    print(f"{'='*70}")
    print(f"Password: {password}")
    print(f"Password Hash (SHA1): {password_hash}")
    print(f"Timestamp: {timestamp}")
    print(f"Signature: {full_signature}")
    print(f"\nJavaScript Test Code:")
    print(f"-----")
    print(f"window.passwordHash = '{password_hash}';")
    print(f"var url = '{url}';")
    print(f"var sigData = computeSignature('{method}', url, '');")
    print(f"console.log('JS Signature:', sigData.signature);")
    print(f"console.log('Python Expected:', '{full_signature}');")
    print(f"console.log('Match:', sigData.signature === '{full_signature}');")
    print(f"-----\n")

    return full_signature


def test_encoding():
    """
    Test URL encoding matches between Python and JavaScript.
    """
    print(f"\n{'='*70}")
    print("URL Encoding Parity Test")
    print(f"{'='*70}\n")

    test_cases = [
        ('hello world', 'hello%20world'),
        ("test!'()*~", "test!'()*~"),  # Safe chars should NOT be encoded
        ('a=b&c=d', 'a%3Db%26c%3Dd'),
        ('user@example.com', 'user%40example.com'),
    ]

    for input_str, expected in test_cases:
        # Python encoding
        python_result = urllib.parse.quote(input_str, safe="!'()*~")

        match = python_result == expected
        status = "✓ PASS" if match else "✗ FAIL"

        print(f"Input: '{input_str}'")
        print(f"  Python:   '{python_result}'")
        print(f"  Expected: '{expected}'")
        print(f"  Status:   {status}\n")


if __name__ == '__main__':
    print("MotionEye V2 Signature Test Suite")
    print("="*70)

    # Test 1: URL encoding parity
    test_encoding()

    # Test 2: Simple GET request
    test_signature(
        'GET',
        '/config/list/?_=1735059000000&_username=admin',
        'wwadmin'
    )

    # Test 3: GET request with special characters
    test_signature(
        'GET',
        '/config/list/?_=1735059000000&_username=admin&test=hello world',
        'wwadmin'
    )

    # Test 4: Empty password (common default)
    test_signature(
        'GET',
        '/login/?_=1735059000000&_username=admin&_login=true',
        ''  # Empty password
    )

    # Test 5: POST request
    test_signature(
        'POST',
        '/config/1/set/?_=1735059000000&_username=admin',
        'wwadmin'
    )

    print("\n" + "="*70)
    print("Testing Instructions:")
    print("="*70)
    print("1. Open MotionEye in browser")
    print("2. Open browser console (F12)")
    print("3. Copy and run each JavaScript test block above")
    print("4. Verify 'Match: true' for all tests")
    print("5. If any test fails, debug the mismatch using the detailed output")
    print("="*70 + "\n")
