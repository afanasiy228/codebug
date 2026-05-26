# Key Handling

- Private deploy keys must not live in the project working tree.
- Use secret storage (`/etc/secrets/...`, CI secrets, or vault).
- If a private key was present in this directory, it must be considered compromised and rotated.
