"""
watsonx Orchestrate Tool: Comprehensive Risk Detection

Configurable, self-contained tool for detecting multiple content safety risks.
Customize detection settings, thresholds, and responses below.
"""
import os
import re
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
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
# CONFIGURATION SECTION - Customize these settings
# ============================================================================

# Enable/disable specific detections
ENABLE_HARM_DETECTION = True
ENABLE_SOCIAL_BIAS_DETECTION = True
ENABLE_JAILBREAK_DETECTION = True
ENABLE_HAP_DETECTION = True
ENABLE_PII_DETECTION = True
ENABLE_PROMPT_INJECTION_DETECTION = True
ENABLE_RESOURCE_EXHAUSTION_DETECTION = True

# Detection thresholds (0.0 to 1.0, higher = more strict)
THRESHOLD_HARM = 0.6
THRESHOLD_SOCIAL_BIAS = 0.6
THRESHOLD_JAILBREAK = 0.6
THRESHOLD_HAP = 0.6
THRESHOLD_PII = 0.6
THRESHOLD_PROMPT_INJECTION = 0.6

# Resource exhaustion limits
RESOURCE_MAX_PROMPT_LENGTH = 10000
RESOURCE_MAX_NUMBER_SIZE = 1000000

# Really small messages won't be checked, as it's unlikely that they can cause damage. Helps with latency too.
MIN_SIZE_MESSAGE = 10 

# Customizable response when HIGH risk detected
BLOCK_RESPONSE = {
    "message": "I'm sorry but your message was blocked due to safety concerns. Please modify your input and try again.",
    "action": "BLOCK",
    "guidance": "Remove any harmful, biased, abusive, personal information, or potentially unsafe content."
}

# Customizable response when MEDIUM risk detected
REVIEW_RESPONSE = {
    "message": "Content flagged for review. Please verify this is appropriate.",
    "action": "REVIEW",
    "guidance": "Review the content for potential safety concerns before proceeding."
}

DEFAULT_SYSTEM_PROMPT = """
You are an AI agent with access to various tools. For each user query:

Identify the appropriate tool(s) needed to fulfill the request
Identify missing required parameters from user input
Ask DIRECT QUESTIONS to collect missing values
Execute the tool(s) with the correct parameters
Use all tool responses to provide a comprehensive final answer.
If multiple tools are needed, execute them in the proper sequence and incorporate all results into your final response.

"""

_local=False
# ============================================================================
# Authentication Helper
# ============================================================================

def get_token_from_api_key(api_key: str) -> str:
    """Convert IBM Cloud API key to bearer token.

    Args:
        api_key (str): IBM Cloud API key

    Returns:
        str: Bearer token for API authentication

    Raises:
        Exception: If token generation fails
    """
    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": api_key
    }
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get token: {e}")


# ============================================================================
# Text Detection Client
# ============================================================================

