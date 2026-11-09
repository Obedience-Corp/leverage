root := justfile_directory()

# Validate runtime syntax and Bash entry point without creating host caches.
syntax:
    python3 -c 'import ast,pathlib; [ast.parse(p.read_text(),filename=str(p)) for folder in ("skills", "scripts") for p in (pathlib.Path("{{root}}")/folder).rglob("*.py")]'
    bash -n {{root}}/skills/leverage/scripts/ensure-festival.sh
