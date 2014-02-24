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

"""Migrate hubiC data out of the default container"""

import argparse
import os.path
import sys

import swiftclient.client

import auth


class PseudoRemote(object):
    """Object that mimics a normal Remote"""

    def debug(self, msg):
        print >>sys.stderr, msg

    def fatal(self, msg):
        print >>sys.stderr, msg
        sys.exit(1)

    def get_config(self, *args):
        return None
    def get_credentials(self, *args):
        return None, None

    def send(self, *args): pass
    def set_config(self, *args): pass
    def set_credentials(self, *args): pass


def main():
    """Move hubiC data out of the default container"""
    parser = argparse.ArgumentParser(
        description="Migrate annexed data out of the default hubiC container")
    parser.add_argument("source_path",
                        help="directory to copy/move out of the default container")
    parser.add_argument("target_container", help="target container")
    parser.add_argument("target_path",
                        help="directory where the data will be copied/moved")
    parser.add_argument("--move", action="store_true",
                        help="move data instead of copying them")
    parser.add_argument("--token", type=str,
                        help="OAuth2 refresh token used to log into the hubiC account")
    args = parser.parse_args()

    # Authenticate
    remote = PseudoRemote()
    hubic_auth = auth.HubicAuth(remote)
    hubic_auth.refresh_token = args.token
    hubic_auth.initialize()
    print "OAuth2 credentials: token=%s" % hubic_auth.refresh_token

    # Init Swift connection
    endpoint, token = hubic_auth.get_swift_credentials()
    options = {
        "auth_token": token,
        "object_storage_url": endpoint,
    }
    print "Swift credentials: token=%s, endpoint=%s" % (token, endpoint)
    conn = swiftclient.client.Connection(os_options=options, auth_version=2)

    # List objects in the source directory
    _, objects = conn.get_container("default", prefix=args.source_path,
                                    full_listing=True)

    # Remove directories
    files = [(obj["name"], obj["hash"]) for obj in objects
             if obj["content_type"] != "application/directory"]
    print "Processing %d files..." % len(files)

    # Create the target container
    conn.put_container(args.target_container)

    # List objects in the target directory
    _, objects = conn.get_container(args.target_container, prefix=args.target_path,
                                    full_listing=True)
    target_files = {obj["name"]: obj["hash"] for obj in objects
                    if obj["content_type"] != "application/directory"}

    # Start copying files
    for idx, (name, etag) in enumerate(files):
        source_path = "/" + os.path.join("default", name)
        target_path = os.path.join(args.target_path, os.path.basename(name))

        # First check for the target
        if target_path not in target_files or target_files[target_path] != etag:
            nice_target_path = "/" + args.target_container + "/" + target_path
            print (idx+1), source_path, "-->", nice_target_path
            conn.put_object(args.target_container, target_path, contents=None,
                            headers={"X-Copy-From": source_path,
                                     "Content-Length": 0})

        if args.move:
            print (idx+1), "deleting", source_path
            conn.delete_object("default", name)


if __name__ == "__main__":
    main()
