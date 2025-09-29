#!/usr/bin/env python3
"""
Simplified Preflight Script
- verifies license
- prompts user only for essential DB + superuser credentials + domain
- generates secret key automatically
- writes full .env file with all required variables
"""

import os
import json
import base64
from pathlib import Path
from getpass import getpass
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import secrets

HERE = Path.cwd()
ENV_FILE = HERE / ".env"


def load_public_key(path: Path):
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def verify_license(license_path: Path, public_key):
    data = json.loads(license_path.read_text(encoding="utf-8"))
    payload = data["payload"]
    signature = base64.b64decode(data["signature"])
    message = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    public_key.verify(
        signature,
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return payload


def prompt_values(payload: dict):
    print("\n=== Configure Your Application ===\n")

    # --- domain ---
    domain = input("Main domain (without www, e.g. domain.com) [example.com]: ").strip() or "example.com"

    # --- db ---
    db_user = input("Database username [distributor]: ").strip() or "distributor"
    db_pass = getpass("Database password [changeme]: ") or "changeme"

    # --- superuser ---
    print("\n--- Superuser (Admin) account ---")
    su_user = input(f"Username [{payload.get('admin_username','admin')}]: ") \
              or payload.get("admin_username", "admin")
    su_email = input(f"Email [{payload.get('admin_email','admin@example.com')}]: ") \
               or payload.get("admin_email", "admin@example.com")
    su_pass = getpass("Password [changeme]: ") or "changeme"

    return {
        "DOMAIN": domain,
        "DB_USER": db_user,
        "DB_PASSWORD": db_pass,
        "DJANGO_SUPERUSER_USERNAME": su_user,
        "DJANGO_SUPERUSER_EMAIL": su_email,
        "DJANGO_SUPERUSER_PASSWORD": su_pass,
    }


def generate_secret():
    return secrets.token_urlsafe(50)


def write_env(payload, values):
    # auto-expand allowed hosts
    domain = values["DOMAIN"]
    allowed_hosts = f"{domain},www.{domain}"

    env_vars = {
        "DJANGO_SETTINGS_MODULE": "distributor.settings",
        # --- DB ---
        "DB_ENGINE": "django.db.backends.postgresql",
        "DB_NAME": "distributor_db",
        "DB_USER": values["DB_USER"],
        "DB_PASSWORD": values["DB_PASSWORD"],
        "DB_HOST": "db",
        "DB_PORT": "5432",

        # --- Django ---
        "DJANGO_SUPERUSER_USERNAME": values["DJANGO_SUPERUSER_USERNAME"],
        "DJANGO_SUPERUSER_EMAIL": values["DJANGO_SUPERUSER_EMAIL"],
        "DJANGO_SUPERUSER_PASSWORD": values["DJANGO_SUPERUSER_PASSWORD"],
        "SECRET_KEY": generate_secret(),
        "ALLOWED_HOSTS": allowed_hosts,
        "DJANGO_DEBUG": "False",

        # --- License & domain info ---
        "LICENSE_FILE": "/app/license.pem",
        "LETSENCRYPT_EMAIL": payload.get("contact_email", "ops@example.com"),
        "DOMAIN": domain,
    }

    ENV_FILE.write_text(
        "\n".join(f"{k}={v}" for k, v in env_vars.items()) + "\n",
        encoding="utf-8"
    )
    print(f"\n✅ .env file created at {ENV_FILE}")


def main():
    print("=== Preflight Setup ===")

    license_file = HERE / "license.pem"
    pub_key_file = HERE / "license_public.pem"

    if not pub_key_file.exists() or not license_file.exists():
        print("ERROR: license_public.pem and license.pem must be present in this folder.")
        return

    # verify license
    try:
        public_key = load_public_key(pub_key_file)
        payload = verify_license(license_file, public_key)
        print("✅ License verified for:", payload.get("company", "Unknown company"))
    except Exception as e:
        print("❌ License verification failed:", str(e))
        return

    # ask only for essential values
    values = prompt_values(payload)

    # write full .env
    write_env(payload, values)

    print("\nNext steps:")
    print("1) Review and adjust the .env file if needed.")
    print("      The system already includes both domain.com and www.domain.com in ALLOWED_HOSTS.")
    print("2) Run: docker compose up -d")
    print("   This will pull the app image and start everything.")
    print("3) Login with your superuser credentials to configure your company.\n")


if __name__ == "__main__":
    main()
