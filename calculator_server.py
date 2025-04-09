from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List, Optional
import math

# Create an MCP server named "Calculator"
mcp = FastMCP("Calculator")


@mcp.tool()
async def add(a: float, b: float) -> str:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of a and b
    """
    result = a + b
    return f"{a} + {b} = {result}"


@mcp.tool()
async def subtract(a: float, b: float) -> str:
    """Subtract second number from the first.

    Args:
        a: First number
        b: Second number to subtract from the first

    Returns:
        The result of a - b
    """
    result = a - b
    return f"{a} - {b} = {result}"


@mcp.tool()
async def multiply(a: float, b: float) -> str:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        The product of a and b
    """
    result = a * b
    return f"{a} × {b} = {result}"


@mcp.tool()
async def divide(a: float, b: float) -> str:
    """Divide first number by the second.

    Args:
        a: Numerator
        b: Denominator

    Returns:
        The result of a / b
    """
    if b == 0:
        return "Error: Division by zero is not allowed."
    result = a / b
    return f"{a} ÷ {b} = {result}"


@mcp.tool()
async def power(base: float, exponent: float) -> str:
    """Calculate base raised to the power of exponent.

    Args:
        base: The base number
        exponent: The exponent to raise the base to

    Returns:
        The result of base^exponent
    """
    result = math.pow(base, exponent)
    return f"{base}^{exponent} = {result}"


@mcp.tool()
async def square_root(number: float) -> str:
    """Calculate the square root of a number.

    Args:
        number: The number to find the square root of

    Returns:
        The square root of the number
    """
    if number < 0:
        return "Error: Cannot calculate square root of a negative number."
    result = math.sqrt(number)
    return f"√{number} = {result}"


@mcp.tool()
async def calculate_expression(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: A string containing a mathematical expression (e.g., "2+2*3")

    Returns:
        The result of evaluating the expression
    """
    try:
        # Using eval is generally not safe for user input, but this is just a demo
        # In a production environment, use a proper expression parser
        # We're assuming the server runs in a controlled environment
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"


# Start the server if run directly
if __name__ == "__main__":
    mcp.run()
