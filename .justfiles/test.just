root := justfile_directory()
image := 'leverage-tests:local'

# Build the disposable Linux runtime; all filesystem tests run here.
image:
    docker build -t {{image}} -f {{root}}/tests/Dockerfile {{root}}

# Run all deterministic tests against the installed skill copy.
all: image
    docker run --rm --network none -v {{root}}:/src:ro {{image}} python3 tests/test_skill.py

# Download/verify the official suite and report on a new unregistered Git repo.
live: image
    docker run --rm -v {{root}}:/src:ro {{image}} bash tests/live.sh
