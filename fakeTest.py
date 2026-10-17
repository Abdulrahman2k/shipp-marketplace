
# SHIPP — Validate Bed image files in Unity Catalog
# READ ONLY

volume_path = (
    "/Volumes/bootcamp_students/shipp_bronze/listing_images/"
    "a2c97986-ab61-47b4-b577-b28d90271ee8"
)

# Expected file sizes from Lakebase listing_files
expected = {
    "81d0f601-2ae4-4d20-bff5-d5a06bc5069c": 656389,
    "354a0932-7c4e-4fb6-a623-fdee6c4eb13c": 1745404,
    "5d579a89-6497-48b3-9c0a-2c454d3d2499": 1988219,
}

files = dbutils.fs.ls(volume_path)

print("=== ACTUAL VOLUME FILES ===")

found = {}

for file in files:
    print(f"File: {file.name}")
    print(f"Size: {file.size} bytes")
    print("---")

    file_id = file.name.split("_", 1)[0]
    found[file_id] = file.size

print(f"\nTotal files found: {len(files)}")

print("\n=== VALIDATION RESULTS ===")

all_passed = True

for file_id, expected_size in expected.items():
    actual_size = found.get(file_id)

    if actual_size == expected_size:
        print(f"PASS — {file_id}")
    else:
        all_passed = False
        print(
            f"FAIL — {file_id}: "
            f"expected {expected_size}, got {actual_size}"
        )

if all_passed:
    print("\nPASS — All 3 Bed image files exist and sizes match.")
else:
    print("\nFAIL — Investigate missing files or size mismatches.")
