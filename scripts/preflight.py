#!/usr/bin/env python3
"""
Simplified Preflight Script
- verifies license
- prompts user only for essential DB + superuser credentials + domain
- generates secret key automatically
- generates agent key, set agent port for system operations
- writes full .env file with all required variables
"""

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

def generate_username(company_name):
    name = (company_name or "admin")
    return name.strip().lower().replace(" ", "_")

def generate_password(company_name, issued):
    part_one = (company_name or "admin").strip().lower().replace(" ", "_")
    issued_str = str(issued or "")
    # safe slicing: if issued shorter than 5 chars, use empty suffix
    part_two = issued_str[4:] if len(issued_str) > 4 else ""
    return f"{part_one.title()}{part_two}"


def prompt_values(payload: dict):
    print("\n=== Configure Your Application ===\n")
    # default values
    default_domain = payload.get("domain")
    default_user_name = generate_username(payload.get("company", "admin"))
    default_password = generate_password(
        company_name=payload.get("company", "admin"),
        issued=payload.get("issued", "2025"),
    )
    default_email = payload.get("email")

    # --- domain and contact ---
    domain = input(f"Main domain (without www, e.g. domain.com) [{default_domain}]: ").strip() or default_domain

    # --- db ---
    db_user = input("Database username [distributor]: ").strip() or "distributor"
    db_pass = getpass(f"Database password [{default_password}]: ") or default_password

    # --- superuser ---
    print("\n--- Superuser (Admin) account ---")
    su_user = input(f"Username [{default_user_name}]: ") or default_user_name
    su_email = input(f"Email [{default_email}]: ") or default_email
    su_pass = getpass(f"Password [{default_password}]: ") or default_password

    # SSL
    contact_email = input(f"Let's Encrypt contact email [{default_email}]: ").strip() or default_email

    return {
        "DOMAIN": domain,
        "CONTACT_EMAIL": contact_email,
        "DB_USER": db_user,
        "DB_PASSWORD": db_pass,
        "DJANGO_SUPERUSER_USERNAME": su_user,
        "DJANGO_SUPERUSER_EMAIL": su_email,
        "DJANGO_SUPERUSER_PASSWORD": su_pass,
    }


def generate_secret():
    return secrets.token_urlsafe(50)


def write_env(values):
    # auto-expand allowed hosts
    domain = values["DOMAIN"]
    allowed_hosts = f"{domain},www.{domain},127.0.0.1,localhost"

    env_vars = {
        "DJANGO_SETTINGS_MODULE": "distributor.settings",

        # --- DB ---
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

        # --- to run agent scripts ----
        "AGENT_HOST": "0.0.0.0",
        "AGENT_KEY": generate_secret(),
        "AGENT_PORT": "6001",
        "POSTGRES_DB": "distributor_db",
        "POSTGRES_USER": values["DB_USER"],
        "POSTGRES_PASSWORD": values["DB_PASSWORD"],

        # --- License & domain info ---
        "LETSENCRYPT_EMAIL": values["CONTACT_EMAIL"],
        "DOMAIN": domain,
        "DRY_RUN": "False",
        "DRY_WEB_PORT": "9560",
    }

    ENV_FILE.write_text(
        "\n".join(f"{k}={v}" for k, v in env_vars.items()) + "\n",
        encoding="utf-8"
    )
    print(f"\n .env file created at {ENV_FILE}")


def main():
    print("=== Preflight Setup ===")

    license_file = HERE / "license/license.pem"
    pub_key_file = HERE / "license/license_public.pem"

    if not pub_key_file.exists() or not license_file.exists():
        print("ERROR: license_public.pem and license.pem must be present in this folder.")
        return

    # verify license
    try:
        public_key = load_public_key(pub_key_file)
        payload = verify_license(license_file, public_key)
        print("License verified for:", payload.get("company", "Unknown company"))
    except Exception as e:
        print("License verification failed:", str(e))
        return
    
    if ENV_FILE.exists():
        print(f"{ENV_FILE} already exists. Overwrite? [y/N]: ", end="")
        if input().strip().lower() != "y":
            print("Aborted.")
            return

    # ask only for essential values
    values = prompt_values(payload)

    # write full .env
    write_env(values)

    print("\nNext steps:")
    print("1) Review and adjust the .env file if needed.")
    print("      The system already includes both domain.com and www.domain.com in ALLOWED_HOSTS.")
    print("2) Run: docker compose up -d --build")
    print("   This will pull the app image and start everything.")
    print("3) Login with your superuser credentials to configure your company.\n")


if __name__ == "__main__":
    main()
