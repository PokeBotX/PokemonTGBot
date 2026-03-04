"""Unit tests for router and callback parser."""
import pytest
from unittest.mock import Mock, AsyncMock

from bot.navigation.router import parse_callback_data, CallbackData, NavigationRouter


def test_parse_callback_data_valid():
    """Test parsing valid callback data."""
    callback_data = parse_callback_data("menu:shop:abc-123-def")
    
    assert callback_data is not None
    assert callback_data.action == "menu"
    assert callback_data.section == "shop"
    assert callback_data.session_id == "abc-123-def"


def test_parse_callback_data_with_uuid():
    """Test parsing callback with real UUID."""
    uuid_session = "550e8400-e29b-41d4-a716-446655440000"
    callback_data = parse_callback_data(f"menu:profile:{uuid_session}")
    
    assert callback_data is not None
    assert callback_data.action == "menu"
    assert callback_data.section == "profile"
    assert callback_data.session_id == uuid_session


def test_parse_callback_data_invalid_format():
    """Test parsing invalid callback data formats."""
    # Not enough parts
    assert parse_callback_data("menu:shop") is None
    
    # Too many parts
    assert parse_callback_data("menu:shop:abc:extra") is None
    
    # Empty string
    assert parse_callback_data("") is None
    
    # Random string
    assert parse_callback_data("random_string") is None
    
    # No colons
    assert parse_callback_data("menushopabc") is None


def test_parse_callback_data_wrong_action():
    """Test that non-menu actions return None."""
    # Only "menu" action is supported
    callback_data = parse_callback_data("other:shop:abc")
    assert callback_data is None


def test_parse_callback_data_empty_fields():
    """Test parsing with empty section or session_id."""
    # Empty section
    assert parse_callback_data("menu::abc") is None
    
    # Empty session_id
    assert parse_callback_data("menu:shop:") is None


def test_navigation_router_register():
    """Test registering handlers in router."""
    router = NavigationRouter()
    
    # Create mock handler
    mock_handler = AsyncMock()
    
    # Register handler
    router.register("shop", mock_handler)
    
    # Get handler back
    handler = router.get_handler("shop")
    assert handler is mock_handler


def test_navigation_router_get_unknown_handler():
    """Test getting unknown handler returns None."""
    router = NavigationRouter()
    
    handler = router.get_handler("unknown_section")
    assert handler is None


def test_navigation_router_list_routes():
    """Test listing all registered routes."""
    router = NavigationRouter()
    
    # Register multiple handlers
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    handler3 = AsyncMock()
    
    router.register("shop", handler1)
    router.register("market", handler2)
    router.register("profile", handler3)
    
    # List routes
    routes = router.list_routes()
    
    assert len(routes) == 3
    assert "shop" in routes
    assert "market" in routes
    assert "profile" in routes


def test_navigation_router_overwrite_handler():
    """Test that registering same section overwrites previous handler."""
    router = NavigationRouter()
    
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    
    # Register first handler
    router.register("shop", handler1)
    assert router.get_handler("shop") is handler1
    
    # Register second handler (overwrite)
    router.register("shop", handler2)
    assert router.get_handler("shop") is handler2


def test_callback_data_dataclass():
    """Test CallbackData dataclass."""
    data = CallbackData(
        action="menu",
        section="shop",
        session_id="abc-123",
    )
    
    assert data.action == "menu"
    assert data.section == "shop"
    assert data.session_id == "abc-123"


def test_parse_callback_data_all_sections():
    """Test parsing callback data for all sections."""
    sections = ["shop", "market", "profile", "games", "collection", "updates", "chat", "support", "info", "back"]
    
    for section in sections:
        callback_data = parse_callback_data(f"menu:{section}:test-session")
        assert callback_data is not None
        assert callback_data.section == section
