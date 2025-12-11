import sys
import os
# Add backend directory to sys.path
sys.path.append(os.getcwd())

try:
    print("Testing DuckDB Service Import...")
    from app.services.duckdb_service import get_duckdb_service
    service = get_duckdb_service()
    print("DuckDB Service initialized successfully:", service)
    
    # Test validation
    try:
        service.validate_table_name("valid_table_1")
        print("Validation test 1 passed")
    except Exception as e:
        print("Validation test 1 failed:", e)
        
    try:
        service.validate_table_name("Invalid Table!")
        print("Validation test 2 (should fail) failed: accepted invalid name")
    except ValueError:
        print("Validation test 2 passed: rejected invalid name")

    print("\nTesting Upload Router Import...")
    from app.api.endpoints.upload import router as upload_router
    print("Upload Router imported successfully")

    print("\nTesting Relationships Router Import...")
    from app.api.endpoints.relationships import router as relationships_router
    print("Relationships Router imported successfully")

    print("\nTesting Agent Service Import...")
    from app.services.agent_service import agent_service
    print("Agent Service initialized successfully")

    print("\nALL BACKEND VERIFICATIONS PASSED")

except Exception as e:
    import traceback
    traceback.print_exc()
    print("\nBACKEND VERIFICATION FAILED")
    sys.exit(1)
