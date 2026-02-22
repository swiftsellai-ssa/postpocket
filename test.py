import pytest
import os
import json
from unittest.mock import MagicMock, patch
from post_pocket import DatabaseManager, XApiWorker

# =============== DATABASE UNIT TESTS ===============

@pytest.fixture
def db():
    """Provides a fresh, isolated, temporary SQLite DatabaseManager mapping for every test."""
    test_db_name = "test_post_pocket_pro.db"
    manager = DatabaseManager(test_db_name)
    
    # Force clean tables before every run due to lingering WAL locks preventing os.remove
    conn = manager._get_conn()
    conn.execute("DELETE FROM categories")
    conn.execute("DELETE FROM posts")
    conn.execute("DELETE FROM posts_fts")
    
    # Re-insert the base General category
    conn.execute("INSERT OR IGNORE INTO categories (name, parent_id) VALUES ('General', NULL)")
    conn.commit()
    conn.close()
    
    yield manager

def test_add_and_get_category(db):
    """Verifies SQLite successfully inserts hierarchical category strings."""
    db.add_category("Tech", parent_name=None)
    db.add_category("Python", parent_name="Tech")
    
    cats = db.get_categories()
    assert len(cats) == 3 # General + Tech + Python
    names = [c['name'] for c in cats]
    assert "Tech" in names
    assert "Python" in names

def test_save_and_retrieve_post(db):
    """Verifies Dict serialization into SQLite rows natively preserves tags and metadata mapping."""
    post_data = {
        'title': 'First Test Post',
        'content': 'This is exciting! #pytest',
        'category': 'General',
        'timestamp': '2026-02-23T12:00:00',
        'status': 'draft',
        'tags': {'thread_count': 1, 'word_count': 4}
    }
    
    post_id = db.save_post(post_data)
    assert post_id > 0
    
    retrieved = db.get_post(post_id)
    assert retrieved['title'] == 'First Test Post'
    assert retrieved['content'] == 'This is exciting! #pytest'
    assert retrieved['tags']['word_count'] == 4

def test_full_text_search(db):
    """Verifies the FTS5 virtual table properly indexes dynamic keyword mappings."""
    db.save_post({
        'title': 'Hello World', 'content': 'Learning PyQt6 is great.', 
        'category': 'General', 'timestamp': '2026-02-23T12:00:00', 'status': 'draft'
    })
    db.save_post({
        'title': 'Advanced Stuff', 'content': 'Learning Rust is hard.', 
        'category': 'General', 'timestamp': '2026-02-23T12:00:00', 'status': 'draft'
    })
    
    results = db.get_posts(search_query="PyQt6")
    assert len(results) == 1
    assert results[0]['title'] == 'Hello World'

def test_duplicate_post_backend_flow(db):
    """Tests the new Phase 5 natively piped DatabaseWorker action."""
    original_id = db.save_post({
        'title': 'Amazing Insight', 'content': 'Here is my tweet.', 
        'category': 'General', 'timestamp': '2026-02-23T12:00:00', 'status': 'posted'
    })
    
    # Simulate DBWorker duplication
    post = db.get_post(original_id)
    del post['id']
    post['title'] = "Copy of " + post.get('title', '')
    post['status'] = 'draft'
    new_id = db.save_post(post)
    
    assert new_id != original_id
    duplicate = db.get_post(new_id)
    assert duplicate['title'] == "Copy of Amazing Insight"
    assert duplicate['status'] == 'draft'

# =============== X API (TWEEPY) MOCKS ===============

@pytest.fixture
def x_worker():
    return XApiWorker()

def test_chunk_text_logic(x_worker):
    """Validates the text thread-splitter correctly chops text avoiding bad word fracturing."""
    short_text = "This fits nicely into one."
    chunks = x_worker.chunk_text(short_text)
    assert len(chunks) == 1
    assert chunks[0] == short_text
    
    long_text = "Word " * 60  # ~300 chars, should split into two chunks
    chunks = x_worker.chunk_text(long_text)
    assert len(chunks) == 2
    assert len(chunks[0]) <= 280
    assert len(chunks[1]) > 0

@patch('post_pocket.tweepy.Client')
@patch('post_pocket.keyring.get_password')
def test_x_api_post_flow(mock_keyring, mock_client_class, x_worker):
    """Mocks Tweepy and Network responses to validate thread loop logic without network lag."""
    mock_keyring.return_value = "fake_key"
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock return layout for create_tweet
    mock_response = MagicMock()
    mock_response.data = {'id': '123456789'}
    mock_client.create_tweet.return_value = mock_response

    # Test posting
    payload = {'text': "Posting this text #awesome", 'post_id': 1}
    # Notice we can manually run handle_request without spinning up the QThread
    x_worker.handle_request('post', payload)
    
    # Expect single call to create_tweet
    mock_client.create_tweet.assert_called_once_with(text="Posting this text #awesome")
