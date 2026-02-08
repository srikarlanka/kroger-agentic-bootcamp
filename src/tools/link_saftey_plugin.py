import re
from typing import List
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.tools.types import (
    PythonToolKind,
    PluginContext,
    AgentPreInvokePayload,
    AgentPreInvokeResult,
    Message,
    TextContent,
    Role
)

# ============================================================================
# CONFIGURATION - Define what is considered "Safe"
# ============================================================================

# Allowed domains (e.g., imgur)
SAFE_DOMAINS = [r"imgur\.com", r"i\.imgur\.com"]

# Allowed image extensions
SAFE_EXTENSIONS = [r"\.png", r"\.jpg", r"\.jpeg", r"\.gif", r"\.webp"]

BLOCK_MESSAGE = (
    "I'm sorry, but your message contains a link that does not meet our safety requirements. "
    "Currently, I only support links from Imgur or direct image files (PNG, JPG, JPEG, GIF)."
)

def is_link_safe(url: str) -> bool:
    """
    Checks if a URL is safe based on domain or file extension.
    """
    # Check for safe domains
    for domain in SAFE_DOMAINS:
        if re.search(domain, url, re.IGNORECASE):
            return True
            
    # Check for safe image extensions
    for ext in SAFE_EXTENSIONS:
        if re.search(ext + r"(\?.*)?$", url, re.IGNORECASE):
            return True
            
    return False

# ============================================================================
# Tool Definition
# ============================================================================

@tool(
    description="Checks user input for URLs and blocks the request if the link is not a trusted image source.",
    kind=PythonToolKind.AGENTPREINVOKE,
)
def link_safety_plugin(
    plugin_context: PluginContext,
    agent_pre_invoke_payload: AgentPreInvokePayload
) -> AgentPreInvokeResult:
    """
    Pre-invoke hook that validates URL safety.
    """
    # 1. Guard clause: Ensure there are messages to check
    if not agent_pre_invoke_payload or not agent_pre_invoke_payload.messages:
        return AgentPreInvokeResult(continue_processing=True)

    # 2. Extract text from the last message
    last_msg = agent_pre_invoke_payload.messages[-1]
    user_text = ""
    
    if hasattr(last_msg.content, 'text'):
        user_text = last_msg.content.text
    elif isinstance(last_msg.content, str):
        user_text = last_msg.content

    if not user_text:
        return AgentPreInvokeResult(continue_processing=True)

    # 3. Find all URLs in the text
    # Regex to find standard http/https links
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?\S*)?'
    found_links = re.findall(url_pattern, user_text)

    # 4. Perform Safety Check if links exist
    if found_links:
        for link in found_links:
            if not is_link_safe(link):
                # LINK IS UNSAFE: Create a block response
                block_content = TextContent(type="text", text=BLOCK_MESSAGE)
                block_msg = Message(role=Role.ASSISTANT, content=block_content)
                
                # Copy payload and replace the last message with the block warning
                new_payload = agent_pre_invoke_payload.model_copy(deep=True)
                new_payload.messages[-1] = block_msg
                
                return AgentPreInvokeResult(
                    continue_processing=False, 
                    modified_payload=new_payload
                )

    # 5. ALL CLEAR: Continue to the agent
    return AgentPreInvokeResult(continue_processing=True)