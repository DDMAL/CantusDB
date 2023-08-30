import json
import sys
from pathlib import Path
import sys

print(f"Running: {sys.argv[0]}", file=sys.stderr)

FILE_LOCATION = "/tmp/link-checker.txt"

# If link checker doesn't have any errors exit gracefully
if not Path(FILE_LOCATION).exists():
  print("# ✅ No Broken Link")
  sys.exit(0)
else:
  print("# Broken Link found, parsing needed", file=sys.stderr)

# Loading link checker output result
with open(FILE_LOCATION) as f:
  print(f"Parsing the json data for {FILE_LOCATION}", file=sys.stderr)
  link_checker_result = json.load(f)

listOfFailure = link_checker_result['fail_map']

if not listOfFailure:
  print("# ✅ No Broken Link")
  sys.exit(0)

RealErrors = []
skipErrors = []

for failureWebSite in listOfFailure: # looping through tested websites
  for failure in listOfFailure[failureWebSite]: # looping through broken links
    errorCode = failure['status'].get('code')
    if not errorCode: # if there's a timeout its a client side issue so will not exit 1, but just print as an additional problem
      skipErrors.append(failure)
      continue

    # Find all 4xx errors
    if 400 <= errorCode and 500 > errorCode:
      RealErrors.append(failure)
    else:
      skipErrors.append(failure)

if RealErrors:
  print("# Broken Link")
  for error in RealErrors:
    print(f"* {error['url']}: {error['status']['code']}")

if skipErrors:
  print("# Skippable error Link")
  for error in skipErrors:
    print(f"* {error['url']}: {error['status']['text']}")

if RealErrors:
  sys.exit(1)