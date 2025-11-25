# logistech/controller.py

from collections import deque
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from logistech.models import StorageBin, Package
# Import all required database models from setup.py
from db.setup import DATABASE_URL, Base, StorageBin as DBSQLABin, ShipmentLog, Package as DBSQLAPackage 
from logistech.algorithms import find_optimal_shipment 
from db.setup import DeliveryTruck as DBSQLATruck
from sqlalchemy.pool import NullPool # Add this line to the imports section

# --- C. The "Control Tower" (Singleton Pattern) ---
class LogiMaster:
    """
    The Warehouse Controller: Implemented as a Singleton.
    It is the single source of truth for inventory space and truck schedules.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization if already done
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        print("Initializing LogiMaster: Connecting DB and loading configuration.")
        
        # 1. Database Connection
        #self.engine = create_engine(DATABASE_URL)
        # CRUCIAL FIX: Disable connection pooling for SQLite to prevent 'database is locked' errors
        self.engine = create_engine(DATABASE_URL, poolclass=NullPool)
        Base.metadata.bind = self.engine
        self.DBSession = sessionmaker(bind=self.engine)
        
        # 2. Attributes (as required by HLD)
        self.bin_inventory = self._load_and_sort_bins() # Sorted List
        self.conveyor_queue = deque()                  # FIFO Queue
        self.loading_stack = []                        # LIFO Stack (Truck Loading)
        
        self._initialized = True
        print(f"LogiMaster initialized with {len(self.bin_inventory)} bins.")


    def _load_and_sort_bins(self) -> list[StorageBin]:
        """
        Loads all bin configurations from the SQL database and sorts them
        by capacity (max_capacity) for efficient Binary Search.
        """
        session = self.DBSession()
        try:
            sql_bins = session.query(DBSQLABin).all()
            
            oop_bins = [
                StorageBin(
                    bin_id=b.bin_id, 
                    capacity=b.max_capacity, 
                    location_code=b.location_code, 
                    current_occupancy=b.current_occupancy
                )
                for b in sql_bins
            ]
            
            oop_bins.sort()
            return oop_bins
            
        except Exception as e:
            print(f"Error loading bins: {e}")
            return []
        finally:
            session.close()
            
    # ====================================================================
    # MODULE A: BINARY SEARCH (O(log N)) - The "Best-Fit" Selector
    # ====================================================================

    def find_best_fit_bin(self, package_size: float) -> StorageBin | None:
        """
        Uses Binary Search (O(log N)) to find the smallest StorageBin 
        with capacity >= package_size AND sufficient remaining capacity.
        """
        bins = self.bin_inventory
        low = 0
        high = len(bins) - 1
        best_fit_bin = None
        
        while low <= high:
            mid = (low + high) // 2
            current_bin = bins[mid]
            
            # Check if this bin works (capacity is large enough)
            if current_bin.capacity >= package_size:
                best_fit_bin = current_bin
                # Try to find a smaller bin that also works (move left)
                high = mid - 1
            else:
                # Bin is too small, look right
                low = mid + 1
        
        # Final check: The chosen bin must also have available space
        if best_fit_bin and best_fit_bin.get_remaining_capacity() >= package_size:
            return best_fit_bin
        
        return None 

    # ====================================================================
    # INGESTION LOGIC (FIFO Queue) & SQL Auditor (Module C)
    # ====================================================================

    def _log_shipment(self, tracking_id, size, status, bin_id=None, truck_id=None):
        """Helper to create a new ShipmentLog record (Auditor)."""
        session = self.DBSession()
        try:
            log_entry = ShipmentLog(
                tracking_id=tracking_id,
                package_size=size,
                status=status,
                bin_id=bin_id,
                truck_id=truck_id
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"!! AUDITOR ERROR: Failed to log shipment status: {e}")
        finally:
            session.close()

    def _update_db_assignment(self, package: Package, bin_obj: StorageBin):
        """Helper to update the current location of the package and bin occupancy."""
        session = self.DBSession()
        try:
            # 1. Update the Bin's occupancy in the 'storage_bins' table
            sql_bin = session.query(DBSQLABin).filter_by(bin_id=bin_obj.bin_id).one()
            sql_bin.current_occupancy = bin_obj.occupancy

            # 2. Update the Package's location (and create package record if new)
            sql_package = session.query(DBSQLAPackage).filter_by(tracking_id=package.tracking_id).first()
            if not sql_package:
                sql_package = DBSQLAPackage(
                    tracking_id=package.tracking_id,
                    package_size=package.size,
                    destination_zip=package.destination,
                    is_fragile=package.is_fragile
                )
                session.add(sql_package)
                
            sql_package.current_bin_id = bin_obj.bin_id
            sql_package.current_truck_id = None # Ensure package is not marked as being on a truck

            session.commit()
        except Exception as e:
            session.rollback()
            raise e # Re-raise to trigger rollback in process_next_package
        finally:
            session.close()

    def ingest_package(self, package: Package):
        """
        Ingestion: Adds a new package to the FIFO Conveyor Belt Queue.
        """
        self.conveyor_queue.append(package)
        print(f"-> INGESTED: Package {package.tracking_id} added to the Conveyor Queue.")
        self._log_shipment(package.tracking_id, package.size, 'INGESTED')

    def process_next_package(self):
        """
        Processes the package at the front of the FIFO queue.
        Finds the Best-Fit bin, assigns it, and updates the database.
        """
        if not self.conveyor_queue:
            return

        package = self.conveyor_queue.popleft()
        print(f"\n<- PROCESSING: Package {package.tracking_id} (Size: {package.size})")

        # 1. Find the Best-Fit Bin using O(log N) search
        best_bin = self.find_best_fit_bin(package.size)

        if best_bin:
            try:
                # 2. Update in-memory state
                best_bin.occupy_space(package.size)
                
                # 3. Update Package and Bin in SQL (Persistence)
                self._update_db_assignment(package, best_bin)
                
                print(f"   ASSIGNED: Found Best-Fit Bin {best_bin.bin_id} at {best_bin.location_code}.")
                print(f"   Bin Occupancy: {best_bin.occupancy:.1f}/{best_bin.capacity:.1f}")
                
                # 4. Log the assignment (Auditor requirement)
                self._log_shipment(package.tracking_id, package.size, 'BIN_ASSIGNED', bin_id=best_bin.bin_id)

            except Exception as e:
                # Catch crash scenario, rollback allocation, put package back (Module C requirement)
                print(f"   !! ERROR: Assignment failed due to {e}. Rolling back allocation.")
                best_bin.free_space(package.size) 
                self.conveyor_queue.appendleft(package) 
                
        else:
            print(f"   !! FAILURE: No suitable bin found for Package {package.tracking_id}.")
    
    def get_packages_in_bin(self, bin_id: int) -> list[Package]:
        """Helper to retrieve all Package objects currently stored in a given bin."""
        session = self.DBSession()
        try:
            # 1. Get the SQL package records
            sql_packages = session.query(DBSQLAPackage).filter_by(current_bin_id=bin_id).all()
            
            # 2. Convert to in-memory OOP Package objects
            oop_packages = [
                Package(
                    tracking_id=p.tracking_id,
                    size=p.package_size,
                    destination=p.destination_zip,
                    is_fragile=p.is_fragile
                )
                for p in sql_packages
            ]
            return oop_packages
        finally:
            session.close()

    def prepare_shipment(self, truck_id: int, zip_code_filter: str):
        """
        Module B: Finds the optimal cargo load for a truck using Backtracking.
        1. Queries all packages destined for the target ZIP.
        2. Calls the Backtracking algorithm.
        3. Loads packages onto the LIFO Stack and updates the DB.
        """
        print(f"\n--- PREPARING SHIPMENT for TRUCK {truck_id} (ZIP: {zip_code_filter}) ---")
        session = self.DBSession()
        
        try:
            # 1. Get Truck Capacity
            sql_truck = session.query(DBSQLATruck).filter_by(truck_id=truck_id).one()
            truck_capacity = sql_truck.max_capacity
            
            # 2. Query Candidate Packages (those in a bin AND matching destination)
            sql_candidates = session.query(DBSQLAPackage).filter(
                DBSQLAPackage.current_bin_id.isnot(None), 
                DBSQLAPackage.destination_zip == zip_code_filter
            ).all()
            
            # 3. Convert candidates to OOP models for the algorithm
            candidate_packages = [
                Package(p.tracking_id, p.package_size, p.destination_zip, p.is_fragile)
                for p in sql_candidates
            ]
            
            if not candidate_packages:
                print("!! No packages found for this destination.")
                return

            # 4. Run Backtracking Algorithm
            optimal_load = find_optimal_shipment(candidate_packages, truck_capacity)
            
            if not optimal_load:
                print("!! Optimal load found 0 packages that fit.")
                return

            total_size = sum(p.size for p in optimal_load)
            print(f"-> BACKTRACKING COMPLETE: Optimal Load Size: {total_size:.1f}/{truck_capacity:.1f} (Packages: {len(optimal_load)})")
            
            # 5. Update Truck, Stack (LIFO), and Package status
            sql_truck.current_load = total_size
            sql_truck.status = 'LOADING_IN_PROGRESS'

            for package in optimal_load:
                # Add to LIFO Stack (The Stack requirement for rollback)
                self.loading_stack.append(package.tracking_id)
                
                # Update Package location in DB
                sql_package = session.query(DBSQLAPackage).filter_by(tracking_id=package.tracking_id).one()
                sql_package.current_bin_id = None      # Remove from bin
                sql_package.current_truck_id = truck_id # Assign to truck
                
                # Log the change (Auditor)
                self._log_shipment(package.tracking_id, package.size, 'TRUCK_LOADED', truck_id=truck_id)

            session.commit()
            print(f"-> SUCCESS: {len(optimal_load)} packages loaded onto Truck {truck_id}.")
            print(f"-> LIFO Stack (Load Order): {self.loading_stack}")

        except Exception as e:
            session.rollback()
            print(f"!! FATAL SHIPMENT ERROR: {e}. All changes rolled back.")
        finally:
            session.close()