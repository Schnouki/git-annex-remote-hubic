# Copyright (c) 2014-2016 Thomas Jost and the Contributors
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

"""git-annex special remote for hubiC"""

import errno
import sys

from . import auth
from . import swift

REMOTE_COST = 175  # Semi-expensive remote as per Config/Cost.hs

class Remote(object):
    """git-annex special remote protocol implementation"""

    def __init__(self, fin=None, fout=None):
        """Initializes the communication with git-annex"""
        if fin is None:
            fin = sys.stdin
        if fout is None:
            fout = sys.stdout

        self.fin = fin
        self.fout = fout

        self.auth = None

    def send(self, msg):
        """Send a message to git-annex"""
        def _closed():
            print("[hubic] git-annex has stopped, exiting.", file=sys.stderr)
            sys.exit(1)

        if self.fout.closed:
            _closed()

        try:
            self.fout.write("%s\n" % msg)
            self.fout.flush()
        except IOError as exc:
            if exc.errno == errno.EPIPE:
                _closed()
            else:
                raise exc

    def read(self):
        """Read a message from git-annex"""
        return self.fin.readline().strip()

    def debug(self, msg):
        """Send a debug message to git-annex"""
        self.send("DEBUG " + msg)

    def error(self, msg):
        """Signal an error to git-annex"""
        self.send("ERROR " + msg)

    def fatal(self, msg):
        """Signal an error to git-annex and exit"""
        self.error(msg)
        sys.exit(1)

    def run(self):
        """Wrapper for the command loop"""
        # Check that we're not running interactively
        if self.fin.isatty() or self.fout.isatty():
            print("Don't run this by yourself! Use git annex initremote type=external externaltype=hubic", file=sys.stderr)
            sys.exit(1)

        # Run the real loop handling keyboard interrupts
        try:
            self._run_forever()
        except KeyboardInterrupt:
            self.fatal("Interrupted by user")

    def _run_forever(self):
        """Run forever, accepting commands and running stuff"""
        # Start the communication with git-annex
        self.send("VERSION 1")

        self.auth = auth.HubicAuth(self)

        while True:
            line = self.read().split(None, 1)

            # Empty line: exit
            if len(line) == 0:
                return

            command = line[0]

            # Boring commands -- reply immediately
            if command == "GETCOST":
                self.send("COST %d" % REMOTE_COST)
            elif command == "GETAVAILABILITY":
                self.send("AVAILABILITY GLOBAL")

            # Init commands -- from auth.py
            elif command == "INITREMOTE":
                self.auth.initialize()

            elif command == "PREPARE":
                self.auth.prepare()

            # File transfer commands -- from swift.py
            elif command == "TRANSFER":
                subcommand, key, filename = line[1].split(None, 2)
                try:
                    conn = swift.SwiftConnection(self)
                except Exception as exc:
                    self.send("TRANSFER-%s FAILURE %s %s" % (subcommand, key, str(exc)))
                    continue

                if subcommand == "STORE":
                    conn.store(key, filename)
                elif subcommand == "RETRIEVE":
                    conn.retrieve(key, filename)
                else:
                    self.send("UNSUPPORTED-REQUEST")

            elif command == "CHECKPRESENT":
                conn = swift.SwiftConnection(self)
                conn.check(line[1])

            elif command == "REMOVE":
                conn = swift.SwiftConnection(self)
                conn.remove(line[1])

            # Fallback: unsupported command
            else:
                self.send("UNSUPPORTED-REQUEST")

    # Commands
    def get_config(self, name):
        """Read a configuration value"""
        self.send("GETCONFIG " + name)
        msg = self.read().split(None, 1)
        if msg[0] != "VALUE":
            self.fatal("Expected VALUE, got " + msg[0])
        if len(msg) == 1:
            return None
        else:
            return msg[1]

    def set_config(self, name, value):
        """Set a configuration value"""
        self.send("SETCONFIG %s %s" % (name, value))

    def get_credentials(self, name):
        """Read user credentials"""
        self.send("GETCREDS " + name)
        msg = self.read().split(None, 2)
        if msg[0] != "CREDS":
            self.fatal("Expected CREDS, got " + msg[0])
        if len(msg) < 3:
            return None, None
        else:
            return msg[1], msg[2]

    def set_credentials(self, name, user, password):
        """Set user credentials"""
        self.send("SETCREDS %s %s %s" % (name, user, password))

    def dirhash(self, key):
        """Get a two level hash associated with key."""
        self.send("DIRHASH " + key)
        msg = self.read().split(None, 1)
        if len(msg) != 2:
            self.fatal("Unexpected reply format for DIRHASH")
        if msg[0] != "VALUE":
            self.fatal("Expected VALUE, got " + msg[0])
        return msg[1]

    # Helpers and wrappers
    def get_swift_credentials(self):
        """Get SWIFT credientials using the auth module"""
        return self.auth.get_swift_credentials()

    def swift_token_expired(self):
        """Check if the SWIFT credentials have expired using the auth module"""
        return self.auth.swift_token_expired()
