"""Callback data parsing and routing."""
from dataclasses import dataclass
from typing import Callable, Dict, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class CallbackData:
    """Parsed callback data."""
    action: str       # "menu"
    section: str      # "shop", "back", etc.
    session_id: str   # UUID4


def parse_callback_data(data: str) -> Optional[CallbackData]:
    """
    Parse callback_data format: menu:<section>:<session_id>
    
    Args:
        data: Callback data string from inline button
    
    Returns:
        CallbackData object or None if format is invalid
    
    Example:
        >>> parse_callback_data("menu:shop:abc-123")
        CallbackData(action='menu', section='shop', session_id='abc-123')
    """
    try:
        parts = data.split(":")
        if len(parts) != 3:
            logger.warning("callback_data_invalid_format", data=data, parts_count=len(parts))
            return None
        
        action, section, session_id = parts
        
        # Validate no empty fields
        if not action or not section or not session_id:
            logger.warning("callback_data_empty_field", data=data)
            return None
        
        if action != "menu":
            logger.warning("callback_data_unknown_action", action=action, data=data)
            return None
        
        return CallbackData(action=action, section=section, session_id=session_id)
    
    except Exception as e:
        logger.error("callback_data_parse_error", data=data, error=str(e))
        return None


class NavigationRouter:
    """Routes callback queries to appropriate section handlers."""
    
    def __init__(self):
        self._routes: Dict[str, Callable] = {}
    
    def register(self, section: str, handler: Callable) -> None:
        """Register a handler for a section."""
        self._routes[section] = handler
        logger.info("route_registered", section=section)
    
    def get_handler(self, section: str) -> Optional[Callable]:
        """Get handler for a section."""
        return self._routes.get(section)
    
    def list_routes(self) -> list[str]:
        """List all registered routes."""
        return list(self._routes.keys())


# Global router instance
navigation_router = NavigationRouter()
