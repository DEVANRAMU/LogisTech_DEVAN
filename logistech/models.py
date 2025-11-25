from abc import ABC, abstractmethod

# --- C. StorageUnit (Abstract Base Class) ---
class StorageUnit(ABC):
    """
    Abstract Base Class for any unit that can hold packages (Bins or Trucks).
    """
    def __init__(self, capacity, current_occupancy=0.0):
        self.capacity = capacity
        self.occupancy = current_occupancy

    @abstractmethod
    def occupy_space(self, amount: float) -> bool:
        """Adds space taken by an item."""
        pass

    @abstractmethod
    def free_space(self, amount: float):
        """Removes space taken by an item."""
        pass

# --- Class: Package ---
class Package:
    """
    Represents an item/package being stored or shipped.
    """
    def __init__(self, tracking_id: str, size: float, destination: str, is_fragile: bool = False):
        self.tracking_id = tracking_id
        self.size = size
        self.destination = destination
        self.is_fragile = is_fragile
        self.current_bin_id = None
        self.current_truck_id = None

    def __repr__(self):
        return f"Package(ID={self.tracking_id}, Size={self.size}, Dest={self.destination})"

# --- Class: StorageBin (inherits StorageUnit) ---
class StorageBin(StorageUnit):
    """
    Represents a single storage location in the warehouse.
    Crucial: Implements comparison for Binary Search.
    """
    def __init__(self, bin_id: int, capacity: float, location_code: str, current_occupancy: float = 0.0):
        super().__init__(capacity, current_occupancy)
        self.bin_id = bin_id
        self.location_code = location_code

    def get_remaining_capacity(self):
        return self.capacity - self.occupancy

    def occupy_space(self, amount: float) -> bool:
        """
        Attempts to store a package. Returns True on success, False otherwise.
        """
        if self.get_remaining_capacity() >= amount:
            self.occupancy += amount
            return True
        return False

    def free_space(self, amount: float):
        """
        Frees space when a package is removed.
        """
        self.occupancy = max(0.0, self.occupancy - amount)

    # --- CRUCIAL IMPLEMENTATION FOR BINARY SEARCH ---
    def __lt__(self, other):
        """
        Defines 'less than' based on capacity, allowing bins to be sorted and 
        searched efficiently (Module A requirement).
        """
        return self.capacity < other.capacity

    def __repr__(self):
        return f"Bin(ID={self.bin_id}, Cap={self.capacity:.1f}, Occ={self.occupancy:.1f}, Loc={self.location_code})"