from typing import Any
import msgspec
from fastapi.responses import JSONResponse


class CustomJSONResponse(JSONResponse):
    """Inherits all functionalities from JSONResponse but customizes the 
    render method to use msgspec for  serialisation"""
    def render(self, content: Any) -> bytes:
        """Renders the content to JSON bytes using msgspec
        Args:
         content:
            The content to be serialised as JSON.
        
        Returns:
          json_bytes:
            The JSON serialised content in bytes.
        """

        assert content is not None, "Content to render cannot be None"
        json_bytes = msgspec.json.encode(content)
        return json_bytes