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

"""hubiC interaction using the SWIFT API"""

import functools
import hashlib
import os
import os.path

import swiftclient.client
from swiftclient.exceptions import ClientException


def md5sum(filename):
    """Compute the MD5 checksum of a file"""
    md5 = hashlib.md5()
    with open(filename, "rb") as src:
        for chunk in iter(functools.partial(src.read, 65536), ""):
            md5.update(chunk)
    return md5.hexdigest()


class ProgressFile(file):
    """File wrapper that writes read/write progress to the remote"""
    def __init__(self, remote, *args, **kwds):
        self._remote = remote
        super(ProgressFile, self).__init__(*args, **kwds)

    def read(self, *args, **kwds):
        self._remote.send("PROGRESS %d" % self.tell())
        return super(ProgressFile, self).read(*args, **kwds)

    def write(self, *args, **kwds):
        ret = super(ProgressFile, self).write(*args, **kwds)
        self._remote.send("PROGRESS %d" % self.tell())
        return ret


class SwiftConnection(object):
    """Swift connection to hubiC"""
    cache = {
        "container": None,
        "path": None,
        "conn": None,
        "last_creds": None,
    }

    def __init__(self, remote):
        self.remote = remote

        # Reuse everything as much as possible. Mostly interesting for the
        # connection object, to avoid re-opening HTTP connections and use
        # pipelining instead.
        self.container = SwiftConnection.cache["container"]
        self.path = SwiftConnection.cache["path"]
        self.conn = SwiftConnection.cache["conn"]
        last_creds = SwiftConnection.cache["last_creds"]

        if self.container is None:
            self.container = remote.get_config("hubic_container")
            if self.container is None:
                self.container = "default"

        if self.path is None:
            self.path = remote.get_config("hubic_path")
            if self.path is None:
                self.path = ""

        creds = remote.get_swift_credentials()
        if last_creds != creds:
            endpoint, token = creds
            options = {
                "auth_token": token,
                "object_storage_url": endpoint,
            }
            remote.debug("Swift credentials: " + str(options))
            self.conn = swiftclient.client.Connection(os_options=options, auth_version=2)

        # Store new things in the cache
        SwiftConnection.cache = {
            "container": self.container,
            "path": self.path,
            "conn": self.conn,
            "last_creds": creds,
        }

    def get_path(self, key):
        """Get the full path for storing a key"""
        # Only use dirhash in the "default" container
        if self.container == "default":
            dirhash = self.remote.dirhash(key)
            return os.path.join(self.path, dirhash, key)
        else:
            return os.path.join(self.path, key)

    def ensure_directory_exists(self, path):
        """Makes sure the directory exists, by creating it if necessary"""
        self.remote.debug("ensure directory exists '%s'" % path)

        # If the container is "default", we need to create application/directory
        # objects so that directories are visible in the web UI. But in
        # non-default containers, we don't care about that: we only need to make
        # sure that the container itself exists.
        if self.container != "default":
            self.conn.put_container(self.container)
            return

        # In the "default" container, check for directories and subdirectories,
        # and create them if needed.
        path_components = path.split("/")
        for idx in range(len(path_components)):
            path = "/".join(path_components[:idx])

            try:
                status = self.conn.head_object(self.container, "path")
                if status["content-type"] != "application/directory":
                    self.remote.fatal("Directory %s has type %s" % (path, status["content-type"]))
            except ClientException, exc:
                if exc.http_status != 404:
                    self.conn.put_object(self.container, path, None, content_type="application/directory")


    def store(self, key, filename):
        """Store filename to key"""
        md5 = md5sum(filename)
        path = self.get_path(key)
        self.ensure_directory_exists(os.path.dirname(path))

        try:
            with ProgressFile(self.remote, filename, "rb") as contents:
                self.conn.put_object(self.container, path, contents, etag=md5)
            self.remote.send("TRANSFER-SUCCESS STORE " + key)
        except KeyboardInterrupt:
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s Interrupted by user" % key)
            raise
        except Exception, exc:
            self.remote.send("TRANSFER-FAILURE STORE %s %s" % (key, str(exc)))


    def retrieve(self, key, filename):
        """Retrieve key to filename"""
        path = self.get_path(key)

        try:
            head, body = self.conn.get_object(self.container, path, resp_chunk_size=65536)
            with ProgressFile(self.remote, filename, "wb") as dst:
                for chunk in body:
                    dst.write(chunk)
                dst.flush()
        except KeyboardInterrupt:
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s Interrupted by user" % key)
            raise
        except Exception, exc:
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s %s" % (key, str(exc)))
            return

        md5 = md5sum(filename)
        if md5 != head['etag']:
            os.remove(filename)
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s Checksum mismatch" % key)
        else:
            self.remote.send("TRANSFER-SUCCESS RETRIEVE " + key)


    def check(self, key):
        """Check if key is present"""
        path = self.get_path(key)

        try:
            self.conn.head_object(self.container, path)
            self.remote.send("CHECKPRESENT-SUCCESS " + key)
        except KeyboardInterrupt:
            self.remote.send("CHECKPRESENT-UNKNOWN %s Interrupted by user" % key)
            raise
        except ClientException, exc:
            if exc.http_status == 404:
                self.remote.send("CHECKPRESENT-FAILURE " + key)
            else:
                self.remote.send("CHECKPRESENT-UNKNOWN %s %s" % (key, str(exc)))


    def remove(self, key):
        """Remove key"""
        path = self.get_path(key)

        # TODO: remove empty directories
        try:
            self.conn.delete_object(self.container, path)
            self.remote.send("REMOVE-SUCCESS " + key)
        except KeyboardInterrupt:
            self.remote.send("REMOVE-FAILURE %s Interrupted by user" % key)
            raise
        except Exception, exc:
            self.remote.send("REMOVE-FAILURE %s %s" % (key, str(exc)))
