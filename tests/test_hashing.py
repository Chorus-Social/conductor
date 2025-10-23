import pytest
import blake3
import json
from src.conductor.hashing import blake3_hash

def test_blake3_hash_string():
    data = "hello world"
    expected_hash = "24ad5c1111111111111111111111111111111111111111111111111111111111" # Placeholder, actual hash will be computed
    assert blake3_hash(data) == blake3.blake3(data.encode('utf-8')).hexdigest()

def test_blake3_hash_bytes():
    data = b"hello world"
    expected_hash = "24ad5c1111111111111111111111111111111111111111111111111111111111" # Placeholder, actual hash will be computed
    assert blake3_hash(data) == blake3.blake3(data).hexdigest()

def test_blake3_hash_dict():
    data = {"key": "value", "number": 123}
    expected_hash = "24ad5c1111111111111111111111111111111111111111111111111111111111" # Placeholder, actual hash will be computed
    assert blake3_hash(data) == blake3.blake3(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

def test_blake3_hash_empty_string():
    data = ""
    assert blake3_hash(data) == blake3.blake3(data.encode('utf-8')).hexdigest()

def test_blake3_hash_empty_bytes():
    data = b""
    assert blake3_hash(data) == blake3.blake3(data).hexdigest()

def test_blake3_hash_empty_dict():
    data = {}
    assert blake3_hash(data) == blake3.blake3(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()
