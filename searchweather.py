import os
import sys
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from gemini_mcp_adapter import GeminiMCPAdapter

# Load environment variables
load_dotenv()


async def generate_with_mcp():
    """Process weather queries using Gemini with MCP integration."""
    # Get API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment")
        sys.exit(1)

    # Initialize Gemini client
    print("\nInitializing Gemini client...")
    client = genai.Client(api_key=api_key)

    # Create MCP adapter
    print("Creating MCP adapter...")
    adapter = GeminiMCPAdapter()

    # Connect to weather server
    print("Connecting to weather server...")
    print(f"Looking for weather_server.py: {os.path.exists('weather_server.py')}")

    if not os.path.exists("weather_server.py"):
        print("Error: weather_server.py not found!")
        print("Make sure weather_server.py is in the current directory")
        return

    try:
        # Connect to server
        server_id = "weather"
        await adapter.connect_to_server(server_id, "weather_server.py")
        print("✅ Successfully connected to weather server")

        # List available tools
        print(f"Available tools: {[tool['name'] for tool in adapter.tools_cache]}")

        # Get user query
        user_query = input("\nEnter your weather question: ")
        if not user_query:
            user_query = "What's the current weather in New York?"
            print(f"Using default query: '{user_query}'")

        # Create Gemini content
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_query)],
            ),
        ]

        # Create config with tools
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1024,
        )

        # Prepare tools for Gemini
        gemini_tools = []
        for tool_decl in adapter.tools_cache:
            gemini_tools.append(
                types.Tool(
                    function_declarations=[types.FunctionDeclaration(**tool_decl)]
                )
            )

        if gemini_tools:
            config.tools = gemini_tools

        print("\nSending query to Gemini with MCP tools...")

        # Process with Gemini in streaming mode
        print("\n--- Response ---")
        try:
            # Use regular (non-async) stream
            stream = client.models.generate_content_stream(
                model="gemini-2.5-pro-preview-03-25",
                contents=contents,
                config=config,
            )

            function_call_detected = False
            # Use regular for loop instead of async for
            for chunk in stream:
                # Check for function calls
                if hasattr(chunk, "function_calls") and chunk.function_calls:
                    function_call_detected = True
                    function_call = chunk.function_calls[0]
                    print(f"\n[Detected function call: {function_call.name}]")
                    print(f"[Arguments: {function_call.args}]")

                    # Execute the function call via MCP
                    print(f"\n[Executing {function_call.name} through MCP...]")
                    result = await adapter.call_tool(
                        function_call.name, function_call.args
                    )
                    print(f"\n[Result from MCP server: {result}]")

                    # Now generate a follow-up with the result
                    follow_up = f"The weather tool returned: {result}\nCan you summarize this information for me in a friendly way?"

                    follow_up_response = client.models.generate_content(
                        model="gemini-2.5-pro-preview-03-25",
                        contents=follow_up,
                    )

                    print(f"\n{follow_up_response.text}")
                elif hasattr(chunk, "text"):
                    print(chunk.text, end="")

            if not function_call_detected:
                print("\n\nNote: Gemini responded directly without using MCP tools.")

        except Exception as e:
            print(f"\nError during Gemini processing: {str(e)}")
            import traceback

            traceback.print_exc()

        # Clean up
        await adapter.cleanup()
        print("\n--- End of response ---")

    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback

        traceback.print_exc()


def main():
    """Run the weather query processor."""
    try:
        asyncio.run(generate_with_mcp())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
