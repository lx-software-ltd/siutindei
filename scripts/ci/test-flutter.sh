#!/usr/bin/env bash
# Run Flutter tests for every app that has a pubspec.
set -euo pipefail
sudo apt-get update && sudo apt-get install -y libsqlite3-0 libsqlite3-dev
python3 -c 'from pathlib import Path; p=Path("apps/siutindei_app/pubspec.yaml"); t=p.read_text(encoding="utf-8"); h="\nhooks:\n  user_defines:\n    sqlite3:\n      source: system\n"; p.write_text(t+h, encoding="utf-8") if "user_defines:" not in t else None'
shopt -s globstar nullglob
for spec in apps/*/pubspec.yaml; do
  dir="$(dirname "$spec")"
  test_files=("$dir"/test/**/*_test.dart)
  if [ "${#test_files[@]}" -eq 0 ]; then
    echo "ERROR: $dir has a pubspec.yaml but no test/**/*_test.dart files"
    exit 1
  fi
  echo "Testing Flutter in $dir"
  (cd "$dir" && flutter pub get && flutter test)
done
