"""Read non-secret diagnostics from the isolated Listkeeper test container."""

import argparse
import json
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("container")
arguments = parser.parse_args()
metadata = json.loads(subprocess.check_output(["docker", "inspect", arguments.container]))[0]
if metadata["Config"]["Labels"].get("io.pax0r.listkeeper.test-instance") != "true":
    raise SystemExit("Refusing to inspect a non-test container")

for filename in ("/config/.storage/core.config_entries", "/config/.shopping_list.json"):
    result = subprocess.run(
        ["docker", "exec", arguments.container, "cat", filename],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print(filename, "unavailable")
        continue
    value = json.loads(result.stdout)
    if filename.endswith("core.config_entries"):
        print("Config entries:", [entry["domain"] for entry in value["data"]["entries"]])
    else:
        print("Native items:", value)

query = """import sqlite3
connection = sqlite3.connect('file:/config/pax0r_listkeeper.db?mode=ro', uri=True)
for table in ('todo_items', 'deduplication_operations'):
    rows = connection.execute('SELECT * FROM pax0r_listkeeper_' + table).fetchall()
    print(table, rows)
connection.close()
"""
subprocess.run(["docker", "exec", arguments.container, "python", "-c", query], check=True)
