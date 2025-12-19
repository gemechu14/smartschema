"""
Debug script to test survey token generation and validation
"""
from app.core.security import random_token, sha256
from app.services.survey_service import generate_survey_token

print("=" * 60)
print("SURVEY TOKEN DEBUG TEST")
print("=" * 60)

# Test 1: Generate a token
print("\n[1] Generating test token...")
raw_token, token_hash = generate_survey_token()
print(f"Raw token: {raw_token}")
print(f"Token length: {len(raw_token)}")
print(f"Token hash: {token_hash}")
print(f"Token hash length: {len(token_hash)}")

# Test 2: Verify hash matches
print("\n[2] Verifying hash...")
recomputed_hash = sha256(raw_token)
print(f"Recomputed hash: {recomputed_hash}")
print(f"Hash matches: {token_hash == recomputed_hash}")

# Test 3: Test URL encoding
print("\n[3] Testing URL encoding...")
from urllib.parse import quote, unquote
encoded = quote(raw_token)
decoded = unquote(encoded)
print(f"Original: {raw_token}")
print(f"URL encoded: {encoded}")
print(f"URL decoded: {decoded}")
print(f"Decoded matches original: {raw_token == decoded}")

# Test 4: Test hash after encoding/decoding
print("\n[4] Testing hash after encoding/decoding...")
hash_after_decode = sha256(decoded)
print(f"Hash after decode: {hash_after_decode}")
print(f"Hash still matches: {token_hash == hash_after_decode}")

print("\n" + "=" * 60)
print("If all tests pass, token generation is working correctly.")
print("The issue might be with how the token is extracted from URL fragment.")
print("=" * 60)









