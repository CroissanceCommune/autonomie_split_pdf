Licence
--------

This is a free software (GPLv3), see LICENCE.txt for licencing info.

local installation
------------------

pip install -r requirements.txt

User constraint
---------------

Use with files named .../path/.../[salaires|tresorerie]_YYYY_MM.pdf

Examples
--------

A full run::

    ./tweak playground/salaires_2013_07.pdf

Test that the file is parseable on the 5 first pages::

    ./tweak playground/salaires_2013_07.pdf -r 5

Use `-v` for debug messages.

Use `-h` to get a complete overview of options.

Configuration
--------------

Main config file
  Defaults to `~/.autonomie_pdfsplit.yaml`
  Specifiable by use -c <configfile>

Format is yaml.

Example

.. code:: yaml

    {
        loglevel: 10,
        use_syslog: true,
        verbosity: DEBUG,
        log_to_mail: true,
        payroll: {
            preprocessor: ./payrollpdf2ancode.sh,
        },
        mail: {
            host: smtp.free.fr,
            from: autonomie@yourserver.tld,
            to: responsible@yourorga.tld,
            subject: '[%(hostname)s] Log of autonomie pdf splitter',
            }}


For payroll handling, an additional file is needed::

    ~/payroll_rc

This file is bash sourced and contains some info about the payroll layout.

Example:

    .. code:: shell

        ANCODE_LINE=12
        ANCODE_COL=55
        NAME_COL=90
        NAME_LINE=15
        ALTERNATE_NAME_LINE=14

Logging
--------

That program is smart enough to use syslog if the config

It logs to mail if the config contains `log_to_mail: True`


Known problems
--------------

* for payrolls
    cannot handle some PDF files, especially if there is no outline and the
    charset is 'binary'.
    Check this with::

        file -i $filename.pdf

* for situation and result
    We need an outline in the PDF file.
    This outline must follow the following hierarchy:

        * title of level 1

          * entrepreneur name

            * analytic code
            * [optional analytic code]

          * entrepreneur name

            * analytic code
            * [optional analytic code]

          * entrepreneur name

            * analytic code
            * [optional analytic code]

          ...

        * optional title level 1

Writing a payroll RC file
-------------------------

Use pdf2txt -q -layout once on the file. In the output txt file, find the line and
the column where the ANCODE is written, then set the ANCODE_LINE and ANCODE_COL
accordingly. Do the same for the NAME, with NAME_LINE, NAME_COL.
