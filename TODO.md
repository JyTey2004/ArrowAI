## Today todo

### Context Summarization Logic Update
1. Update CEL.md logic to always summarize the current tool output + previous outputs
    - To retain context with minimal token usage
    - Eval current step -> summarise previous steps + current step -> Always one summary with high context
2. Update RUN_LOG.md and RESEARCH.md with the new logic
3. Test the new logic with a sample workflow to ensure it works as intended


### Update Coding Agent 
1. Update ARTIFACT.md to be more concise and clear
2. Pass previous step's code with summarized context to the coding agent
3. Ensure the coding agent can handle the new input format and generate accurate code
4. Test the coding agent with a sample coding task to verify functionality

