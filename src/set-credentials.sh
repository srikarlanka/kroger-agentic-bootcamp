#!/bin/bash

# Load variables from .env
set -o allexport
source .env
set +o allexport

# set the credentials
orchestrate connections set-credentials -a watsonxai --env "draft" -e "modelid=${WATSONX_MODEL_ID}" -e "spaceid=${WATSONX_SPACE_ID}" -e "apikey=${WATSONX_APIKEY}"
orchestrate connections set-credentials -a watsonxai --env "live" -e "modelid=${WATSONX_MODEL_ID}" -e "spaceid=${WATSONX_SPACE_ID}" -e "apikey=${WATSONX_APIKEY}"

orchestrate connections set-credentials -a tavily --env "draft" -e "apikey=${TAVILY_API_KEY}"
orchestrate connections set-credentials -a tavily --env "live" -e "apikey=${TAVILY_API_KEY}"