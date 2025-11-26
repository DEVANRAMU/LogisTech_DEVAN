# app.py
from flask import Flask, jsonify, request
from collections import deque
from logistech.controller import LogiMaster
from logistech.models import Package
from db.setup import initialize_db

# --- INITIAL SETUP ---
initialize_db() # Ensure a clean DB is loaded on startup
app = Flask(__name__)
wm = LogiMaster()

# --- HELPER FUNCTIONS ---

def _package_to_dict(package_data):
    """Converts a database Package record to a JSON-friendly dict."""
    return {
        'tracking_id': package_data.tracking_id,
        'size': package_data.package_size,
        'destination_zip': package_data.destination_zip,
        'is_fragile': package_data.is_fragile,
        'current_bin_id': package_data.current_bin_id,
        'current_truck_id': package_data.current_truck_id
    }

# --- API ENDPOINTS ---

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns the current state of the warehouse system."""
    bin_status = [str(b) for b in wm.bin_inventory]
    
    return jsonify({
        "status": "Operational",
        "conveyor_queue_size": len(wm.conveyor_queue),
        "loading_stack_size": len(wm.loading_stack),
        "bin_inventory": bin_status,
        "truck_load_order": list(wm.loading_stack) # LIFO stack contents
    })

@app.route('/api/ingest', methods=['POST'])
def ingest_and_assign():
    """
    Ingests a new package and immediately processes it through Binary Search.
    Expected JSON: {"tracking_id": "PXXX", "size": 15.0, "destination": "10001", "is_fragile": false}
    """
    data = request.get_json()
    
    # 1. Ingest Package
    new_package = Package(
        tracking_id=data['tracking_id'],
        size=data['size'],
        destination=data['destination'],
        is_fragile=data.get('is_fragile', False)
    )
    wm.ingest_package(new_package)
    
    # 2. Process (Binary Search Assignment)
    assignment_result = wm.process_next_package()

    # 3. Fetch final state of the package from DB
    package_db_state = wm.get_package_status(data['tracking_id'])
    
    if "ASSIGNED" in assignment_result:
        return jsonify({
            "status": "Success",
            "message": assignment_result,
            "package": _package_to_dict(package_db_state)
        }), 200
    else:
        return jsonify({
            "status": "Failure",
            "message": assignment_result
        }), 400

@app.route('/api/shipment/prepare', methods=['POST'])
def prepare_shipment_api():
    """
    Triggers the Backtracking algorithm to load a truck.
    Expected JSON: {"truck_id": 1, "zip_code": "40004"}
    """
    data = request.get_json()
    truck_id = data.get('truck_id')
    zip_code = data.get('zip_code')
    
    if not truck_id or not zip_code:
        return jsonify({"status": "error", "message": "Missing truck_id or zip_code"}), 400
        
    # The LogiMaster method handles the core logic (Backtracking, DB update, LIFO push)
    wm.prepare_shipment(truck_id, zip_code)
    
    # Simple check on the LIFO stack to confirm packages were added
    packages_loaded = [p for p in wm.loading_stack if wm.loading_stack.index(p) >= len(wm.loading_stack) - 1] # Simple check to see recent additions
    
    return jsonify({
        "status": "Shipment Prepared",
        "truck_id": truck_id,
        "zip_code_filter": zip_code,
        "loading_stack_size": len(wm.loading_stack),
        "message": f"Backtracking completed for Truck {truck_id}. Check status endpoint for details."
    })

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)