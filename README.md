hubiC remote for git-annex
==========================

This lets you store your data managed with git-annex to [hubiC](https://hubic.com/).

**Warning:** this project is very recent. It may cause data loss. It may hurt
  your children and your cats. It might text your ex. Don't trust it.


Installation
------------

1.  Install Python2 and setuptools (on Arch Linux: `pacman -S python2-setuptools`;
    on Debian/Ubuntu: `apt-get install python-setuptools`).

2.  Clone this repository:

        git clone git://github.com/Schnouki/git-annex-remote-hubic.git

3.  Install the package:

        python2 setup.py --user install
        # Use python on outdated distros such as Debian or Ubuntu

4.  Go to a repository you manage with git-annex, and initialize your new remote
    using the following commands as a starting point:

        git annex initremote my-hubic-remote type=external externaltype=hubic encryption=shared hubic_path=annex/dirname

    where `my-hubic-remote` is the name of your remote, and `hubic_path` is the
    directory in your hubiC account where your annexed data will be stored.
    Adjust the value of the `encryption` variable as you like.

You can now use your new remote just like any other git-annex remote.

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
