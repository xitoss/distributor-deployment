#!/usr/bin/env python3
import sys
import importlib

# Command registry: map command name -> module:function
COMMANDS = {
    "db-backup": ("backup_database", "backup_database"),
    "db-restore": ("restore_database", "restore_database"),
}

def main():
    if len(sys.argv) < 2:
        print("Usage: run.py [command]")
        print("Available commands:", ", ".join(COMMANDS.keys()))
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'")
        sys.exit(1)

    module_name, func_name = COMMANDS[cmd]
    try:
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        func()
    except Exception as e:
        print(f"Error running {cmd}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
