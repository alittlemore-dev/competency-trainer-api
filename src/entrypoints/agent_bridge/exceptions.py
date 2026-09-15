from mcp.server.mcpserver.exceptions import ToolError


class AgentBridgeToolError(ToolError):
    def __init__(self) -> None:
        super().__init__("agent bridge tool failed")
