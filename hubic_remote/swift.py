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
import io
import os
import os.path

import swiftclient.client
from swiftclient.exceptions import ClientException

DEFAULT_CHUNK_SIZE = 2**30  # 1 GB

class ProgressFile(io.FileIO):
    """File wrapper that writes read/write progress to the remote"""
    def __init__(self, remote, *args, **kwds):
        self._remote = remote
        super().__init__(*args, **kwds)

    def read(self, *args, **kwds):
        self._remote.send("PROGRESS %d" % self.tell())
        return super().read(*args, **kwds)

    def write(self, *args, **kwds):
        ret = super().write(*args, **kwds)
        self._remote.send("PROGRESS %d" % self.tell())
        return ret

class ChunkedReader(object):
    """File wrapper that can only read file chunks"""
    def __init__(self, file_, offset, size):
        self._file = file_
        self._offset = offset
        self._size = size

    def tell(self):
        return self._file.tell() - self._offset

    def seek(self, offset, whence):
        if whence == 0:
            self._file.seek(offset + self._offset)

    def read(self, size=None):
        pos = self._file.tell()
        max_pos = self._offset + self._size
        if size is None or pos + size >= max_pos:
            size = max_pos - pos
        if size <= 0:
            return ""
        return self._file.read(size)

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

        if self.container is None:
            self.container = remote.get_config("hubic_container")
            if self.container is None:
                self.container = "default"

        if self.path is None:
            self.path = remote.get_config("hubic_path")
            if self.path is None:
                self.path = ""

        self.chunk_size = remote.get_config("hubic_chunk_size")
        if self.chunk_size is None:
            self.chunk_size = DEFAULT_CHUNK_SIZE
        else:
            self.chunk_size = int(self.chunk_size)

        self.renew_connection()

    def renew_connection(self):
        """Start a new Swift connection, renewing credentials if necessary"""
        last_creds = SwiftConnection.cache["last_creds"]
        creds = self.remote.get_swift_credentials()
        if last_creds != creds:
            endpoint, token = creds
            options = {
                "auth_token": token,
                "object_storage_url": endpoint,
            }
            self.remote.debug("Swift credentials: " + str(options))
            self.remote.debug('export OS_AUTH_TOKEN="%(auth_token)s"; '
                              'export OS_STORAGE_URL="%(object_storage_url)s"' % options)

            dump_filename = os.getenv("GIT_ANNEX_HUBIC_AUTH_FILE")
            if dump_filename is not None:
                with open(dump_filename, "w") as dump:
                    dump.write('export OS_AUTH_TOKEN="%(auth_token)s"\n'
                               'export OS_STORAGE_URL="%(object_storage_url)s"\n' % options)

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
            except ClientException as exc:
                if exc.http_status != 404:
                    self.conn.put_object(self.container, path, None, content_type="application/directory")


    def store(self, key, filename):
        """Store filename to key"""
        # Prepare chunks
        size = os.path.getsize(filename)
        chunks = []
        while size > len(chunks) * self.chunk_size:
            new_chunk = {
                "md5": hashlib.md5(),
                "offset": len(chunks) * self.chunk_size,
                "size": min(self.chunk_size, size - len(chunks) * self.chunk_size)
            }
            chunks.append(new_chunk)

        # Compute MD5 checksums: the global one (for ETag) and one for each chunk
        md5 = hashlib.md5()
        with open(filename, "rb") as src:
            for chunk in chunks:
                reader = ChunkedReader(src, chunk["offset"], chunk["size"])
                for data_chunk in iter(functools.partial(reader.read, 65536), ""):
                    md5.update(data_chunk)
                    chunk["md5"].update(data_chunk)
                chunk["md5_digest"] = chunk["md5"].hexdigest()
        md5_digest = md5.hexdigest()

        path = self.get_path(key)
        self.ensure_directory_exists(os.path.dirname(path))

        try:
            with ProgressFile(self.remote, filename, "rb") as contents:
                for idx, chunk in enumerate(chunks):
                    this_path = path if idx == 0 else "%s/chunk%04d" % (path, idx)

                    # Chunk metadata
                    headers = {
                        "x-object-meta-annex-chunks": str(len(chunks)),
                        "x-object-meta-annex-global-md5": md5_digest,
                    }
                    if idx < len(chunks) - 1:
                        headers["x-object-meta-annex-next-chunk"] = "%s/chunk%04d" % (path, idx + 1)

                    # Try 3 times, in case of expiring OpenStack tokens
                    for nb_try in range(3):
                        self.remote.debug("Sending chunk %d/%d, try %d"
                                          % (idx + 1, len(chunks), nb_try + 1))
                        contents.seek(chunk["offset"])
                        try:
                            self.conn.put_object(self.container, this_path,
                                                 contents=contents, content_length=chunk["size"],
                                                 etag=chunk["md5_digest"], headers=headers)
                        except ClientException as exc:
                            if exc.http_status == 401 and self.remote.swift_token_expired():
                                # Retry!
                                self.renew_connection()
                                continue
                            else:
                                raise exc

                        # Chunk upload successful: break the retry loop
                        break

            self.remote.send("TRANSFER-SUCCESS STORE " + key)

        except KeyboardInterrupt:
            self.remote.send("TRANSFER-FAILURE STORE %s Interrupted by user" % key)
            raise
        except Exception as exc:
            self.remote.send("TRANSFER-FAILURE STORE %s %s" % (key, str(exc)))


    def retrieve(self, key, filename):
        """Retrieve key to filename"""
        md5 = hashlib.md5()
        path = self.get_path(key)

        nb_chunks = None
        chunk_idx = 0
        global_etag = None

        try:
            with ProgressFile(self.remote, filename, "wb") as dst:
                while path is not None:
                    chunk_idx += 1
                    self.remote.debug("Getting chunk %d" % chunk_idx)

                    headers, body = self.conn.get_object(self.container, path, resp_chunk_size=65536)

                    # Read chunk metadata
                    meta_nb_chunks = int(headers.get("x-object-meta-annex-chunks", 1))
                    meta_global_etag = headers.get("x-object-meta-annex-global-md5", headers["etag"])

                    # Check for consistency
                    if nb_chunks is None:
                        nb_chunks = meta_nb_chunks
                    elif nb_chunks != meta_nb_chunks:
                        raise ValueError("Inconsistent number of chunks: %d != %d (%d)"
                                         % (nb_chunks, meta_nb_chunks, chunk_idx))
                    if global_etag is None:
                        global_etag = meta_global_etag
                    elif global_etag != meta_global_etag:
                        raise ValueError("Inconsistent global MD5 checksum: %s != %s (%d)"
                                         % (global_etag, meta_global_etag, chunk_idx))

                    # Path of the next chunk
                    path = headers.get("x-object-meta-annex-next-chunk", None)

                    # Write chunk to file
                    chunk_md5 = hashlib.md5()
                    for chunk in body:
                        dst.write(chunk)
                        md5.update(chunk)
                        chunk_md5.update(chunk)
                    dst.flush()

                    # Check chunk MD5
                    chunk_md5_digest = chunk_md5.hexdigest()
                    if chunk_md5_digest != headers["etag"]:
                        raise ValueError("Checksum mismatch for chunk %d: %s != %s"
                                         % (chunk_idx, chunk_md5_digest, headers["etag"]))

        except KeyboardInterrupt:
            os.remove(filename)
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s Interrupted by user" % key)
            raise
        except Exception as exc:
            os.remove(filename)
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s %s" % (key, str(exc)))
            return

        md5_digest = md5.hexdigest()
        if md5_digest != global_etag:
            os.remove(filename)
            self.remote.send("TRANSFER-FAILURE RETRIEVE %s Checksum mismatch" % key)
        else:
            self.remote.send("TRANSFER-SUCCESS RETRIEVE " + key)


    def check(self, key):
        """Check if key is present"""
        path = self.get_path(key)
        nb_chunks = None
        chunk_idx = 0

        try:
            while path is not None:
                chunk_idx += 1
                self.remote.debug("Checking chunk %d" % chunk_idx)
                headers = self.conn.head_object(self.container, path)

                # Check chunk metadata
                meta_nb_chunks = int(headers.get("x-object-meta-annex-chunks", 1))
                if nb_chunks is None:
                    nb_chunks = meta_nb_chunks
                elif nb_chunks != meta_nb_chunks:
                    raise ValueError("Inconsistent number of chunks: %d != %d (%d)"
                                     % (nb_chunks, meta_nb_chunks, chunk_idx))

                # Path of the next chunk
                path = headers.get("x-object-meta-annex-next-chunk", None)

            if chunk_idx == nb_chunks:
                self.remote.send("CHECKPRESENT-SUCCESS " + key)
            else:
                self.remote.send("CHECKPRESENT-FAILURE %s Found %d chunks instead of %d"
                                 % (key, chunk_idx, nb_chunks))
        except KeyboardInterrupt:
            self.remote.send("CHECKPRESENT-UNKNOWN %s Interrupted by user" % key)
            raise
        except ClientException as exc:
            if exc.http_status == 404:
                self.remote.send("CHECKPRESENT-FAILURE " + key)
            else:
                self.remote.send("CHECKPRESENT-UNKNOWN %s %s" % (key, str(exc)))


    def remove(self, key):
        """Remove key"""
        path = self.get_path(key)
        chunks = []

        # TODO: remove empty directories
        try:
            # List existing chunks
            while path is not None:
                self.remote.debug("Checking chunk %d" % (1 + len(chunks)))
                try:
                    headers = self.conn.head_object(self.container, path)
                except ClientException as exc:
                    if exc.http_status == 404:
                        break
                    else:
                        raise exc
                chunks.append(path)
                path = headers.get("x-object-meta-annex-next-chunk", None)

            # Remove chunks. Do it in reverse order so that we can try again if
            # this is interrupted.
            for idx, chunk in enumerate(reversed(chunks)):
                self.remote.debug("Removing chunk %d" % (len(chunks) - idx))
                try:
                    self.conn.delete_object(self.container, chunk)
                except ClientException as exc:
                    if exc.http_status == 404:
                        continue
                    else:
                        raise exc

            self.remote.send("REMOVE-SUCCESS " + key)
        except KeyboardInterrupt:
            self.remote.send("REMOVE-FAILURE %s Interrupted by user" % key)
            raise
        except Exception as exc:
            self.remote.send("REMOVE-FAILURE %s %s" % (key, str(exc)))
