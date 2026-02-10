import requests
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections


# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------
# --------------------------------------- ServiceNow --------------------------------------
# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------


MY_APP_ID = 'servicenow_oauth2_auth_code_ibm_184bdbd3'

@tool(
    name="get_ticket_test",
    description="Get service now tickets based off of ticket number.",
    expected_credentials=[
        {"app_id": MY_APP_ID, "type": ConnectionType.OAUTH2_AUTH_CODE}
    ]
)
def get_ticket_test(ticket_number: str)-> dict: 
    """
    Fetch a specific ticket from ServiceNow by ticket number.
    
    Args:
        ticket_number: The ticket number to search for (e.g., "INC0012345")
    
    Returns the ticket information including:
    - Ticket Number
    - Description
    - Short Description
    - Priority
    - State
    - Assignment Group
    - Assigned To
    - Comments and Work Notes
    - Created On
    - Opened At
    - Closed At
    - Due Date
    """
    # Get ServiceNow OAuth2 connection credentials
    creds = connections.oauth2_auth_code(MY_APP_ID)
    base_url = creds.url

    headers = {
        "Authorization": f"Bearer {creds.access_token}",
        "Content-Type": "application/json"
    }

    # Query parameters for ServiceNow API
    params = {
        "sysparm_query": f"number={ticket_number}",
        "sysparm_display_value": True,
        "sysparm_limit": 10,
        "sysparm_offset": 0
    }

    response = requests.get(
        f"{base_url}/api/now/table/ticket",
        headers=headers,
        params=params
    )
    response.raise_for_status()

    records = response.json().get("result", [])

    if not records:
        return {
            "ticket_number": ticket_number,
            "status": "Not Found",
            "message": f"No ticket found with number: {ticket_number}"
        }

    ticket = records[0]
    
    # Extract assignment group and assigned to (handle both dict and string)
    assignment_group = (
        ticket.get("assignment_group", {}).get("display_value", "")
        if isinstance(ticket.get("assignment_group"), dict)
        else ticket.get("assignment_group", "")
    )
    
    assigned_to = (
        ticket.get("assigned_to", {}).get("display_value", "")
        if isinstance(ticket.get("assigned_to"), dict)
        else ticket.get("assigned_to", "")
    )

    return {
        "ticket_number": ticket.get("number", ""),
        "description": ticket.get("description", ""),
        "short_description": ticket.get("short_description", ""),
        "priority": ticket.get("priority", ""),
        "state": ticket.get("state", ""),
        "assignment_group": assignment_group,
        "assigned_to": assigned_to,
        "comments_and_work_notes": ticket.get("comments_and_work_notes", ""),
        "system_id": ticket.get("sys_id", ""),
        "created_on": ticket.get("sys_created_on", ""),
        "opened_at": ticket.get("opened_at", ""),
        "closed_at": ticket.get("closed_at", ""),
        "due_date": ticket.get("due_date", "")
    }

# orchestrate tools import -k python \
# -f ./tools/service_now_tool.py \
# -r tools/requirements.txt \
# -a "servicenow_oauth2_auth_code_ibm_184bdbd3=servicenow_oauth2_auth_code_ibm_184bdbd3"