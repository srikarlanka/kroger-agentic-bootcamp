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
# CONFIGURATION
# ============================================================================

SAFE_DOMAINS = [r"imgur\.com", r"i\.imgur\.com"]
SAFE_EXTENSIONS = [r"\.png", r"\.jpg", r"\.jpeg", r"\.gif", r"\.webp"]

BLOCK_MESSAGE = (
    "I'm sorry, but your message contains a link that does not meet our safety requirements. "
    "Currently, I only support links from Imgur or direct image files (PNG, JPG, JPEG, GIF)."
)

def is_link_safe(url: str) -> bool:
    """Checks if a URL is safe based on domain or file extension."""
    for domain in SAFE_DOMAINS:
        if re.search(domain, url, re.IGNORECASE):
            return True

    for ext in SAFE_EXTENSIONS:
        if re.search(ext + r"(\?.*)?$", url, re.IGNORECASE):
            return True

    return False

@tool(
    description="Checks user input for URLs and blocks unsafe links.",
    kind=PythonToolKind.AGENTPREINVOKE,
)
def link_safety_plugin(
    plugin_context: PluginContext,
    agent_pre_invoke_payload: AgentPreInvokePayload
) -> AgentPreInvokeResult:
    # 1. Handle empty payload cases
    if not agent_pre_invoke_payload or not agent_pre_invoke_payload.messages:
        # Pass the payload back even if empty/invalid to maintain flow
        return AgentPreInvokeResult(
            continue_processing=True, 
            modified_payload=agent_pre_invoke_payload
        )

    last_msg = agent_pre_invoke_payload.messages[-1]

    # Extract text content safely
    if hasattr(last_msg.content, 'text'):
        user_text = last_msg.content.text
    elif isinstance(last_msg.content, str):
        user_text = last_msg.content
    else:
        user_text = ""

    # 2. Handle empty text
    if not user_text:
        return AgentPreInvokeResult(
            continue_processing=True, 
            modified_payload=agent_pre_invoke_payload
        )

    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?\S*)?'
    found_links = re.findall(url_pattern, user_text)

    if found_links:
        for link in found_links:
            if not is_link_safe(link):
                # BLOCK LOGIC
                block_content = TextContent(type="text", text=BLOCK_MESSAGE)
                block_msg = Message(role=Role.ASSISTANT, content=block_content)

                new_payload = agent_pre_invoke_payload.model_copy(deep=True)
                new_payload.messages[-1] = block_msg

                return AgentPreInvokeResult(
                    continue_processing=False, 
                    modified_payload=new_payload
                )

    # 3. SUCCESS CASE (Safe links or no links)
    # CRITICAL FIX: You must return the payload here, otherwise the agent receives nothing.
    return AgentPreInvokeResult(
        continue_processing=True, 
        modified_payload=agent_pre_invoke_payload
    )