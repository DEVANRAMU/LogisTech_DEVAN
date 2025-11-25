from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. Database Configuration and Base
DATABASE_URL = "sqlite:///warehouse.db"
Base = declarative_base()

# 2. Table Definitions (Declarative Base)

class StorageBin(Base):
    """Defines the master data for physical storage bins."""
    __tablename__ = 'storage_bins'
    
    bin_id = Column(Integer, primary_key=True)
    location_code = Column(String, unique=True, nullable=False)
    max_capacity = Column(Float, nullable=False)
    current_occupancy = Column(Float, default=0.0, nullable=False)

class DeliveryTruck(Base):
    """Defines the master data for outbound delivery vehicles."""
    __tablename__ = 'delivery_trucks'
    
    truck_id = Column(Integer, primary_key=True)
    license_plate = Column(String, unique=True, nullable=False)
    max_capacity = Column(Float, nullable=False)
    current_load = Column(Float, default=0.0, nullable=False)
    status = Column(String, default='READY_TO_LOAD', nullable=False)

class Package(Base):
    """Defines the current state of a package in the warehouse."""
    __tablename__ = 'packages'
    
    tracking_id = Column(String, primary_key=True)
    package_size = Column(Float, nullable=False)
    destination_zip = Column(String, nullable=False)
    is_fragile = Column(Boolean, default=False, nullable=False)
    
    # Foreign Keys to track current location
    # Note: Only one FK should be non-NULL at any time (in a bin OR on a truck)
    current_bin_id = Column(Integer, ForeignKey('storage_bins.bin_id'), nullable=True)
    current_truck_id = Column(Integer, ForeignKey('delivery_trucks.truck_id'), nullable=True)

class ShipmentLog(Base):
    """The Auditor/Manifest: Tracks every status change."""
    __tablename__ = 'shipment_logs'
    
    id = Column(Integer, primary_key=True)
    tracking_id = Column(String, nullable=False)
    bin_id = Column(Integer, nullable=True)
    truck_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    status = Column(String, nullable=False) # e.g., 'INGESTED', 'BIN_ASSIGNED', 'TRUCK_LOADED'
    package_size = Column(Float, nullable=False)


# 3. Setup and Seeding Functions


def initialize_db(engine=None): # <-- Engine is now optional
    """Creates the database tables and seeds the initial data."""
    
    # 1. Create Engine if not provided (needed for standalone runs like main.py)
    if engine is None:
        print("Creating database schema at sqlite:///warehouse.db...")
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(engine)
        print("Database schema created successfully.")
    
    # 2. Seed Data
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    
    # Check if data has already been seeded to prevent duplicates
    if session.query(StorageBin).count() == 0:
        seed_data(session)
        print("Seeded 6 Storage Bins.")
        print("Seeded 2 Delivery Trucks.")
    
    session.close()

def seed_data(Session):
    """Inserts initial configuration data (bins and trucks)."""
    session = Session()
    
    # Seed Storage Bins (Crucial for Binary Search testing)
    # We must ensure they are created with different sizes.
    bins_data = [
        # Smallest Bins
        StorageBin(bin_id=101, location_code='A01S01', max_capacity=5.0),
        StorageBin(bin_id=102, location_code='A01S02', max_capacity=10.0),
        
        # Medium Bins
        StorageBin(bin_id=201, location_code='A05S10', max_capacity=15.0),
        StorageBin(bin_id=202, location_code='A05S11', max_capacity=20.0),
        
        # Large Bins
        StorageBin(bin_id=301, location_code='B10S05', max_capacity=50.0),
        StorageBin(bin_id=302, location_code='B10S06', max_capacity=100.0),
    ]
    
    # Seed Delivery Trucks
    trucks_data = [
        DeliveryTruck(truck_id=1, license_plate='LOGI-001', max_capacity=500.0),
        DeliveryTruck(truck_id=2, license_plate='LOGI-002', max_capacity=1200.0),
    ]
    
    try:
        # Check if data already exists before adding
        if session.query(StorageBin).count() == 0:
            session.add_all(bins_data)
            print(f"Seeded {len(bins_data)} Storage Bins.")
            
        if session.query(DeliveryTruck).count() == 0:
            session.add_all(trucks_data)
            print(f"Seeded {len(trucks_data)} Delivery Trucks.")
            
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error during seeding: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    engine = create_engine(DATABASE_URL)
    initialize_db(engine)
    
    Session = sessionmaker(bind=engine)
    seed_data(Session)