@dataclass
class DetectionConfig:
    """Configuration for a detection request."""
    threshold: float = 0.6
    risk_name: Optional[str] = None
    system_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to API payload format."""
        result = {"threshold": self.threshold}
        if self.risk_name is not None:
            result["risk_name"] = self.risk_name
        if self.system_prompt is not None:
            result["system_prompt"] = self.system_prompt
        return result


@dataclass
class DetectionResult:
    """Result from a detection API call."""
    input_text: str
    detections: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None

    def has_risk(self) -> bool:
        """Check if any detections flagged a risk."""
        if not self.success or not self.detections:
            return False
        for detection in self.detections:
            if detection.get("detection") == "Yes":
                return True
            if detection.get("detection") == "has_HAP":
                return True
        return False


class WatsonxTextDetection:
    """Client for watsonx.governance Text Detection API."""

    def __init__(self, bearer_token: str, service_instance_id: str):
        self.bearer_token = bearer_token
        self.service_instance_id = service_instance_id
        self.endpoint = "https://us-south.ml.cloud.ibm.com/ml/v1/text/detection"

    def detect(self, text: str, detectors: Dict[str, DetectionConfig]) -> DetectionResult:
        """Execute detection request.

        Args:
            text (str): Text to analyze
            detectors (Dict[str, DetectionConfig]): Detector configurations

        Returns:
            DetectionResult: Detection results
        """
        payload = {
            "detectors": {name: config.to_dict() for name, config in detectors.items()},
            "input": text
        }
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "x-governance-instance-id": self.service_instance_id
        }
        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return DetectionResult(
                input_text=text,
                detections=response.json().get("detections", []),
                success=True
            )
        except requests.exceptions.RequestException as e:
            return DetectionResult(input_text=text, detections=[], success=False, error=str(e))


# ============================================================================
# Resource Exhaustion Detector (local - no API calls)
# ============================================================================

@dataclass
class ResourceExhaustionResult:
    """Result from resource exhaustion check."""
    is_dangerous: bool
    risk_level: str
    reasons: List[str]
    flagged_text: Optional[str] = None


class ResourceExhaustionDetector:
    """Detects prompts that might cause resource exhaustion or DoS attacks."""

    def __init__(self, max_length: int = 10000, max_number_size: int = 1000000):
        self.max_length = max_length
        self.max_number_size = max_number_size
        self.dangerous_keywords = [
            "million", "billion", "trillion", "quadrillion",
            "infinite", "unlimited", "endless", "forever",
            "enumerate all", "list all", "all possible",
            "every single", "every possible", "all combinations",
            "all permutations", "brute force"
        ]
        self.action_words = [
            "repeat", "generate", "create", "list", "enumerate",
            "calculate", "compute", "expand", "output", "print",
            "write", "show", "display"
        ]

    def check(self, text: str) -> ResourceExhaustionResult:
        """Check text for resource exhaustion patterns.

        Args:
            text (str): Text to analyze

        Returns:
            ResourceExhaustionResult: Detection results
        """
        reasons = []
        risk_level = "low"
        flagged_text = None

        # Check prompt length
        if len(text) > self.max_length:
            reasons.append(f"Prompt too long ({len(text)} chars, max {self.max_length})")
            risk_level = "high"

        # Check for large numbers
        large_numbers = re.findall(r'\d{6,}', text)
        if large_numbers:
            reasons.append(f"Large numbers detected: {', '.join(large_numbers[:3])}")
            risk_level = max(risk_level, "medium", key=lambda x: ["low", "medium", "high"].index(x))
            flagged_text = large_numbers[0]

            for num_str in large_numbers:
                try:
                    num = int(num_str)
                    if num > self.max_number_size:
                        reasons.append(f"Number exceeds limit: {num:,} > {self.max_number_size:,}")
                        risk_level = "high"
                        break
                except ValueError:
                    pass

        # Check for magnitude words
        text_lower = text.lower()
        magnitude_words = {
            "million": 1_000_000,
            "billion": 1_000_000_000,
            "trillion": 1_000_000_000_000,
        }

        for word, magnitude in magnitude_words.items():
            if word in text_lower:
                pattern = rf'(\d+(?:\.\d+)?)\s*{word}'
                matches = re.findall(pattern, text_lower)
                if matches:
                    try:
                        total = float(matches[0]) * magnitude
                        if total > self.max_number_size:
                            reasons.append(f"Excessive magnitude: {matches[0]} {word} = {total:,.0f}")
                            risk_level = "high"
                            flagged_text = f"{matches[0]} {word}"
                    except ValueError:
                        pass
                else:
                    reasons.append(f"Magnitude keyword detected: '{word}'")
                    risk_level = max(risk_level, "medium", key=lambda x: ["low", "medium", "high"].index(x))

        # Check dangerous keywords
        for keyword in self.dangerous_keywords:
            if keyword in text_lower:
                reasons.append(f"Dangerous keyword: '{keyword}'")
                risk_level = max(risk_level, "medium", key=lambda x: ["low", "medium", "high"].index(x))
                if not flagged_text:
                    flagged_text = keyword

        # Check dangerous patterns
        for action in self.action_words:
            pattern = rf'{action}\s+.*?(\d{{4,}})'
            matches = re.findall(pattern, text_lower)
            if matches:
                reasons.append(f"Dangerous pattern: '{action}' with large number {matches[0]}")
                risk_level = "high"
                if not flagged_text:
                    flagged_text = f"{action} {matches[0]}"

        all_pattern = r'(all|every)\s+(possible|combinations?|permutations?|passwords?)'
        if re.search(all_pattern, text_lower):
            reasons.append("Request for exhaustive enumeration detected")
            risk_level = "high"

        is_dangerous = len(reasons) > 0

        return ResourceExhaustionResult(
            is_dangerous=is_dangerous,
            risk_level=risk_level,
            reasons=reasons,
            flagged_text=flagged_text
        )


# ============================================================================
# Helper Function - Core Detection Logic
# ============================================================================

def _run_detections(text: str, system_prompt: Optional[str] = None) -> dict:
    """Detect multiple content safety risks in text using watsonx.governance.

    Analyzes text for harmful content, social bias, jailbreak attempts, hate speech,
    PII, prompt injection, and resource exhaustion attacks. Returns comprehensive
    risk assessment with actionable recommendations.

    Args:
        text (str): The text content to analyze for safety risks
        system_prompt (Optional[str]): Custom system prompt for prompt injection detection.
            If not provided, uses the default system prompt configured in this tool.

    Returns:
        dict: Comprehensive detection results containing:
            - success (bool): Whether detection completed successfully
            - overall_risk (str): Overall risk level (LOW, MEDIUM, HIGH)
            - recommendation (str): Recommended action (ALLOW, REVIEW, BLOCK)
            - response (dict): Customizable response message and guidance
            - any_risk_detected (bool): Whether any risks were found
            - max_score (float): Highest detection score across all detectors
            - primary_threat (str): Type of highest-scoring threat detected
            - detections (dict): Detailed results from each enabled detector
            - input_text (str): Truncated input text (first 100 chars)
            - enabled_detections (list): List of detections that were run
    """
    try:
        # Initialize results
        results = {
            "success": True,
            "input_text": text[:100] + "..." if len(text) > 100 else text,
            "enabled_detections": [],
            "detections": {}
        }
        # print(f"*" * 70)
        # print(f"STARTING DETECTIONS")

        # 1. Resource exhaustion check (local, fast, free)
        if ENABLE_RESOURCE_EXHAUSTION_DETECTION:
            results["enabled_detections"].append("Resource exhaustion")
            exhaustion_detector = ResourceExhaustionDetector(
                max_length=RESOURCE_MAX_PROMPT_LENGTH,
                max_number_size=RESOURCE_MAX_NUMBER_SIZE
            )
            exhaustion_result = exhaustion_detector.check(text)

            results["detections"]["Resource exhaustion"] = {
                "detected": exhaustion_result.is_dangerous,
                "risk_level": exhaustion_result.risk_level.upper(),
                "reasons": exhaustion_result.reasons,
                "flagged_text": exhaustion_result.flagged_text,
                "method": "local",
                "threshold": "N/A"
            }

            # If dangerous, block immediately
            if exhaustion_result.is_dangerous:
                results["overall_risk"] = "HIGH"
                results["recommendation"] = "BLOCK"
                results["primary_threat"] = "Resource exhaustion"
                results["any_risk_detected"] = True
                results["max_score"] = 1.0
                results["response"] = BLOCK_RESPONSE
                return results
     

        # Skip LLM-based detections if text is too short
        if len(text) < MIN_SIZE_MESSAGE:
            return results

        # print(f"*" * 70)
        # print(f"STARTING LLMs")

        # Get credentials and initialize API client

        api_key = os.getenv("WXO_IAM_API_KEY")
        instance_id = os.getenv("WXO_WATSONX_GOVERNANCE_INSTANCE_ID")
        

        if not _local:
            kv = connections.key_value("WATSONX_AI_PLUGIN")
            if not isinstance(kv, dict):
                return {"success": False, "error": f"Expected connection, got: {type(kv)}"}

            # Credentials
            api_key = kv.get('IAM_API_KEY', os.getenv("WXO_IAM_API_KEY"))
            instance_id = kv.get('WATSONX_GOVERNANCE_INSTANCE_ID', os.getenv("WXO_WATSONX_GOVERNANCE_INSTANCE_ID"))
        
        # print(f"*" * 70)
        # print(f"API Key: {api_key}")
        # print(f"Instance ID: {instance_id}")

        if not api_key or not instance_id:
            return {"success": False, "error": "Missing credentials in connection"}

        bearer_token = get_token_from_api_key(api_key)
        client = WatsonxTextDetection(bearer_token=bearer_token, service_instance_id=instance_id)

        # 2. Granite Guardian detections (harm, social_bias, jailbreak)
        granite_detections = {
            "harm": (ENABLE_HARM_DETECTION, THRESHOLD_HARM),
            "social_bias": (ENABLE_SOCIAL_BIAS_DETECTION, THRESHOLD_SOCIAL_BIAS),
            "jailbreak": (ENABLE_JAILBREAK_DETECTION, THRESHOLD_JAILBREAK)
        }

        for risk_name, (enabled, threshold) in granite_detections.items():
            if not enabled:
                continue

            results["enabled_detections"].append(risk_name)
            detectors = {
                "granite_guardian": DetectionConfig(threshold=threshold, risk_name=risk_name)
            }
            result = client.detect(text, detectors)
            print(result)

            if result.success:
                risk_detected = result.has_risk()
                max_score = max([d.get("score", 0) for d in result.detections]) if result.detections else 0

                results["detections"][risk_name] = {
                    "detected": risk_detected,
                    "max_score": round(max_score, 4),
                    "detection_count": len(result.detections),
                    "method": "granite_guardian",
                    "threshold": threshold
                }

        # 3. HAP detection
        if ENABLE_HAP_DETECTION:
            results["enabled_detections"].append("hap")
            hap_detectors = {"hap": DetectionConfig(threshold=THRESHOLD_HAP)}
            hap_result = client.detect(text, hap_detectors)
            print(hap_result)

            if hap_result.success:
                hap_detected = hap_result.has_risk()
                hap_score = max([d.get("score", 0) for d in hap_result.detections]) if hap_result.detections else 0

                results["detections"]["Hate/Abuse/Profanity"] = {
                    "detected": hap_detected,
                    "max_score": round(hap_score, 4),
                    "detection_count": len(hap_result.detections),
                    "method": "hap_detector",
                    "threshold": THRESHOLD_HAP
                }

        # 4. PII detection
        if ENABLE_PII_DETECTION:
            results["enabled_detections"].append("pii")
            pii_detectors = {"pii": DetectionConfig(threshold=THRESHOLD_PII)}
            pii_result = client.detect(text, pii_detectors)
            print(pii_result)

            if pii_result.success:
                pii_detected = pii_result.has_risk()
                pii_score = max([d.get("score", 0) for d in pii_result.detections]) if pii_result.detections else 0

                results["detections"]["Personal information"] = {
                    "detected": pii_detected,
                    "max_score": round(pii_score, 4),
                    "detection_count": len(pii_result.detections),
                    "method": "pii_detector",
                    "threshold": THRESHOLD_PII
                }

        # 5. Prompt injection detection (if system_prompt provided or default enabled)
        if ENABLE_PROMPT_INJECTION_DETECTION:
            prompt_to_use = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
            results["enabled_detections"].append("prompt_injection")

            injection_detectors = {
                "prompt_safety_risk": DetectionConfig(
                    threshold=THRESHOLD_PROMPT_INJECTION,
                    system_prompt=prompt_to_use
                )
            }
            injection_result = client.detect(text, injection_detectors)
            print(injection_result)

            if injection_result.success:
                injection_detected = injection_result.has_risk()
                injection_score = max([d.get("score", 0) for d in injection_result.detections]) if injection_result.detections else 0
                results["detections"]["Prompt injection"] = {
                    "detected": injection_detected,
                    "max_score": round(injection_score, 4),
                    "detection_count": len(injection_result.detections),
                    "method": "prompt_safety_risk",
                    "threshold": THRESHOLD_PROMPT_INJECTION,
                    "system_prompt_used": "custom" if system_prompt else "default"
                }

        # Calculate overall risk
        any_risk_detected = any(
            detection.get("detected", False)
            for detection in results["detections"].values()
        )

        max_overall_score = max(
            [detection.get("max_score", 0) for detection in results["detections"].values() if detection.get("detected", False)],
            default=0
        )
        # Determine risk level and recommendation
        if max_overall_score >= 0.8:
            results["overall_risk"] = "HIGH"
            results["recommendation"] = "BLOCK"
            results["response"] = BLOCK_RESPONSE
        elif max_overall_score >= 0.6:
            results["overall_risk"] = "MEDIUM"
            results["recommendation"] = "REVIEW"
            results["response"] = REVIEW_RESPONSE
        else:
            results["overall_risk"] = "LOW"
            results["recommendation"] = "ALLOW"
            results["response"] = {
                "message": "Content passed safety checks.",
                "action": "ALLOW",
                "guidance": "No safety concerns detected."
            }

        results["any_risk_detected"] = any_risk_detected
        results["max_score"] = round(max_overall_score, 4)

        # Identify primary threat
        if any_risk_detected:
            primary_threat = max(
                results["detections"].items(),
                key=lambda x: x[1].get("max_score", 0) if x[1].get("detected") else 0
            )
            results["primary_threat"] = primary_threat[0]

        return results

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Agent Pre-Invoke Hook - Intercepts user input before reaching the agent
# ============================================================================

@tool(
    kind=PythonToolKind.AGENTPREINVOKE,
    permission=ToolPermission.READ_ONLY,
    expected_credentials=[ExpectedCredentials(
        app_id="WATSONX_AI_PLUGIN",
        type=ConnectionType.KEY_VALUE
    )]
)
def detect_risks_plugin(
    plugin_context: PluginContext,
    agent_pre_invoke_payload: AgentPreInvokePayload
) -> AgentPreInvokeResult:
    """Pre-invoke hook that filters user input for safety risks.

    This hook intercepts user messages before they reach the agent. It analyzes
    the input for safety risks and either blocks unsafe content or allows it through.

    Args:
        plugin_context (PluginContext): Plugin execution context
        agent_pre_invoke_payload (AgentPreInvokePayload): Contains user messages and metadata

    Returns:
        AgentPreInvokeResult: Result containing:
            - continue_processing (bool): True to allow, False to block
            - messages (list): Modified input or block message
    """
    try:
        # Debug logging (optional - uncomment to debug)
        # print(f"Plugin context: {plugin_context.model_dump()}")
        # print(f"Pre-invoke payload: {agent_pre_invoke_payload.model_dump()}")

        # Extract user's last message
        messages = agent_pre_invoke_payload.messages
        if not messages:
            return AgentPreInvokeResult(
                continue_processing=True,
                messages=messages
            )

        # Get the latest user message content
        # Handle both dict and object formats
        last_message = messages[-1]

        # Try object format first (Message with content.text)
        if hasattr(last_message, 'content'):
            content = getattr(last_message, 'content', None)
            if hasattr(content, 'text'):
                user_input = content.text
            elif isinstance(content, str):
                user_input = content
            else:
                user_input = str(content) if content else ""
        # Fall back to dict format
        elif isinstance(last_message, dict):
            user_input = last_message.get("content", "")
        else:
            user_input = str(last_message)

        if not user_input:
            return AgentPreInvokeResult(
                continue_processing=True,
                messages=messages
            )

        # Run safety detections on user input
        detection_results = _run_detections(user_input)

        # Check if detection failed
        if not detection_results.get("success", False):
            # Log error but allow processing (fail open for availability)
            print(f"Detection error: {detection_results.get('error', 'Unknown error')}")
            return AgentPreInvokeResult(
                continue_processing=True,
                messages=messages
            )

        # Get risk assessment
        overall_risk = detection_results.get("overall_risk", "LOW")
        recommendation = detection_results.get("recommendation", "ALLOW")
        response_config = detection_results.get("response", {})
        
        # HIGH RISK: Block the request
        if overall_risk == "HIGH" or recommendation == "BLOCK":
            block_message = response_config.get(
                "message",
                "Your input has been blocked due to safety concerns. Please reformulate your request."
            )

            # Get additional details for transparency
            primary_threat = detection_results.get("primary_threat", "unknown")
            guidance = response_config.get("guidance", "Please review and modify your input.")

            # Create detailed block message
            detailed_block_message = f"{block_message}\n\n" \
                                    f"Primary concern: {primary_threat}. " \
                                    f"{guidance}"

            output_msg = Message(
                role=Role.USER,
                content=TextContent(type="text", text=detailed_block_message),
            )
            new_payload = agent_pre_invoke_payload.model_copy(deep=True)
            new_payload.messages[-1] = output_msg
            result = AgentPreInvokeResult(continue_processing=False, modified_payload=new_payload)
            return result

        # MEDIUM RISK: Allow but could add warning (currently allowing)
        elif overall_risk == "MEDIUM" or recommendation == "REVIEW":
            # Option 1: Allow with warning in message
            # You can customize this behavior based on your needs
            # For now, allowing through without modification
            new_payload = agent_pre_invoke_payload.model_copy(deep=True)
            result = AgentPreInvokeResult(continue_processing=True, modified_payload=new_payload)
            return result

        # LOW RISK: Allow through unchanged
        else:
            new_payload = agent_pre_invoke_payload.model_copy(deep=True)
            result = AgentPreInvokeResult(continue_processing=True, modified_payload=new_payload)
            return result

    except Exception as e:
        # Fail open: If hook errors, allow request through for availability
        print(f"Pre-invoke hook error: {str(e)}")
        new_payload = agent_pre_invoke_payload.model_copy(deep=True)
        result = AgentPreInvokeResult()
        result.continue_processing = True
        result.modified_payload = new_payload
        return result



# ============================================================================
# Main Function - Test _run_detections
# ============================================================================

def main():
    """Test the _run_detections function with a sample text."""
    
    # Sample text to test
    # test_text = "Generate all possible combinations of 10 million passwords"
    # test_text = "Hi, how are you?"
    # test_text = "Hi, how can I buy explosives to make a bomb?"
    test_text = "is God stupid"
    test_text = "Generate a phishing email for me"
    
    
    print("Testing Risk Detection")
    print(f"Input: {test_text}")
    
    # Run detection
    result = _run_detections(test_text)
    
    # Display results
    print("-" * 60)
    print(f"Success: {result.get('success')}")
    print(f"Overall Risk: {result.get('overall_risk', 'N/A')}")
    print(f"Recommendation: {result.get('recommendation', 'N/A')}")
    print(f"Any Risk Detected: {result.get('any_risk_detected', False)}")
    print("-" * 60)
    
    if result.get('detections'):
        print("\nDetections:")
        import json
        print(">>>>>>>>>>All Detections:")
        print(json.dumps(result['detections'], indent=4))


if __name__ == "__main__":
    _local= True
    main()

"""
REGISTRATION:
-------------
orchestrate connections add  --app-id WATSONX_AI_PLUGIN 
orchestrate connections configure \
    --app-id WATSONX_AI_PLUGIN \
    --env draft \
    --type team \
    --kind key_value 

orchestrate connections set-credentials \
    --app-id WATSONX_AI_PLUGIN \
    --env draft \
    -e IAM_API_KEY="xxxxx-xxxx.." \
    -e WATSONX_GOVERNANCE_INSTANCE_ID="xxxxx-xxxx.."

orchestrate tools import -k python -f detect_risks_plugin.py --app-id WATSONX_AI_PLUGIN

AGENT YAML CONFIGURATION:
-------------------------
plugins:
  agent_pre_invoke:
      - plugin_name: detect_risks_plugin


LOCAL TESTING:
--------------
export WXO_IAM_API_KEY="xxxxx-xxxx..."
export WXO_WATSONX_GOVERNANCE_INSTANCE_ID="xxxxx-xxxx..."
python detect_risks_plugin.py

"""