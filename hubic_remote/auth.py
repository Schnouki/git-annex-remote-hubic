# Copyright (c) 2014 Thomas Jost
#
# This file is part of git-annex-remote-hubic.
#
# git-annex-remote-hubic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# git-annex-remote-hubic is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# git-annex-remote-hubic. If not, see <http://www.gnu.org/licenses/>.

"""hubiC authentication module"""

import BaseHTTPServer
import datetime
import os
import sys
import urlparse
import webbrowser

import dateutil.parser
import dateutil.tz
import rauth

REDIRECT_PORT = 18181
REDIRECT_URI = "http://localhost:%d/" % REDIRECT_PORT

DATETIME_MIN = datetime.datetime(2000, 1, 1, tzinfo=dateutil.tz.tzlocal())

def now():
    """Timezone-aware version of datetime.datetime.now"""
    return datetime.datetime.now(dateutil.tz.tzlocal())


class HubicAuth(object):
    """Handle authentication using the hubiC API"""

    access_token_url = "https://api.hubic.com/oauth/token"
    authorize_url = "https://api.hubic.com/oauth/auth"
    base_url = "https://api.hubic.com/1.0/"

    def __init__(self, remote):
        self.remote = remote

        self.oauth_client_id = self.oauth_client_secret = None
        self.service = None

        self.refresh_token = self.access_token = None
        self.access_token_expiration = DATETIME_MIN

        self.swift_token = self.swift_endpoint = None
        self.swift_token_expiration = DATETIME_MIN


    def get_service(self):
        """Initialize the OAuth2 service"""
        if self.service is not None:
            return self.service
        self.remote.debug("Initializing the OAuth service")

        # Try to get client IDs from the config
        self.oauth_client_id, self.oauth_client_secret = self.remote.get_credentials("oauth_client")

        # If this is the initial login, get them from the environment instead
        if self.oauth_client_id is None or self.oauth_client_secret is None:
            self.remote.debug("Reading OAuth credentials from the environment")
            self.oauth_client_id = os.environ.get("HUBIC_CLIENT_ID", None)
            self.oauth_client_secret = os.environ.get("HUBIC_CLIENT_SECRET", None)
            if self.oauth_client_id is None or self.oauth_client_secret is None:
                self.remote.fatal("Could not read the HUBIC_CLIENT_ID and HUBIC_CLIENT_SECRET environment variables")

            self.remote.set_credentials("oauth_client", self.oauth_client_id, self.oauth_client_secret)

        # Create the OAuth service
        self.service = rauth.OAuth2Service(
            name="git-annex-remote",
            client_id=self.oauth_client_id,
            client_secret=self.oauth_client_secret,
            access_token_url=self.access_token_url,
            authorize_url=self.authorize_url,
            base_url=self.base_url
        )
        return self.service


    def initialize(self):
        """Perform a first-time OAuth2 authentication"""
        self.remote.debug("Starting first-time OAuth2 authentication")
        service = self.get_service()

        # Is this enableremote or initremote? If enableremote, we already have our credentials...
        _, self.refresh_token = self.remote.get_credentials("token")
        if self.refresh_token is not None:
            self.refresh_access_token()
            self.remote.send("INITREMOTE-SUCCESS")
            return

        # First step: open the authorization URL in a browser
        url = service.get_authorize_url(redirect_uri=REDIRECT_URI, response_type="code", scope="account.r,credentials.r")
        print >>sys.stderr, "\nAn authentication tab should open in your browser. If it does not,"
        print >>sys.stderr, "please go to the following URL:"
        print >>sys.stderr, url
        webbrowser.open_new_tab(url)

        # Start a simple webserver that will handle the redirect and extract the
        # request code
        self.remote.debug("Starting the HTTP server to handle the redirection URL")
        httpd = RedirectServer(("127.0.0.1", REDIRECT_PORT), RedirectHandler)
        httpd.handle_request()
        if "code" not in httpd.query:
            self.remote.fatal("Something went wrong during the authentication: the request code is missing.")

        request_code = httpd.query['code']

        # Now get an access token and a refresh token
        data = {
            "code": request_code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        tokens = service.get_raw_access_token(data=data).json()
        self.refresh_token = tokens["refresh_token"]
        self.access_token = tokens["access_token"]
        self.access_token_expiration = now() + datetime.timedelta(seconds=tokens["expires_in"])
        self.remote.debug("The current OAuth access token expires in %d seconds" % tokens["expires_in"])

        # Finally get some informations about the account, just for fun
        sess = self.get_session()
        data = sess.get("account").json()
        email = data['email']

        # Store the credentials safely
        self.remote.set_credentials("token", email, self.refresh_token)

        # And tell that we're done
        self.remote.send("INITREMOTE-SUCCESS")


    def prepare(self):
        """Prepare for OAuth2 access"""
        self.remote.debug("Preparing the remote")
        _, self.refresh_token = self.remote.get_credentials("token")
        if self.refresh_token is None:
            self.remote.send("PREPARE-FAILURE No credentials found")

        self.refresh_swift_token()
        self.remote.send("PREPARE-SUCCESS")


    def get_session(self):
        """Get an authenticated OAuth2 session"""
        if self.access_token_expiration <= now():
            self.refresh_access_token()
        service = self.get_service()
        return service.get_session(token=self.access_token)


    def refresh_access_token(self):
        """Refresh the OAuth2 access token"""
        data = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        service = self.get_service()
        self.remote.debug("Refreshing the OAuth access token")
        tokens = service.get_raw_access_token(data=data).json()
        self.access_token = tokens["access_token"]
        self.access_token_expiration = now() + datetime.timedelta(seconds=tokens["expires_in"])
        self.remote.debug("The current OAuth access token expires in %d seconds" % tokens["expires_in"])


    def refresh_swift_token(self):
        """Refresh the OpenStack access token"""
        self.remote.debug("Refreshing the OpenStack access token")
        sess = self.get_session()
        swift_creds = sess.get("account/credentials").json()
        self.swift_token = swift_creds['token']
        self.swift_endpoint = swift_creds['endpoint']
        self.swift_token_expiration = dateutil.parser.parse(swift_creds['expires'])
        delta = self.swift_token_expiration - now()
        self.remote.debug("The current OpenStack access token expires in %d seconds" % delta.total_seconds())


    def get_swift_credentials(self):
        """Get a valid OpenStack endpoint and access token"""
        if self.swift_token_expiration <= now():
            self.refresh_swift_token()
        return (self.swift_endpoint, self.swift_token)


class RedirectServer(BaseHTTPServer.HTTPServer):
    """A basic HTTP server that handles a single request to the OAuth redirection URL"""
    query = {}

class RedirectHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """A basic HTTP request handler that extracts relevant information from the OAuth redirection URL"""

    def do_GET(request):
        """Extract query string parameters from a URL and return a generic response"""
        query = request.path.split('?', 1)[-1]
        query = dict(urlparse.parse_qsl(query))
        request.server.query = query

        request.send_response(200)
        request.send_header("Content-Type", "text/html")
        request.end_headers()
        request.wfile.write("""<html>
            <head><title>git-annex-remote-hubic authentication</title></head>
            <body><p>Authentication completed, you can now close this window.</p></body>
            </html>""")

    def log_message(self, *args, **kwargs):
        """No-op log message handler"""
        pass
