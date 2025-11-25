# main.py

from logistech.controller import LogiMaster
from logistech.models import Package
from db.setup import initialize_db

# ensure a clean slate for every run
initialize_db()
# Get the single controller instance
wm = LogiMaster()

print("\n--- 1. SETUP PHASE: Ingesting & Assigning Packages ---")
# Reset DB and fill bins (same as previous successful run, but with new packages)
wm.ingest_package(Package(tracking_id="P001", size=11.0, destination="10001", is_fragile=False)) 
wm.ingest_package(Package(tracking_id="P002", size=4.0, destination="20002", is_fragile=True)) 
wm.ingest_package(Package(tracking_id="P003", size=16.0, destination="30003", is_fragile=False)) 
wm.process_next_package() # P001 -> Bin 201 (15.0)
wm.process_next_package() # P002 -> Bin 101 (5.0)
wm.process_next_package() # P003 -> Bin 202 (20.0)

# Inject packages for the Backtracking test (all destined for '40004' for the first truck)
wm.ingest_package(Package(tracking_id="P005", size=5.0, destination="40004", is_fragile=False)) # Bin 102
wm.ingest_package(Package(tracking_id="P006", size=10.0, destination="40004", is_fragile=False)) # Bin 201 (fails)
wm.ingest_package(Package(tracking_id="P007", size=25.0, destination="40004", is_fragile=False)) # Bin 301
wm.process_next_package() # P005 -> Bin 102 (Cap 10.0)
wm.process_next_package() # P006 (10.0) -> Fails Best Fit (no 10.0+ space)
wm.process_next_package() # P007 -> Bin 301 (Cap 50.0)

# --- 2. BACKTRACKING TEST (Module B) ---

# Test 1: Truck 1 (Capacity 500.0) filtering for ZIP '40004'.
# Candidates in Bins for ZIP 40004: P005 (5.0), P007 (25.0)
# Optimal load should be P005 + P007 = 30.0
wm.prepare_shipment(truck_id=1, zip_code_filter='40004')

# Test 2: Truck 2 (Capacity 1200.0) filtering for ZIP '10001'.
# Candidate in Bins for ZIP 10001: P001 (11.0)
wm.prepare_shipment(truck_id=2, zip_code_filter='10001')


# --- 3. FINAL STATE CHECK ---
print("\n--- FINAL SYSTEM STATUS AFTER SHIPMENT ---")
print(f"LIFO Loading Stack: {wm.loading_stack}")

# Check current bin occupancy again (P005, P007, P001 should be removed from bins)
print("\nFinal In-Memory Bin Occupancy (Loaded packages should be gone):")
for bin_obj in wm.bin_inventory:
    if bin_obj.occupancy > 0.0:
        print(f"  {bin_obj}")