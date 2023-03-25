import json
import time
from threading import Thread

from django.conf import settings
from django.urls import resolve
from django.utils import timezone

from logs import API_LOGGER_SIGNAL
from logs.start_logger_when_server_starts import LOGGER_THREAD
from logs.utils import get_headers, get_client_ip, mask_sensitive_data

"""
File: api_logger_middleware.py
Class: APILoggerMiddleware
"""


class APILoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

        self.DRF_API_LOGGER_DATABASE = False
        if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
            self.DRF_API_LOGGER_DATABASE = settings.DRF_API_LOGGER_DATABASE

        self.DRF_API_LOGGER_SIGNAL = False
        if hasattr(settings, 'DRF_API_LOGGER_SIGNAL'):
            self.DRF_API_LOGGER_SIGNAL = settings.DRF_API_LOGGER_SIGNAL

        self.DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'
        if hasattr(settings, 'DRF_API_LOGGER_PATH_TYPE'):
            if settings.DRF_API_LOGGER_PATH_TYPE in ['ABSOLUTE', 'RAW_URI', 'FULL_PATH']:
                self.DRF_API_LOGGER_PATH_TYPE = settings.DRF_API_LOGGER_PATH_TYPE

        self.DRF_API_LOGGER_SKIP_URL_NAME = []
        if hasattr(settings, 'DRF_API_LOGGER_SKIP_URL_NAME'):
            if type(settings.DRF_API_LOGGER_SKIP_URL_NAME) is tuple or type(
                    settings.DRF_API_LOGGER_SKIP_URL_NAME) is list:
                self.DRF_API_LOGGER_SKIP_URL_NAME = settings.DRF_API_LOGGER_SKIP_URL_NAME

        self.DRF_API_LOGGER_SKIP_NAMESPACE = []
        if hasattr(settings, 'DRF_API_LOGGER_SKIP_NAMESPACE'):
            if type(settings.DRF_API_LOGGER_SKIP_NAMESPACE) is tuple or type(
                    settings.DRF_API_LOGGER_SKIP_NAMESPACE) is list:
                self.DRF_API_LOGGER_SKIP_NAMESPACE = settings.DRF_API_LOGGER_SKIP_NAMESPACE

        self.DRF_API_LOGGER_METHODS = []
        if hasattr(settings, 'DRF_API_LOGGER_METHODS'):
            if type(settings.DRF_API_LOGGER_METHODS) is tuple or type(
                    settings.DRF_API_LOGGER_METHODS) is list:
                self.DRF_API_LOGGER_METHODS = settings.DRF_API_LOGGER_METHODS

        self.DRF_API_LOGGER_STATUS_CODES = []
        if hasattr(settings, 'DRF_API_LOGGER_STATUS_CODES'):
            if type(settings.DRF_API_LOGGER_STATUS_CODES) is tuple or type(
                    settings.DRF_API_LOGGER_STATUS_CODES) is list:
                self.DRF_API_LOGGER_STATUS_CODES = settings.DRF_API_LOGGER_STATUS_CODES

    def __call__(self, request):

        # Run only if logger is enabled.
        if self.DRF_API_LOGGER_DATABASE or self.DRF_API_LOGGER_SIGNAL:

            url_name = resolve(request.path_info).url_name
            namespace = resolve(request.path_info).namespace

            # Always skip Admin panel
            if namespace == 'admin':
                return self.get_response(request)

            # Skip for url name
            if url_name in self.DRF_API_LOGGER_SKIP_URL_NAME:
                return self.get_response(request)

            # Skip entire app using namespace
            if namespace in self.DRF_API_LOGGER_SKIP_NAMESPACE:
                return self.get_response(request)

            start_time = time.time()
            request_data = ''
            try:
                request_data = json.loads(request.body) if request.body else ''
            except:
                pass

            # Code to be executed for each request before
            # the view (and later middleware) are called.
            response = self.get_response(request)

            # Only log required status codes if matching
            if self.DRF_API_LOGGER_STATUS_CODES and response.status_code not in self.DRF_API_LOGGER_STATUS_CODES:
                return response

            # Code to be executed for each request/response after
            # the view is called.

            headers = get_headers(request=request)
            method = request.method

            # Log only registered methods if available.
            if len(self.DRF_API_LOGGER_METHODS) > 0 and method not in self.DRF_API_LOGGER_METHODS:
                return response

            if response.get('content-type') in ('application/json', 'application/vnd.api+json', 'application/gzip'):

                if response.get('content-type') == 'application/gzip':
                    response_body = '** GZIP Archive **'
                elif getattr(response, 'streaming', False):
                    response_body = '** Streaming **'
                else:
                    if type(response.content) == bytes:
                        response_body = json.loads(response.content.decode())
                    else:
                        response_body = json.loads(response.content)
                if self.DRF_API_LOGGER_PATH_TYPE == 'ABSOLUTE':
                    api = request.build_absolute_uri()
                elif self.DRF_API_LOGGER_PATH_TYPE == 'FULL_PATH':
                    api = request.get_full_path()
                elif self.DRF_API_LOGGER_PATH_TYPE == 'RAW_URI':
                    api = request.get_raw_uri()
                else:
                    api = request.build_absolute_uri()

                if not request.user.is_authenticated and request.user.is_anonymous:
                    user = None
                else:
                    user = mask_sensitive_data(request.user)

                data = dict(
                    api=mask_sensitive_data(api, mask_api_parameters=True),
                    headers=mask_sensitive_data(headers),
                    body=mask_sensitive_data(request_data),
                    method=method,
                    client_ip_address=get_client_ip(request),
                    response=mask_sensitive_data(response_body),
                    status_code=response.status_code,
                    execution_time=time.time() - start_time,
                    added_on=timezone.now(),
                    # instance_before_change=mask_sensitive_data(request_data),
                    user=user
                )
                if self.DRF_API_LOGGER_DATABASE:
                    if LOGGER_THREAD:
                        d = data.copy()
                        d['headers'] = json.dumps(d['headers'], indent=4, ensure_ascii=False)
                        if request_data:
                            d['body'] = json.dumps(d['body'], indent=4, ensure_ascii=False)
                        d['response'] = json.dumps(d['response'], indent=4, ensure_ascii=False)
                        LOGGER_THREAD.put_log_data(data=d)
                if self.DRF_API_LOGGER_SIGNAL:
                    API_LOGGER_SIGNAL.listen(**data)
            else:
                return response
        else:
            response = self.get_response(request)
        return response
