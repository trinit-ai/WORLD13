"""
13TMOS Pack Auth — Passphrase-Based Access Control

Minimal, auditable authentication for pack-level access.
Passphrases are never stored in plaintext. bcrypt hash only.

Usage:
    python engine/pack_auth.py --set-hash protocols/private/robert_c_ventura/header.yaml
    python engine/pack_auth.py --verify protocols/private/robert_c_ventura/header.yaml
"""
import bcrypt
import getpass


class PackAuthError(Exception):
    """Raised when pack authentication fails."""
    pass


def hash_passphrase(plaintext: str) -> str:
    """Hash a passphrase using bcrypt. Returns the hash string."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plaintext.encode(), salt).decode()


def verify_passphrase(plaintext: str, stored_hash: str) -> bool:
    """Verify a passphrase against a stored bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode(), stored_hash.encode())


def prompt_and_verify(stored_hash: str, prompt: str = "Passphrase: ") -> bool:
    """
    Prompt for passphrase at terminal (hidden input).
    Returns True if correct, False otherwise.
    Allows 3 attempts before returning False.
    """
    for attempt in range(3):
        entered = getpass.getpass(prompt)
        if verify_passphrase(entered, stored_hash):
            return True
        if attempt < 2:
            print("Incorrect. Try again.")
    print("Access denied.")
    return False


def set_passphrase_interactive() -> str:
    """
    Prompt user to set a new passphrase (hidden input, confirmed).
    Returns the bcrypt hash. Plaintext is never returned or stored.
    """
    while True:
        p1 = getpass.getpass("Set passphrase: ")
        if not p1:
            print("Passphrase cannot be empty. Try again.")
            continue
        p2 = getpass.getpass("Confirm passphrase: ")
        if p1 == p2:
            hashed = hash_passphrase(p1)
            del p1, p2
            return hashed
        print("Passphrases do not match. Try again.")


def reset_passphrase_interactive(stored_hash: str) -> str:
    """
    Prompt for current passphrase, then set a new one.
    Returns the new bcrypt hash, or raises PackAuthError if current fails.
    """
    entered = getpass.getpass("Current passphrase: ")
    if not verify_passphrase(entered, stored_hash):
        raise PackAuthError("Current passphrase incorrect.")
    del entered
    return set_passphrase_interactive()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python engine/pack_auth.py --set-hash <header.yaml path>")
        print("  python engine/pack_auth.py --verify <header.yaml path>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--set-hash" and len(sys.argv) == 3:
        import yaml
        path = sys.argv[2]
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if not data or "auth" not in data:
            print(f"Error: {path} has no 'auth' section")
            sys.exit(1)

        hashed = set_passphrase_interactive()
        data["auth"]["hash"] = hashed

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        print(f"Hash written to {path}")

    elif cmd == "--verify" and len(sys.argv) == 3:
        import yaml
        path = sys.argv[2]
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        stored_hash = data.get("auth", {}).get("hash", "")
        if not stored_hash or stored_hash == "SET_ON_FIRST_RUN":
            print("No hash set yet. Run --set-hash first.")
            sys.exit(1)

        if prompt_and_verify(stored_hash):
            print("Access granted.")
        else:
            sys.exit(1)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
