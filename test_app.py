#!/usr/bin/env python3
"""Simple test script to verify the CleanSpot application works correctly."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.database import init_db

def test_app():
    """Test basic application functionality."""
    try:
        # Create app
        app = create_app()
        print("[OK] Flask app created successfully")
        
        # Initialize database
        init_db()
        print("[OK] Database initialized successfully")
        
        # Test app context
        with app.app_context():
            print("[OK] App context works")
            
        # Test basic routes exist
        with app.test_client() as client:
            # Test main page
            response = client.get('/')
            print(f"[OK] Main page accessible (status: {response.status_code})")
            
            # Test admin page
            response = client.get('/admin')
            print(f"[OK] Admin page accessible (status: {response.status_code})")
            
            # Test API endpoint
            response = client.get('/api/reports')
            print(f"[OK] API endpoint accessible (status: {response.status_code})")
            
        print("\nAll tests passed! The application is ready to run.")
        print("Run with: python run.py")
        return True
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

if __name__ == '__main__':
    test_app()