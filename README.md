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
- Written in Python 2 (only tested with 2.7, may work with 2.6)
- Uses the reputable
  [python-swiftclient](https://github.com/openstack/python-swiftclient) package
  to communicate with hubiC servers (official Python bindings from the OpenStack
  project)
- Uses the new git-annex
  [special remote protocol](https://git-annex.branchable.com/design/external_special_remote_protocol/)
- Tested on Linux (x86_64 and armel)


Installation
------------

1.  Install Python2 and setuptools (on Arch Linux: `pacman -S python2-setuptools`;
    on Debian/Ubuntu: `apt-get install python-setuptools`).

2.  Clone this repository:

        git clone git://github.com/Schnouki/git-annex-remote-hubic.git

3.  Install the package:

        python2 setup.py install --user
        # Use python on outdated distros such as Debian or Ubuntu

4.  Go to a repository you manage with git-annex, and initialize your new remote
    using the following commands as a starting point:

        git annex initremote my-hubic-remote type=external externaltype=hubic encryption=shared hubic_path=annex/dirname

    where `my-hubic-remote` is the name of your remote, and `hubic_path` is the
    directory in your hubiC account where your annexed data will be stored.
    Adjust the value of the `encryption` variable as you like.

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
