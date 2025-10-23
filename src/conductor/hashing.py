import json
from typing import Any
import blake3

def blake3_hash(data: Any) -> str:
    """Generates a BLAKE3 hash for the given data.

    Args:
        data: The data to be hashed. Can be a string, bytes, or a serializable object.

    Returns:
        A hexadecimal string representation of the BLAKE3 hash.
    """
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    elif isinstance(data, bytes):
        data_bytes = data
    else:
        # Attempt to serialize to JSON if not string or bytes
        data_bytes = json.dumps(data, sort_keys=True).encode('utf-8')

    return blake3.blake3(data_bytes).hexdigest()
