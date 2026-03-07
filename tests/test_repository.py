import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.database.models import ChatIndexStatus
from src.database.repository import ChatIndexStatusRepository


class TestGetMissingRanges:
    @pytest.fixture
    def repo(self):
        mock_session = MagicMock()
        return ChatIndexStatusRepository(mock_session)
    
    def test_no_status_returns_full_range(self, repo):
        """When chat was never indexed, return the full requested range."""
        requested_from = datetime(2026, 3, 1)
        requested_until = datetime(2026, 3, 7)
        
        ranges = repo.get_missing_ranges(None, requested_from, requested_until)
        
        assert len(ranges) == 1
        assert ranges[0] == (requested_from, requested_until)
    
    def test_fully_covered_returns_empty(self, repo):
        """When requested range is fully covered, return empty list."""
        status = MagicMock(spec=ChatIndexStatus)
        status.indexed_from_date = datetime(2026, 2, 25)
        status.indexed_until_date = datetime(2026, 3, 10)
        
        requested_from = datetime(2026, 3, 1)
        requested_until = datetime(2026, 3, 7)
        
        ranges = repo.get_missing_ranges(status, requested_from, requested_until)
        
        assert len(ranges) == 0
    
    def test_older_data_needed(self, repo):
        """When older data is needed, return range before indexed_from."""
        status = MagicMock(spec=ChatIndexStatus)
        status.indexed_from_date = datetime(2026, 3, 1)
        status.indexed_until_date = datetime(2026, 3, 7)
        
        requested_from = datetime(2026, 2, 20)
        requested_until = datetime(2026, 3, 5)
        
        ranges = repo.get_missing_ranges(status, requested_from, requested_until)
        
        assert len(ranges) == 1
        assert ranges[0] == (datetime(2026, 2, 20), datetime(2026, 3, 1))
    
    def test_newer_data_needed(self, repo):
        """When newer data is needed, return range after indexed_until."""
        status = MagicMock(spec=ChatIndexStatus)
        status.indexed_from_date = datetime(2026, 3, 1)
        status.indexed_until_date = datetime(2026, 3, 5)
        
        requested_from = datetime(2026, 3, 3)
        requested_until = datetime(2026, 3, 10)
        
        ranges = repo.get_missing_ranges(status, requested_from, requested_until)
        
        assert len(ranges) == 1
        assert ranges[0] == (datetime(2026, 3, 5), datetime(2026, 3, 10))
    
    def test_both_ranges_needed(self, repo):
        """When both older and newer data needed, return both ranges."""
        status = MagicMock(spec=ChatIndexStatus)
        status.indexed_from_date = datetime(2026, 3, 3)
        status.indexed_until_date = datetime(2026, 3, 5)
        
        requested_from = datetime(2026, 3, 1)
        requested_until = datetime(2026, 3, 10)
        
        ranges = repo.get_missing_ranges(status, requested_from, requested_until)
        
        assert len(ranges) == 2
        assert (datetime(2026, 3, 1), datetime(2026, 3, 3)) in ranges
        assert (datetime(2026, 3, 5), datetime(2026, 3, 10)) in ranges


class TestIsCacheFresh:
    @pytest.fixture
    def repo(self):
        mock_session = MagicMock()
        return ChatIndexStatusRepository(mock_session)
    
    def test_no_status_not_fresh(self, repo):
        """No status means cache is not fresh."""
        assert repo.is_cache_fresh(None) is False
    
    def test_recent_index_is_fresh(self, repo):
        """Recently indexed is fresh."""
        status = MagicMock(spec=ChatIndexStatus)
        status.last_indexed_at = datetime.utcnow() - timedelta(minutes=30)
        
        assert repo.is_cache_fresh(status, cache_minutes=60) is True
    
    def test_old_index_not_fresh(self, repo):
        """Old index is not fresh."""
        status = MagicMock(spec=ChatIndexStatus)
        status.last_indexed_at = datetime.utcnow() - timedelta(minutes=120)
        
        assert repo.is_cache_fresh(status, cache_minutes=60) is False
    
    def test_just_under_threshold(self, repo):
        """Index just under threshold is fresh."""
        status = MagicMock(spec=ChatIndexStatus)
        status.last_indexed_at = datetime.utcnow() - timedelta(minutes=59)
        
        assert repo.is_cache_fresh(status, cache_minutes=60) is True
