hubiC remote for git-annex
==========================

Manage your data with git-annex, store them in your [hubiC](https://hubic.com/)
account.

**Warning:** this project is very recent and quite experimental. It may cause
  data loss. It may hurt your children and your cats. It might cause a nuclear
  explosion nearby. Don't trust it.


Features
--------

- Lets you store and retrieve data managed with git-annex to your hubiC account
- Authentication is done using OAuth 2.0: no need for your hubiC password!
- Data integrity is checked using client-side and server-side MD5 checksums of
  your files
- Written in Python 3 (only tested with 3.4, should work with 3.3, may work with 3.2)
- Uses the reputable
  [python-swiftclient](https://github.com/openstack/python-swiftclient) package
  to communicate with hubiC servers (official Python bindings from the OpenStack
  project)
- Uses the new git-annex
  [special remote protocol](https://git-annex.branchable.com/design/external_special_remote_protocol/)
- Tested on Linux (x86_64 and armel)


Installation
------------

1.  Install Python3 and setuptools ≥ 0.7 (on Arch Linux: `pacman -S
    python-setuptools`; on Debian/Ubuntu: `apt-get install python3-setuptools`).
    If setuptools ≥ 0.7 is not available, you can install distribute instead; if
    distribute isn't available either, you should try to install setuptools in
    your `$HOME` with `pip3 install --user --upgrade setuptools`.

2.  Clone this repository:

        git clone git://github.com/Schnouki/git-annex-remote-hubic.git

3.  Install the package:

        python3 setup.py install --user

4.  Go to a repository you manage with git-annex, and initialize your new remote
    using the following commands as a starting point:

        git annex initremote my-hubic-remote type=external externaltype=hubic encryption=shared hubic_container=annex hubic_path=path/to/data embedcreds=no

    - `my-hubic-remote` is the name of your remote
    - `hubic_container` is the name of the Swift container used to store your
      data. If you don't specify anything, the name "`default`" will be used,
      which is the name of the container used by the hubiC desktop client and
      shown in the web interface. Therefore it is *not* recommended to use the
      "`default`" container to store your annexed data, as they will be synced
      to your computer if you use the desktop client.
    - `hubic_path` is the directory where your annexed data will be stored in
       the container your chose.
    - `embedcreds` controls whether your access token shall be stored in the git
      repository. If set to `yes`, anyone with access to your repository can get
      full access to all your hubiC data, so don't set it to `yes` unless you
      really trust the machines where your repository is stored and the people
      who have access to it.
    - `encryption` is used to control whether your data will be encrypted on the
      remote, just like with
      [any other remote](http://git-annex.branchable.com/encryption/).

You can now use your new remote just like any other git-annex remote.

If you use `git annex enableremote` on a clone of your repository, you'll be
asked to login again. If this clone happens to be on a browser-less computer
(VPS, server, NAS...), this won't work. However you can just copy your
credentials file to that repository: it should be named
`.git/annex/creds/$UUID-token` where `$UUID` is the UUID of your hubiC remote
(you can get that with `git annex info`).

Enjoy, and in case of trouble don't hesitate to
[file an issue](https://github.com/Schnouki/git-annex-remote-hubic/issues) or to
[send me an e-mail](mailto:schnouki+garh@schnouki.net).


Upgrade
-------

The very first version of this remote, when published to GitHub, only supported
storing data in the default container. However doing so is **not recommended**
as data stored in that container will be synced to your computer if you use the
desktop client.

So if you started using this remote before the `hubic_container` option was
available, I strongly encourage you to migrate your data out of your default
container. To do so, you can use the `git-annex-remote-hubic-migrate` script
provided with this package:

    git-annex-remote-hubic-migrate old_path/to/data new_container_name new/path/to/data

This will do server-side copies from "`default`" to "`new_container_name`",
without needing to re-upload everything. Once the copy is complete, you should change your remote config:

    git annex enableremote my-hubic-remote hubic_container=new_container_name hubic_path=new/path/to/data

You can then run `git annex fsck -F my-remote-hubic` to check that all your data
are still there. Once it succeeds, you may delete the old data by hand (for
example from the webclient), or by running the same script again with the
`--move` option:

    git-annex-remote-hubic-migrate --move old_path/to/data new_container_name new/path/to/data


Hacking
-------

If you want to hack on this remote, feel free :)

- Use `git annex --debug`. It saves lifes.
- There are a few tests in the `test` directory; they only cover common use
  cases.
- If you wish to use the `swift` command to access your hubiC account, you can
  have the remote dump the needed credentials to a file using an environment
  variable:

        export GIT_ANNEX_HUBIC_AUTH_FILE=/path/to/auth/file
        source /path/to/auth/file
        swift list


License
-------

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
