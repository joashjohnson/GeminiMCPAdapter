import asyncio
import os
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Any, Tuple, Set

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class GeminiMCPAdapter:
    """
    Adapter to connect Google Gemini models with MCP servers.

    This adapter serves as a bridge between Gemini's function calling capabilities
    and MCP's standardized protocol for providing context and tools.

    Features:
    - Connect to multiple MCP servers simultaneously
    - Manage tools from all connected servers
    - Route function calls to the appropriate server
    - Handle response processing and follow-up queries
    """

    def __init__(self):
        """Initialize the GeminiMCPAdapter."""
        self.exit_stack = AsyncExitStack()

        # Maps server_id to session objects
        self.sessions: Dict[str, ClientSession] = {}

        # Maps tool names to their source server_id
        self.tool_to_server: Dict[str, str] = {}

        # Cache of all available tools in Gemini format
        self.tools_cache: List[Dict[str, Any]] = []

    async def connect_to_server(
        self,
        server_id: str,
        server_script_path: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Connect to an MCP server and initialize the session.

        Args:
            server_id: Unique identifier for this server connection
            server_script_path: Path to the MCP server script (.py or .js)
            env_vars: Optional environment variables to pass to the server

        Returns:
            List of tools available from the server converted to Gemini format
        """
        # Check if this server_id is already connected
        if server_id in self.sessions:
            raise ValueError(f"Server ID '{server_id}' is already in use")

        # Validate the server script type
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        # Create the server parameters
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=env_vars
        )

        # Initialize the connection
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))

        # Initialize the session
        await session.initialize()

        # Store the session
        self.sessions[server_id] = session

        # Get and register tools for this server
        server_tools = await self._get_server_tools(server_id)

        # Refresh the combined tools cache
        await self.refresh_tools_cache()

        return server_tools

    async def _get_server_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """
        Get tools from a specific MCP server and convert them to Gemini-compatible format.

        Args:
            server_id: The identifier of the server to get tools from

        Returns:
            List of tools in Gemini function call format
        """
        if server_id not in self.sessions:
            raise RuntimeError(f"No connection to server '{server_id}'")

        session = self.sessions[server_id]
        response = await session.list_tools()

        # Convert MCP tools to Gemini function declarations
        gemini_tools = []
        for tool in response.tools:
            # Register this tool as belonging to this server
            self.tool_to_server[tool.name] = server_id

            # Create a Gemini-compatible function declaration
            params = self._clean_schema(tool.inputSchema)
            function_declaration = {
                "name": tool.name,
                "description": tool.description,
                "parameters": params,
            }

            gemini_tools.append(function_declaration)

        return gemini_tools

    async def refresh_tools_cache(self) -> List[Dict[str, Any]]:
        """
        Refresh the combined tools cache from all connected servers.

        Returns:
            List of all available tools across all servers
        """
        all_tools = []

        # Get tools from each connected server
        for server_id in self.sessions:
            server_tools = await self._get_server_tools(server_id)
            all_tools.extend(server_tools)

        # Update the tools cache
        self.tools_cache = all_tools
        return all_tools

    def _clean_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean the schema to remove unsupported fields.

        Args:
            schema: The original schema

        Returns:
            Cleaned schema compatible with Gemini
        """
        # Remove top-level fields that aren't supported
        cleaned = {
            k: v
            for k, v in schema.items()
            if k not in ["additionalProperties", "$schema"]
        }

        # If there are properties, clean each property recursively
        if "properties" in cleaned:
            cleaned_props = {}
            for prop_name, prop_value in cleaned["properties"].items():
                # For each property, remove unsupported fields
                if isinstance(prop_value, dict):
                    cleaned_prop = {
                        k: v
                        for k, v in prop_value.items()
                        if k not in ["default", "examples", "format"]
                    }

                    # If property has nested items, clean those too
                    if "items" in cleaned_prop and isinstance(
                        cleaned_prop["items"], dict
                    ):
                        cleaned_prop["items"] = self._clean_schema(
                            cleaned_prop["items"]
                        )

                    cleaned_props[prop_name] = cleaned_prop
                else:
                    cleaned_props[prop_name] = prop_value

            cleaned["properties"] = cleaned_props

        return cleaned

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call a tool on the appropriate MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Result of the tool call as a string
        """
        # Find which server owns this tool
        if tool_name not in self.tool_to_server:
            return f"Error: Tool '{tool_name}' not found in any connected server"

        server_id = self.tool_to_server[tool_name]

        if server_id not in self.sessions:
            return (
                f"Error: Server '{server_id}' for tool '{tool_name}' is not connected"
            )

        session = self.sessions[server_id]

        try:
            # Call the tool on the MCP server
            result = await session.call_tool(tool_name, arguments)

            # Extract the result content
            if result.content and len(result.content) > 0:
                return result.content[0].text
            return "Tool executed successfully but returned no content."
        except Exception as e:
            return f"Error calling tool {tool_name}: {str(e)}"

    async def process_gemini_response(self, function_call: Any) -> Tuple[str, str]:
        """
        Process a function call from Gemini and execute it via MCP.

        Args:
            function_call: The function call object from Gemini's response

        Returns:
            Tuple of (tool_name, result_text)
        """
        if not function_call:
            return ("", "No function call detected")

        tool_name = function_call.name
        arguments = function_call.args

        # Call the tool via MCP
        result = await self.call_tool(tool_name, arguments)

        return (tool_name, result)

    async def process_query(self, client, query: str, model_name: str) -> str:
        """
        Process a user query with Gemini, using MCP tools when needed.

        Args:
            client: The Gemini client
            query: The user's query
            model_name: The name of the Gemini model to use

        Returns:
            Response text, possibly including results from tool calls
        """
        from google.genai import types
        import json

        # Check if we have any connected servers
        if not self.sessions:
            return "Not connected to any MCP servers. Connect to at least one server first."

        # Create Gemini-compatible tool objects
        tools = [
            types.Tool(function_declarations=[func_decl])
            for func_decl in self.tools_cache
        ]

        # Create configuration with tools
        config = types.GenerateContentConfig(
            temperature=0.2,  # Using lower temperature for more deterministic tool calls
            tools=tools,
        )

        # Send request to the model using just the current query
        response = client.models.generate_content(
            model=model_name, contents=query, config=config
        )

        # Process the response
        if not response.candidates or not response.candidates[0].content.parts:
            return "No response from the model."

        # Check if there's a function call
        if response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call

            # Process the function call via the adapter
            tool_name, result = await self.process_gemini_response(function_call)

            # Send a follow-up request to interpret the result
            follow_up_query = f"I asked: {query}\n\nThe tool {tool_name} returned: {result}\n\nCan you explain this result?"

            follow_up_response = client.models.generate_content(
                model=model_name,
                contents=follow_up_query,
                config=types.GenerateContentConfig(temperature=0.2),
            )

            final_text = follow_up_response.text

            # Return a combined response showing tool use and final answer
            return f"[Tool Used: {tool_name}]\n\n{result}\n\n{final_text}"
        else:
            # No function call, just return the text response
            return response.text

    async def disconnect_server(self, server_id: str):
        """
        Disconnect from a specific server.

        Args:
            server_id: The identifier of the server to disconnect
        """
        if server_id not in self.sessions:
            return

        # Remove tools associated with this server
        tools_to_remove = [
            name for name, sid in self.tool_to_server.items() if sid == server_id
        ]
        for tool_name in tools_to_remove:
            del self.tool_to_server[tool_name]

        # Remove the session (it will be automatically closed by the exit stack)
        del self.sessions[server_id]

        # Refresh the tools cache
        await self.refresh_tools_cache()

    def get_connected_servers(self) -> Set[str]:
        """
        Get the IDs of all connected servers.

        Returns:
            Set of server IDs
        """
        return set(self.sessions.keys())

    async def cleanup(self):
        """Clean up resources and close all connections."""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.tool_to_server.clear()
        self.tools_cache.clear()


async def attach_adapter(client, servers=None):
    """
    Attach the MCP adapter to a Gemini client.

    Args:
        client: The Gemini client instance
        servers: List of paths to MCP server scripts (.py or .js)

    Returns:
        The wrapped Gemini client with MCP capabilities
    """
    adapter = GeminiMCPAdapter()

    # Connect to each server
    if servers:
        for i, server_path in enumerate(servers):
            server_id = f"server_{i}"
            try:
                await adapter.connect_to_server(server_id, server_path)
                print(f"Successfully connected to {server_path}")
            except Exception as e:
                print(f"Failed to connect to {server_path}: {str(e)}")

    # Store the original generate_content_stream method
    original_generate_content_stream = client.models.generate_content_stream

    # Override the generate_content_stream method to intercept function calls
    async def wrapped_generate_content_stream(*args, **kwargs):
        # Get tools from adapter and merge with any existing tools
        config = kwargs.get("config", None)
        adapter_tools = []

        # If there are adapter tools, prepare them for Gemini
        if adapter.tools_cache:
            from google.genai import types

            for tool_decl in adapter.tools_cache:
                adapter_tools.append(
                    types.Tool(
                        function_declarations=[types.FunctionDeclaration(**tool_decl)]
                    )
                )

        # If config has tools, append our adapter tools
        if config and hasattr(config, "tools") and config.tools:
            config.tools.extend(adapter_tools)
        # If no tools in config, add our adapter tools if we have any
        elif adapter_tools:
            from google.genai import types

            if not config:
                config = types.GenerateContentConfig()
                kwargs["config"] = config
            config.tools = adapter_tools

        # Call the original method to get the generator
        generator = await original_generate_content_stream(*args, **kwargs)

        # Return a new generator that checks for function calls
        async for chunk in generator:
            # Check if this chunk contains a function call
            if hasattr(chunk, "function_calls") and chunk.function_calls:
                function_call = chunk.function_calls[0]
                # Check if this is a tool from our adapter
                tool_name = function_call.name
                if tool_name in adapter.tool_to_server:
                    # Process the function call with our adapter
                    _, result = await adapter.process_gemini_response(function_call)
                    # Set the result on the chunk (implementation would depend on
                    # how Gemini represents results)
                    # This is a simplified approach; actual implementation may vary
                    chunk._text = result

            yield chunk

    # Replace the generate_content_stream method
    client.models.generate_content_stream = wrapped_generate_content_stream

    # Also need to handle non-streaming version
    original_generate_content = client.models.generate_content

    def wrapped_generate_content(*args, **kwargs):
        # Get tools from adapter and merge with any existing tools
        config = kwargs.get("config", None)
        adapter_tools = []

        # If there are adapter tools, prepare them for Gemini
        if adapter.tools_cache:
            from google.genai import types

            for tool_decl in adapter.tools_cache:
                adapter_tools.append(
                    types.Tool(
                        function_declarations=[types.FunctionDeclaration(**tool_decl)]
                    )
                )

        # If config has tools, append our adapter tools
        if config and hasattr(config, "tools") and config.tools:
            config.tools.extend(adapter_tools)
        # If no tools in config, add our adapter tools if we have any
        elif adapter_tools:
            from google.genai import types

            if not config:
                config = types.GenerateContentConfig()
                kwargs["config"] = config
            config.tools = adapter_tools

        # Call the original method
        response = original_generate_content(*args, **kwargs)

        # Check if the response has a function call
        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            function_call = part.function_call
                            tool_name = function_call.name
                            if tool_name in adapter.tool_to_server:
                                # Use asyncio to run the async process_gemini_response
                                import asyncio

                                _, result = asyncio.run(
                                    adapter.process_gemini_response(function_call)
                                )
                                # Update the part with the result
                                # Implementation would depend on Gemini's structure
                                part._text = result

        return response

    # Replace the generate_content method
    client.models.generate_content = wrapped_generate_content

    # Store the adapter reference on the client
    client._mcp_adapter = adapter

    return client


def attach_adapter_sync(client, servers=None):
    """
    Synchronous version of attach_adapter for simpler integration.

    Args:
        client: The Gemini client instance
        servers: List of paths to MCP server scripts (.py or .js)

    Returns:
        The wrapped Gemini client with MCP capabilities
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(attach_adapter(client, servers))
    except Exception as e:
        print(f"Error attaching adapter: {str(e)}")
        # Return the original client if something goes wrong
        return client
