"""
Authentication module for IndoFast AI Copilot
"""
import streamlit as st
import hashlib
import time
from config import AUTH_TOKENS

def check_authentication():
    """
    Check if user is authenticated using token-based auth
    Returns True if authenticated, False otherwise
    """
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = None
    
    return st.session_state.authenticated

def authenticate_user(token):
    """
    Authenticate user with provided token
    """
    if token in AUTH_TOKENS:
        st.session_state.authenticated = True
        st.session_state.auth_token = token
        st.session_state.auth_time = time.time()
        return True
    return False

def logout():
    """
    Logout user and clear session
    """
    st.session_state.authenticated = False
    st.session_state.auth_token = None
    if 'auth_time' in st.session_state:
        del st.session_state.auth_time

def show_login_page():
    """
    Display login page
    """
    st.markdown("""
    <div style="max-width: 500px; margin: 0 auto; padding: 2rem; 
                border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                background-color: #f8f9fa;">
        <h2 style="text-align: center; color: #1f77b4; margin-bottom: 1rem;">
            🔐 Station Planning Agent Login
        </h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### Please enter your authentication token:")
    
    with st.form("login_form"):
        token = st.text_input("Authentication Token", type="password", placeholder="Enter your token here...")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if token:
                if authenticate_user(token):
                    st.success("✅ Authentication successful! Redirecting...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid token. Please try again.")
            else:
                st.warning("⚠️ Please enter a token.")
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #6c757d; font-size: 0.9rem;">
        <p>🔒 This application requires authentication to access.</p>
        <p>Contact Sara Tuppad if you need access.</p>
    </div>
    """, unsafe_allow_html=True)

def add_logout_button():
    """
    Add logout button to sidebar
    """
    with st.sidebar:
        st.markdown("---")
        if st.button("🚪 Logout", key="logout_btn"):
            logout()
            st.rerun()
        
        # Show current user info
        # if st.session_state.get('auth_token'):
        #     token_preview = st.session_state.auth_token[:8] + "..." if len(st.session_state.auth_token) > 8 else st.session_state.auth_token
        #     st.markdown(f"👤 **Logged in as:** `{token_preview}`")
            
        #     if 'auth_time' in st.session_state:
        #         auth_duration = int(time.time() - st.session_state.auth_time)
        #         st.markdown(f"⏱️ **Session time:** {auth_duration//60}m {auth_duration%60}s")
