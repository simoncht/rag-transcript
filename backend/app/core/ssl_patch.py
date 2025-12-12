"""
SSL certificate bypass for corporate environments.

This module MUST be imported before any other modules that use HTTPS.
It monkey-patches the requests library to disable SSL verification globally.
"""
import ssl
import os
import warnings
import urllib3

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Disable SSL verification at the SSL module level
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Set environment variables
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['PYTHONWARNINGS'] = 'ignore:Unverified HTTPS request'

# Monkey-patch requests library to disable SSL verification
try:
    import requests
    from functools import wraps

    # Store the original request method
    _original_request = requests.Session.request

    @wraps(_original_request)
    def _patched_request(self, method, url, **kwargs):
        """Patched request method that always sets verify=False"""
        kwargs['verify'] = False
        return _original_request(self, method, url, **kwargs)

    # Apply the patch
    requests.Session.request = _patched_request

    # Also patch requests.request for convenience functions
    _original_requests_request = requests.request

    @wraps(_original_requests_request)
    def _patched_requests_request(method, url, **kwargs):
        """Patched requests.request that always sets verify=False"""
        kwargs['verify'] = False
        return _original_requests_request(method, url, **kwargs)

    requests.request = _patched_requests_request

    # Patch huggingface_hub's session creation
    try:
        import huggingface_hub
        from huggingface_hub import constants

        # Monkey-patch the get_session function
        _original_get_session = huggingface_hub.utils._http.get_session

        def _patched_get_session():
            session = _original_get_session()
            session.verify = False
            return session

        huggingface_hub.utils._http.get_session = _patched_get_session

        # Also patch constants
        constants.HF_HUB_DISABLE_SSL_VERIFY = True

    except Exception as hf_error:
        print(f"WARNING: Could not patch huggingface_hub: {hf_error}")

    print("SSL verification disabled for corporate environment")

except Exception as e:
    print(f"WARNING: Could not patch requests SSL verification: {e}")
