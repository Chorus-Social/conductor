import argparse
import os
import nacl.signing
import nacl.encoding

def generate_keypair(output_path: str):
    """
    Generates an Ed25519 keypair and saves the private key to a file.
    The public key is derived from the private key.
    """
    private_key = nacl.signing.SigningKey.generate()
    public_key = private_key.verify_key

    # Ensure the output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save the private key in a hex-encoded format
    with open(output_path, 'wb') as f:
        f.write(private_key.encode(encoder=nacl.encoding.HexEncoder))
    
    print(f"Private key saved to: {output_path}")
    print(f"Public key (hex): {public_key.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')}")
    print("Keep your private key secure!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an Ed25519 keypair for a Chorus validator.")
    parser.add_argument(
        "--output",
        type=str,
        default="./keys/validator_key.pem",
        help="Path to save the private key file (e.g., ./keys/validator_key.pem)"
    )
    args = parser.parse_args()

    generate_keypair(args.output)
