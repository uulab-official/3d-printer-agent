# Printer LAN test certificates

These two self-signed RSA certificates and private keys were generated locally on
2026-11-16 with `openssl req -x509 -newkey rsa:2048 -nodes -days 36500` solely for the
fake loopback TLS broker in `tests/test_printer_lan.py`. They identify no real printer,
are not trusted by any client configuration, and must never be used outside tests.

- `printer-cert.pem` / `printer-key.pem`: the expected fake printer.
- `other-cert.pem` / `other-key.pem`: a different endpoint used to prove that a pinned
  certificate mismatch stops before the access code is sent.
