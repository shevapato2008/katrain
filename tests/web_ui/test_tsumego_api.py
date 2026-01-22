"""Tests for the Tsumego API endpoints."""

import pytest
import requests

BASE_URL = "http://localhost:8001"


class TestTsumegoLevels:
    """Test the /api/v1/tsumego/levels endpoint."""

    def test_get_levels_returns_list(self):
        """Should return a list of difficulty levels."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least one level should exist

    def test_levels_have_required_fields(self):
        """Each level should have level, categories, and total fields."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels")
        data = resp.json()
        for level in data:
            assert "level" in level
            assert "categories" in level
            assert "total" in level
            assert isinstance(level["categories"], dict)
            assert level["total"] == sum(level["categories"].values())

    def test_3d_level_exists(self):
        """3D level should exist with correct structure."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels")
        data = resp.json()
        levels_by_name = {l["level"]: l for l in data}
        assert "3d" in levels_by_name
        assert levels_by_name["3d"]["total"] > 0


class TestTsumegoCategories:
    """Test the /api/v1/tsumego/levels/{level}/categories endpoint."""

    def test_get_categories_for_3d(self):
        """Should return categories for 3D level."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_categories_have_required_fields(self):
        """Each category should have category, name, and count fields."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories")
        data = resp.json()
        for cat in data:
            assert "category" in cat
            assert "name" in cat
            assert "count" in cat
            assert cat["count"] > 0

    def test_life_death_category_exists(self):
        """Life-death category should exist."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories")
        data = resp.json()
        categories = {c["category"]: c for c in data}
        assert "life-death" in categories

    def test_invalid_level_returns_404(self):
        """Invalid level should return 404."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/invalid/categories")
        assert resp.status_code == 404


class TestTsumegoProblems:
    """Test the /api/v1/tsumego/levels/{level}/categories/{category} endpoint."""

    def test_get_problems_for_3d_life_death(self):
        """Should return problems for 3D life-death category."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/life-death")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_problems_have_required_fields(self):
        """Each problem should have required fields."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/life-death?limit=5")
        data = resp.json()
        for problem in data:
            assert "id" in problem
            assert "level" in problem
            assert "category" in problem
            assert "hint" in problem
            assert "initialBlack" in problem
            assert "initialWhite" in problem
            assert isinstance(problem["initialBlack"], list)
            assert isinstance(problem["initialWhite"], list)

    def test_pagination_limit(self):
        """Limit parameter should control number of results."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/life-death?limit=5")
        data = resp.json()
        assert len(data) <= 5

    def test_pagination_offset(self):
        """Offset parameter should skip results."""
        resp1 = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/life-death?limit=5&offset=0")
        resp2 = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/life-death?limit=5&offset=5")
        data1 = resp1.json()
        data2 = resp2.json()
        # First problem in second page should be different from first page
        if len(data1) >= 5 and len(data2) >= 1:
            assert data1[0]["id"] != data2[0]["id"]

    def test_invalid_category_returns_404(self):
        """Invalid category should return 404."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/invalid")
        assert resp.status_code == 404


class TestTsumegoProblemDetail:
    """Test the /api/v1/tsumego/problems/{problem_id} endpoint."""

    def test_get_problem_detail(self):
        """Should return full problem details with SGF content."""
        # First get a valid problem ID
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/levels/3d/categories/life-death?limit=1")
        problems = resp.json()
        if not problems:
            pytest.skip("No problems available")

        problem_id = problems[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/problems/{problem_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == problem_id
        assert "sgfContent" in data
        assert "boardSize" in data
        assert data["sgfContent"].startswith("(;")  # Valid SGF starts with (;

    def test_invalid_problem_returns_404(self):
        """Invalid problem ID should return 404."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/problems/invalid_id_12345")
        assert resp.status_code == 404


class TestTsumegoProgress:
    """Test the progress endpoints (requires authentication)."""

    def test_progress_requires_auth(self):
        """Progress endpoint should require authentication."""
        resp = requests.get(f"{BASE_URL}/api/v1/tsumego/progress")
        # Should return 401 or 403 when not authenticated
        assert resp.status_code in [401, 403, 422]

    def test_update_progress_requires_auth(self):
        """Update progress endpoint should require authentication."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/tsumego/progress/1014",
            json={"completed": True, "attempts": 1}
        )
        assert resp.status_code in [401, 403, 422]
