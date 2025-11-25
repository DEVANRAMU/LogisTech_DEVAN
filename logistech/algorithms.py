# logistech/algorithms.py

def find_optimal_shipment(packages: list, target_capacity: float) -> list:
    """
    Module B: Recursive Backtracking Algorithm for Cargo Loading.
    Finds a subset of packages whose total size is CLOSEST TO but does not 
    EXCEED the target_capacity.
    """
    
    # Sort packages by size (descending) to prioritize filling large gaps.
    sorted_packages = sorted(packages, key=lambda p: p.size, reverse=True)
    
    best_load = []
    best_size = 0.0

    def backtrack(index: int, current_load: list, current_size: float):
        nonlocal best_load, best_size

        # --- BASE CASE 1: Best Solution Found ---
        if current_size == target_capacity:
            best_load = current_load[:]
            best_size = current_size
            return 
        
        # --- BASE CASE 2: Better Solution Found ---
        # Update best solution if current one is closer to the target
        if current_size > best_size:
            best_load = current_load[:]
            best_size = current_size

        # --- RECURSIVE STEP ---
        for i in range(index, len(sorted_packages)):
            package = sorted_packages[i]
            
            # Pruning Step: Stop if adding the next package exceeds the target capacity
            if current_size + package.size <= target_capacity:
                
                # 1. Choose (Include the package)
                current_load.append(package)
                
                # 2. Recurse (Explore next package combination)
                backtrack(i + 1, current_load, current_size + package.size)
                
                # 3. Un-Choose (Backtrack - Remove the package to explore other combinations)
                current_load.pop()
                
    # Start the recursion from index 0 with an empty load and size 0.0
    backtrack(0, [], 0.0)
    
    return best_load