from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.tools.types import (
    PythonToolKind,
    PluginContext,
    AgentPreInvokePayload,
    AgentPreInvokeResult,
)

# Import your specific plugins
# Ensure these filenames match your .py files
from detect_risks_plugin import detect_risks_plugin
from link_safety_plugin import link_safety_plugin
import re

LINK_DETECTION_REGEX = r'(https?://|//|www\.)[^\s]+|[a-zA-Z0-9.-]+\.(com|org|net|edu|io|jpeg|png|jpg)'

# -------------------------------------------------------------------------
# Declarative Configuration with Conditions
# -------------------------------------------------------------------------
PLUGIN_CHAIN = [
    {
        "name": "detect_risks",
        "function": detect_risks_plugin,
        "description": "General safety and risk detection (Harm, PII, HAP)",
        "condition": "always" 
    },
    {
        "name": "link_safety",
        "function": link_safety_plugin,
        "description": "Checks URLs for Imgur or image extensions",
        "condition": "if_link_present"
    }
]

@tool(
    description="Chained safety plugin: Runs general risk detection and conditional link validation.",
    kind=PythonToolKind.AGENTPREINVOKE,
)
def chain_plugins(
    plugin_context: PluginContext,
    agent_pre_invoke_payload: AgentPreInvokePayload,
) -> AgentPreInvokeResult:
    
    current_payload = agent_pre_invoke_payload
    final_result = AgentPreInvokeResult(continue_processing=True)
    
    for plugin_config in PLUGIN_CHAIN:
        # --- CONDITIONAL LOGIC ---
        user_text = ""
        if current_payload.messages:
            last_msg = current_payload.messages[-1]
            user_text = getattr(last_msg.content, 'text', str(last_msg.content))

        # Check if we should skip this plugin based on condition
        if plugin_config["condition"] == "if_link_present":
            if not re.search(LINK_DETECTION_REGEX, user_text, re.IGNORECASE):                # No link detected, skip to next plugin
                continue

        try:
            # Execute the plugin
            result = plugin_config["function"](plugin_context, current_payload)
            
            # If any plugin blocks, the whole chain blocks
            if not result.continue_processing:
                final_result.continue_processing = False
                final_result.modified_payload = result.modified_payload
                return final_result
            
            # Carry forward modifications (e.g., masked text)
            if result.modified_payload:
                current_payload = result.modified_payload
                
        except Exception as e:
            # Safety fallback: Log error and stop for security
            print(f"Error in {plugin_config['name']}: {e}")
            final_result.continue_processing = False
            return final_result
    
    final_result.modified_payload = current_payload
    return final_result