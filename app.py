import openai 
import streamlit as st

import json 

import logging
from ui import display_calculation_results, create_sidebar
from calculation import CalculationService
from prompts import GREETING_PROMPT, NEGATIVE_FEEDBACK_PROMPT, IRREVELANT_PROMPT, ENTITY_EXTRACTOR_PROMPT, INTENT_PROMPT, INTENT_RESPONSE_FORMAT, ENTITY_EXTRACTOR_RESPONSE_FORMAT, DATA_SUMMARY_PROMPT, USER_CONFIRMATION_STATE_PROMPT, USER_CONFIRMATION_STATE_RESPONSE_FORMAT 
from auth import check_authentication, show_login_page, add_logout_button

from config import SHEET_URL, OPENAI_API_KEY, CREDENTIALS_DATA

LOGGING_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'handlers': [
        logging.FileHandler('indofast_copilot.log'),
        logging.StreamHandler()
    ]
}


logging.basicConfig(**LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Page configuration
OPENAI_MODEL = "gpt-4.1-mini"  # Set your OpenAI model here
PAGE_CONFIG = {
    'page_title': "IndoFast AI Copilot",
    'page_icon': "🔋",
    'layout': "wide",
    'initial_sidebar_state': "expanded"
}



st.set_page_config(**PAGE_CONFIG)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sidebar-content {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# Add your model's price per 1K tokens (example: $0.0015 for gpt-3.5-turbo)
MODEL_PRICE_PER_INPUT_1K_TOKENS = 0.0004
MODEL_PRICE_PER_OUTPUT_1K_TOKENS = 0.0016

class OPENAI_CALL:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    def chat_completion(self, system_prompt: str, messages: list[dict], response_format = None, model: str = OPENAI_MODEL, temperature: float = 0.0, max_tokens: int = 500):
        """
        Call OpenAI's chat completion API with the provided messages.
        Returns a tuple: (response_content, usage_dict)
        """
        input_messages = []
        if system_prompt:
            input_messages.append({"role": "system", "content": system_prompt})
        input_messages.extend(messages)
        if response_format is not None:
            response = openai.chat.completions.create(
                model=model,
                messages=input_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        else:
            response = openai.chat.completions.create(
                model=model,
                messages=input_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        # Extract usage info
        usage = response.usage if hasattr(response, "usage") else None
        return response.choices[0].message.content, usage

def log_openai_cost(usage, logger):
    if usage:
        total_tokens = usage.total_tokens
        cost = ((usage.prompt_tokens / 1000) * MODEL_PRICE_PER_INPUT_1K_TOKENS) + ((usage.completion_tokens/1000)* MODEL_PRICE_PER_OUTPUT_1K_TOKENS)
        logger.info(f"OpenAI API usage: prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}, total_tokens={total_tokens}, estimated_cost=${cost:.6f}")

def initialize_session_state():
    """Initialize session state variables."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    # if 'awaiting_confirmation' not in st.session_state:
    #     st.session_state.awaiting_confirmation = False
    if 'calculation_results' not in st.session_state:
        st.session_state.calculation_results = None

if __name__ == "__main__":
    # Initialize session state
    initialize_session_state()
    
    # Check authentication first
    if not check_authentication():
        show_login_page()
        st.stop()
    
    service = CalculationService(CREDENTIALS_DATA)
    
    # Create sidebar with logout button
    create_sidebar()
    add_logout_button()
        
    # Main header
    st.markdown('<h1 style="font-size: 2.5rem; font-weight: bold; color: #ffffff; text-align: center; margin-bottom: 1rem;">🔋 Station Planning Tool</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #ffffff;">Your intelligent assistant for station (QIS) planning</p>', unsafe_allow_html=True)
    
    #Initialize OpenAI client
    openai_client = OPENAI_CALL(OPENAI_API_KEY)
    
    # Chat messages container
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message['role']):
                st.markdown(message['content'])
                if 'data' in message:
                    with st.expander("📊 View Data", expanded=False):
                        display_calculation_results(message['data'])
    
    # Chat input
    if prompt := st.chat_input("💭 Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("🧠 Analyzing your request..."):
                # Call the intent classifier
                intent_response, usage = openai_client.chat_completion(INTENT_PROMPT, st.session_state.messages, INTENT_RESPONSE_FORMAT)
                log_openai_cost(usage, logger)
                intent_response = json.loads(intent_response).get("intent", "")
                logger.info(f"Intent Response: {intent_response}")

                if intent_response == "calculate_stations":
                    entity_response, usage = openai_client.chat_completion(ENTITY_EXTRACTOR_PROMPT, st.session_state.messages, ENTITY_EXTRACTOR_RESPONSE_FORMAT)
                    log_openai_cost(usage, logger)
                    entity_response = json.loads(entity_response)
                    logger.info(f"Entity Response: {entity_response}")

                    entity_response = entity_response.get("locations", [])
                    entity_response = {d["name"].lower(): {k: v for k, v in d.items() if k != "name"} for d in entity_response}
                    missing_info_messages = []
                    for city, config in entity_response.items():
                        missing_fields = []
                        if "station_utilization_percentage" not in config:
                            missing_fields.append("station utilization percentage")
                        if "off_road_vehicle_percentage" not in config:
                            missing_fields.append("off road vehicle percentage")
                        
                        if missing_fields:
                            fields = " and ".join(missing_fields)
                            missing_info_messages.append(f"Please provide {fields} for '{city}'.")

                    if len(missing_info_messages)>0:
                        for msg in missing_info_messages:
                            logger.warning(f"Missing information for calculation: {msg}")
                            all_combined_messages = "\n".join(missing_info_messages)
                        ai_response = "I need some more information to proceed with the calculation. Please provide the following details for each location:" + f"\n\n{all_combined_messages}"
                        st.markdown(ai_response)
                        st.session_state.messages.append({"role": "assistant", "content": ai_response})
                        
                    

                    else:
                        confirmation_state, usage = openai_client.chat_completion(USER_CONFIRMATION_STATE_PROMPT, st.session_state.messages, response_format=USER_CONFIRMATION_STATE_RESPONSE_FORMAT)
                        confirmation_state = json.loads(confirmation_state).get("confirmation_state", "not_confirmed")
                        log_openai_cost(usage, logger)
                        logger.info(f"User Confirmation State: {confirmation_state}")
                        if confirmation_state== "confirmed":
                            # Proceed with calculation
                            with st.spinner("🔄 Processing calculation..."):
                                response = service.calculate_swap_stations(
                                    entities=entity_response ,
                                    sheet_url=SHEET_URL
                                )
                            ai_response, usage = openai_client.chat_completion(DATA_SUMMARY_PROMPT, [{"role": "user" , "content": f" swap stations data: {json.dumps(response)} entities extracted : {json.dumps(entity_response)}"}], max_tokens=1000)
                            log_openai_cost(usage, logger)
                            logging.info(f"AI Response based on data: {ai_response}")
                            st.markdown(ai_response)
                            # Display fancy results
                            logger.info(f"Calculation Response: {response}")
                            display_calculation_results(response)
                            # st.session_state.awaiting_confirmation = False
                            st.session_state.messages.append({"role": "assistant", "content": ai_response, "data": response})
                        else:
                            ai_response = f"🚗 Please review the vehicle data and underlying assumptions using the provided [Google Sheet]({SHEET_URL}). Once you've verified and updated it with the latest information, let me know so I can proceed with the next steps. Thanks!"
                            st.markdown(ai_response)
                            # st.session_state.awaiting_confirmation = True
                            st.session_state.messages.append({"role": "assistant", "content": ai_response})

                elif intent_response == "greeting":
                    ai_response, usage = openai_client.chat_completion(GREETING_PROMPT, st.session_state.messages)
                    log_openai_cost(usage, logger)
                    st.markdown(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                elif intent_response == "negative_feedback":
                    ai_response, usage = openai_client.chat_completion(NEGATIVE_FEEDBACK_PROMPT, st.session_state.messages)
                    log_openai_cost(usage, logger)
                    st.markdown(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                elif intent_response == "irrelevant":
                    ai_response, usage = openai_client.chat_completion(IRREVELANT_PROMPT, st.session_state.messages)
                    log_openai_cost(usage, logger)
                    st.markdown(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                else:
                    ai_response = "I'm not sure how to assist with that. Please ask about battery swap stations or related services."
                    st.markdown(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})





