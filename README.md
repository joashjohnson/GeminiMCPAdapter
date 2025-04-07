# Gemini MCP Adapter

This adapter allows you to easily integrate your Gemini API applications with Model Context Protocol (MCP) servers, providing access to a wide range of tools and capabilities.

## Getting Started

### Prerequisites

- Python 3.10+
- Google Gemini API key
- MCP server scripts (Python or Node.js)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/gemini-mcp-adapter.git
cd gemini-mcp-adapter

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Unix/MacOS
# OR on Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create a .env file with your API key
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### Running the Interactive Demo

```bash
# Run the interactive demo with both weather and calculator servers
python example.py
```

This will start an interactive session where you can ask questions like:

- "What's the weather in Tokyo?"
- "Calculate 25 \* 16"
- "What's the square root of 144?"

### Basic Usage in Your Code

Here's how to use the adapter with minimal code changes:

```python
import os
from google import genai
from gemini_mcp_adapter import attach_adapter_sync

# Initialize the Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Attach the MCP adapter with your server scripts
client = attach_adapter_sync(client, servers=[
    "path/to/weather_server.py",
    "path/to/calculator_server.js"
])

# Use the client as usual - the adapter automatically handles tool calls
response = client.models.generate_content(
    model="gemini-2.5-pro-preview-03-25",
    contents="What's the weather in New York?"
)
print(response.text)
```

## How It Works

The adapter:

1. Connects to the specified MCP servers
2. Discovers available tools from each server
3. Intercepts Gemini API calls to include the tools
4. Routes tool calls to the appropriate server
5. Returns the results back to the Gemini model

## Advanced Configuration

For more control, you can access the underlying adapter directly:

```python
# Access the adapter instance
adapter = client._mcp_adapter

# Get a list of all available tools
all_tools = adapter.tools_cache

# Manually call a specific tool
result = await adapter.call_tool("get_current_weather", {"city": "San Francisco"})
```

## Supported MCP Servers

The adapter works with any MCP-compliant server script, including:

- Weather information
- Calculator functions
- File system access
- Web search capabilities
- And many more!

## Testing the Adapter

Two test scripts are included to verify the adapter's functionality:

1. **basic_test.py** - Tests direct MCP tool calls without Gemini

   ```bash
   python basic_test.py
   ```

   This test demonstrates that the adapter can successfully connect to MCP servers and execute tool calls directly.

2. **gemini_test.py** - Tests the full Gemini integration with MCP
   ```bash
   python gemini_test.py
   ```
   This test shows that the adapter can connect Gemini to MCP servers and successfully routes function calls to MCP tools.

### Key Test Results

When running these tests, you should see:

- Successful connection to the MCP server
- Available tools being loaded (add, subtract, multiply, etc.)
- Direct tool calls producing expected results (e.g., 40 + 2 = 42)
- **Gemini using the MCP tools for appropriate queries**

### Important Notes on Async Patterns

The adapter uses asynchronous programming (async/await) for MCP server communication. There are two ways to properly use the adapter:

1. **Using attach_adapter_sync()** (simplest approach)

   - This is a synchronous wrapper that takes care of async handling internally
   - Best for simple scripts or when modifying existing Gemini code with minimal changes
   - Example: `client = attach_adapter_sync(client, servers=["calculator_server.py"])`

2. **Using GeminiMCPAdapter directly in async code** (more flexible)

   - Create the adapter and use await for all operations
   - Must be used inside an async function
   - Example:

     ```python
     async def my_function():
         adapter = GeminiMCPAdapter()
         await adapter.connect_to_server("server_id", "server_path.py")
         result = await adapter.call_tool("tool_name", {"param": "value"})

     asyncio.run(my_function())  # Run the async function
     ```

**IMPORTANT:** Never nest asyncio.run() calls or you'll encounter deadlocks and errors. If you're already in an async context, use await instead of asyncio.run().

## License

MIT
