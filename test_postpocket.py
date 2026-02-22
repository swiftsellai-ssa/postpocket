import pytest
import os
import json
from datetime import datetime

# Import classes to test directly from the main script
from post_pocket import DatabaseManager

@pytest.fixture
def mock_db():
    """Initializes an ephemeral SQLite database for safe isolated testing."""
    test_db_path = "test_post_pocket.db"
    
    # Clean up pre-existing if failed previously
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        if os.path.exists(test_db_path + ".backup"):
            os.remove(test_db_path + ".backup")
            
    db = DatabaseManager(test_db_path)
    yield db
    
    # Teardown database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    if os.path.exists(test_db_path + ".backup"):
        os.remove(test_db_path + ".backup")


def test_initial_categories(mock_db):
    """Test that default categories are correctly seeded during initialization."""
    cats = mock_db.get_categories()
    names = [c['name'] for c in cats]
    assert "General" in names
    assert "Marketing" in names
    assert "Tech" in names


def test_save_and_retrieve_post(mock_db):
    """Test standard CRUD operations for drafting a post."""
    post_data = {
        'title': 'Test Integration Post',
        'content': 'This is a test of the Pytest suite.',
        'category': 'Tech',
        'timestamp': datetime.now().isoformat(),
        'status': 'draft',
        'tags': {'hashtags': ['testing', 'automation']}
    }
    
    # Insert
    post_id = mock_db.save_post(post_data)
    assert post_id is not None
    assert post_id > 0
    
    # Retrieve
    saved = mock_db.get_post(post_id)
    assert saved is not None
    assert saved['title'] == 'Test Integration Post'
    assert 'testing' in saved['tags']['hashtags']
    
    # Verify Metadata extraction utility
    all_tags = mock_db.get_all_assigned_tags()
    assert 'testing' in all_tags
    assert 'automation' in all_tags

def test_full_text_search(mock_db):
    """Test FTS5 virtual table implementation matches complex searches."""
    idx1 = mock_db.save_post({
        'title': 'Apples', 'content': 'Red delicious and crunchy', 
        'category': 'General', 'timestamp': datetime.now().isoformat()
    })
    idx2 = mock_db.save_post({
        'title': 'Bananas', 'content': 'Yellow and mushy', 
        'category': 'General', 'timestamp': datetime.now().isoformat()
    })
    
    # Search for exactly 'delicious'
    results = mock_db.get_posts(search_query="delicious")
    assert len(results) == 1
    assert results[0]['id'] == idx1
    assert results[0]['title'] == 'Apples'
    
    # Empty search fallback
    all_results = mock_db.get_posts(category="General")
    assert len(all_results) == 2
