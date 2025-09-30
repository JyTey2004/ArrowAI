# Todo list

## Tomorrow Must Complete (TMC)
- [ ] Finalize the architecture design for MCP servers and their orchestration.
- [ ] Implement the missing key tools: Code Sandbox MCP Server
- [ ] Test the interaction between MCP servers and the MCP Client (Central Controller).

## Backend

MCP servers will take in a task in natural language and get a structured output. 
They will be orchestrated by a central controller that manages the workflow and data flow between them.

**Missing Key Tools**
- Make Code Sandbox a MCP Server:
    - [ ] Same functionality - Take in task in natural language and LLM in sandbox generates code, with eval loop.
- Deep Research MCP Server: A robust tool for conducting in-depth research and consolidating findings. (https://platform.openai.com/docs/guides/tools-web-search?api-mode=chat)
    - [ ] Implement a research tool that can search the web, extract relevant information, and summarize findings.
    - [ ] Make sure it works well with the existing tools and can be easily integrated into the workflow.
- Presentation Generation MCP Server: A tool that can generate presentations (PPTX) from structured data and text.
    - [ ] Implement a tool that can take in structured data (e.g., JSON, CSV) and text (e.g., markdown) and generate a well-formatted presentation.
    - [ ] Ensure the tool can handle different templates and styles.


## Frontend
