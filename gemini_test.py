import os
import sys
import time
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
from gemini_mcp_adapter import GeminiMCPAdapter

# Load environment variables
load_dotenv()


async def test_gemini_integration():
    """Test the integration of Gemini with MCP servers via our adapter."""
    # Get API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment")
        sys.exit(1)

    print("\n===== GEMINI MCP INTEGRATION TEST =====")
    print("This test verifies that the adapter can connect Gemini to MCP servers")

    try:
        # Initialize Gemini client
        print("\n1. Initializing Gemini client...")
        client = genai.Client(api_key=api_key)

        # Test direct Gemini first to verify API is working
        print("\n2. Testing direct Gemini API (no adapter)...")
        try:
            direct_response = client.models.generate_content(
                model="gemini-2.5-pro-preview-03-25", contents="What is 2+2?"
            )

            print(f"   Direct Gemini test: {direct_response.text}")
            print("   ✅ Direct Gemini API is working")
        except Exception as e:
            print(f"   ❌ Direct Gemini API test failed: {str(e)}")
            print("   Please check your API key and internet connection")
            return

        # Create adapter directly instead of using attach_adapter_sync
        print("\n3. Creating MCP adapter...")
        adapter = GeminiMCPAdapter()

        # Connect to calculator server
        print("   Connecting to calculator server...")
        print(
            f"   Looking for calculator_server.py: {os.path.exists('calculator_server.py')}"
        )

        server_id = "calculator"
        await adapter.connect_to_server(server_id, "calculator_server.py")
        print("   ✅ Successfully connected to calculator_server.py")

        # List available tools
        print(f"   Available tools: {[tool['name'] for tool in adapter.tools_cache]}")

        # Test direct tool call
        print("\n4. Testing direct tool call...")
        start_time = time.time()
        result = await adapter.call_tool("add", {"a": 40, "b": 2})
        end_time = time.time()

        print(f"   Direct tool call completed in {end_time - start_time:.2f} seconds")
        print(f"   Result: {result}")
        print("   ✅ Direct tool call successful")

        # Test with Gemini API
        print("\n5. Testing integration with Gemini...")

        # Store the original generate_content method
        original_generate_content = client.models.generate_content

        # Override the generate_content method to add tools
        def wrapped_generate_content(*args, **kwargs):
            # Get tools from adapter
            config = kwargs.get("config", None)
            adapter_tools = []

            # If there are adapter tools, prepare them for Gemini
            if adapter.tools_cache:
                for tool_decl in adapter.tools_cache:
                    adapter_tools.append(
                        types.Tool(
                            function_declarations=[
                                types.FunctionDeclaration(**tool_decl)
                            ]
                        )
                    )

            # If config has tools, append our adapter tools
            if config and hasattr(config, "tools") and config.tools:
                config.tools.extend(adapter_tools)
            # If no tools in config, add our adapter tools if we have any
            elif adapter_tools:
                if not config:
                    config = types.GenerateContentConfig()
                    kwargs["config"] = config
                config.tools = adapter_tools

            # Call the original method
            response = original_generate_content(*args, **kwargs)

            # Check for function calls (would handle them here in a real implementation)
            print("   Checking for function calls in response...")
            has_function_calls = False
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            if hasattr(part, "function_call") and part.function_call:
                                has_function_calls = True
                                function_call = part.function_call
                                print(
                                    f"   ✅ Found function call: {function_call.name}"
                                )
                                print(f"   Arguments: {function_call.args}")

            if not has_function_calls:
                print("   No function calls found in response")

            return response

        # Replace the generate_content method
        client.models.generate_content = wrapped_generate_content

        # Send a query to Gemini
        query = "What is 40 + 2?"
        print(f"   Query: '{query}'")

        try:
            # Create content and config
            contents = [
                types.Content(role="user", parts=[types.Part.from_text(text=query)])
            ]
            config = types.GenerateContentConfig(
                temperature=0.2, max_output_tokens=1024
            )

            # Send to Gemini
            print("   Sending to Gemini...")
            start_time = time.time()

            response = client.models.generate_content(
                model="gemini-2.5-pro-preview-03-25", contents=contents, config=config
            )

            end_time = time.time()
            print(f"   Response received in {end_time - start_time:.2f} seconds")

            # Safely handle response output
            try:
                print(f"   Response text: {response.text}")
            except ValueError:
                print(
                    "   Response contains function calls instead of text (this is good!)"
                )

            # Check for function calls in the response
            function_call_found = False
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            if hasattr(part, "function_call") and part.function_call:
                                function_call_found = True

            # Determine success
            if function_call_found:
                print("\n   ✅ SUCCESS: Gemini used our MCP tool!")
                print("   The adapter integration is working correctly")
            elif "42" in str(response):
                print(
                    "\n   ✓ PARTIAL SUCCESS: Gemini answered correctly without using tools"
                )
            else:
                print("\n   ⚠️ UNCLEAR: Gemini responded but didn't use tools")

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback

            traceback.print_exc()

        # Clean up
        await adapter.cleanup()

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        print("\nThe adapter encountered an error during the Gemini integration test.")


if __name__ == "__main__":
    asyncio.run(test_gemini_integration())
