import requests
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections

# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------
# --------------------------------------- Salesforce --------------------------------------
# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------


MY_APP_ID = 'salesforce_oauth2_auth_code_ibm_184bdbd3'

@tool(
    expected_credentials=[
        {"sal": MY_APP_ID, "type": ConnectionType.OAUTH2_AUTH_CODE}
    ]
)
def get_salesforce_cases():
    """
    Fetch Case Id and Status from Salesforce using OAuth2 credentials. 
    Return the information in Tabular format:
    | Case Number | Case ID | Status |
    |-----------------------|----------|
    | Case Number | Case ID | Status |
    """
    # Get Salesforce OAuth2 connection credentials
    creds = connections.oauth2_auth_code(MY_APP_ID)
    base_url = creds.url

    headers = {
        "Authorization": f"Bearer {creds.access_token}",
        "Content-Type": "application/json"
    }

    # SOQL query for Case Number, Id, and Status
    soql_query = "SELECT Id, CaseNumber, Status FROM Case"

    response = requests.get(
        f"{base_url}/services/data/v61.0/query",
        headers=headers,
        params={"q": soql_query}
    )
    response.raise_for_status()

    records = response.json().get("records", [])

    # Return clean list of dictionaries
    return [
        {
            "CaseNumber": r.get("CaseNumber"),
            "Id": r["Id"],
            "Status": r["Status"]
        }
        for r in records
    ]

@tool(
    expected_credentials=[
        {"app_id": MY_APP_ID, "type": ConnectionType.OAUTH2_AUTH_CODE}
    ]
)
def get_case_status(case_identifier: str):
    """
    Fetch the status of a specific Salesforce Case by Case Number or Case ID.
    Automatically searches by Case Number first, then falls back to Case ID if not found.
    
    Args:
        case_identifier: The Case Number (e.g., '00001234') or Case ID
    
    Returns information in tabular format:
    | Case Number | Case ID | Status |
    """
    creds = connections.oauth2_auth_code(MY_APP_ID)
    base_url = creds.url

    headers = {
        "Authorization": f"Bearer {creds.access_token}",
        "Content-Type": "application/json"
    }

    # First, try searching by Case Number
    soql_query = f"SELECT Id, CaseNumber, Status FROM Case WHERE CaseNumber = '{case_identifier}'"
    
    response = requests.get(
        f"{base_url}/services/data/v61.0/query",
        headers=headers,
        params={"q": soql_query}
    )
    response.raise_for_status()

    records = response.json().get("records", [])

    # If found by Case Number, return immediately
    if records:
        case = records[0]
        return {
            "CaseNumber": case.get("CaseNumber"),
            "Id": case["Id"],
            "Status": case["Status"]
        }

    # Fall back to searching by Case ID
    soql_query = f"SELECT Id, CaseNumber, Status FROM Case WHERE Id = '{case_identifier}'"
    
    response = requests.get(
        f"{base_url}/services/data/v61.0/query",
        headers=headers,
        params={"q": soql_query}
    )
    response.raise_for_status()

    records = response.json().get("records", [])

    if not records:
        return {
            "CaseNumber": "N/A",
            "Id": case_identifier,
            "Status": "Not Found"
        }

    case = records[0]
    return {
        "CaseNumber": case.get("CaseNumber"),
        "Id": case["Id"],
        "Status": case["Status"]
    }


@tool(
    expected_credentials=[
        {"app_id": MY_APP_ID, "type": ConnectionType.OAUTH2_AUTH_CODE}
    ]
)
def get_all_case_information(case_identifier: str):
    """
    Fetch all the case information of a specific Salesforce Case by Case Number or Case ID.
    Automatically searches by Case Number first, then falls back to Case ID if not found.
    
    Args:
        case_identifier: The Case Number (e.g., '00001234') or Case ID
    
    Returns information in tabular format:
    | Case Number | Case ID | ... | Status |
    """
    creds = connections.oauth2_auth_code(MY_APP_ID)
    base_url = creds.url

    headers = {
        "Authorization": f"Bearer {creds.access_token}",
        "Content-Type": "application/json"
    }
    fields = "Id, CaseNumber, Status, Description, LastModifiedDate"

    # First, try searching by Case Number
    soql_query = f"SELECT {fields} FROM Case WHERE CaseNumber = '{case_identifier}'"
    
    response = requests.get(
        f"{base_url}/services/data/v61.0/query",
        headers=headers,
        params={"q": soql_query}
    )
    response.raise_for_status()

    records = response.json().get("records", [])
    
    # If found by Case Number, return immediately
    if records:
        case = records[0]
        return case

    # Fall back to searching by Case ID
    soql_query = f"SELECT {fields} FROM Case WHERE Id = '{case_identifier}'"
    
    response = requests.get(
        f"{base_url}/services/data/v61.0/query",
        headers=headers,
        params={"q": soql_query}
    )
    response.raise_for_status()

    records = response.json().get("records", [])

    if not records:
        case = records[0]
        return case

    case = records[0]
    return case
    
# orchestrate tools import \
#   -k python \
#   -f "tools/salesforce.py" \
#   -r "tools/requirements.txt" \
#   -a "salesforce_oauth2_auth_code_ibm_184bdbd3=salesforce_oauth2_auth_code_ibm_184bdbd3"
