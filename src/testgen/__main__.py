"""Allow running testgen as a module: python -m testgen"""

from .cli import cli

if __name__ == "__main__":
    cli()
