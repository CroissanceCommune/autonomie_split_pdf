local installation
------------------

pip install -r requirements.txt

User constraint
---------------

Use with files named .../path/.../[salaires|tresorerie]_YYYY_MM.pdf

Examples
--------

A full run::

    ./tweak.py playground/salaires_2013_07.pdf -r 5

Test that the file is parseable on the 5 first pages::

    ./tweak.py playground/salaires_2013_07.pdf -r 5

Use `-v` for debug messages.

Use `-h` to get a complete overview of options.

Logging
--------

That program is smart enough to use syslog if you ask for it.

Example config
--------------

There is an example yaml config in the git repo. Use `./tweak -c config.yaml`, for
instance.

How to debug
--------------

When the expected data is not found, tweak dumps the current XML page in a file
so you can read it. A good (quite sufficient) XML reader is iceweasel.

Known problems
--------------

* cannot handle some PDF files, especially if there is no outline and the
  charset is 'binary'.
  Check this with::

    file -i $filename.pdf
