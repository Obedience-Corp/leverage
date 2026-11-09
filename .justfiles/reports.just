root := justfile_directory()

# Validate real report hashes, exact CSV values, accounting and portable metadata.
check:
    python3 {{root}}/scripts/check_reports.py
