Your response could not be parsed as a valid JSON tool call. You MUST respond with a single JSON object in this exact format:

```json
{
    "thoughts": ["your reasoning here"],
    "headline": "Short description of action",
    "tool_name": "response",
    "tool_args": {
        "text": "your message to the user"
    }
}
```

Do NOT wrap JSON in markdown code fences. Do NOT use XML-style tool calls. Output ONLY the raw JSON object, nothing else.