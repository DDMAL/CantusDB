"""Modules"""
import json
import sys
from pathlib import Path
import itertools

print(f"Running: {sys.argv[0]}", file=sys.stderr)

FILE_LOCATION = "/tmp/link-checker-output.txt"

# If link checker does not have any errors, exit gracefully
if not Path(FILE_LOCATION).exists():
    print("✅ No Broken Links Found.")
    sys.exit(0)
else:
    print("❌ Broken Links Found. Proceeding to Parsing Step.", file=sys.stderr)

# Loading link checker output result
with open(FILE_LOCATION, encoding='utf-8') as link_checker_output_file:
    print(f"Parsing the json data in {FILE_LOCATION}", file=sys.stderr)
    link_checker_results = json.load(link_checker_output_file)

list_of_failures = link_checker_results['fail_map']

if not list_of_failures:
    print("✅ No Broken Links")
    sys.exit(0)

# Flatten the list of lists into a single list -
# list_of_failures is returned as a list of lists.
all_failures = list(itertools.chain.from_iterable(list_of_failures.values()))

real_errors = []
skippable_errors = []

# Process each failure in the flattened list
for failure in all_failures:
    error_code = failure['status'].get('code')

    # Check if it's a timeout or a client-side issue
    if not error_code:
        skippable_errors.append(failure)
        continue

    # Find all 4xx errors
    if 400 <= error_code < 500:
        real_errors.append(failure)
    else:
        skippable_errors.append(failure)

if real_errors:
    print("❌ Broken Links:")
    for error in real_errors:
        print(f"* {error['url']}: {error['status']['code']}")
    print("\n")

if skippable_errors:
    print("🆗 Skippable Errors:")
    for error in skippable_errors:
        print(f"* {error['url']}: {error['status']['text']}")
    print("\n")

if real_errors:
    sys.exit(1)