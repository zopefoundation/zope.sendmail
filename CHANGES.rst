=========
 Changes
=========

7.0 (2025-09-12)
================

- Replace ``pkg_resources`` namespace with PEP 420 native namespace.

- Drop support for Python 3.7, 3.8.


6.2 (2024-03-21)
================

- Add implicit_tls option to the Mailer, if setted to True the SMTP connection will use smtplib.SMTP_SSL
  and starts the connection with SSL from the beginning.
  (see `RFC8314 <https://datatracker.ietf.org/doc/html/rfc8314#section-3.3>`_)

6.1 (2024-02-07)
================

- Fix SMTP protocol interoperability by avoiding hardcoded line endings.
  (see https://www.rfc-editor.org/rfc/rfc2821#section-2.3.7)

- Add preliminary support for Python 3.13 as of 3.13a3.

- Add support for Python 3.12.


6.0 (2023-08-22)
================

- Drop support for Python 2.7, 3.5, 3.6.

- Add support for Python 3.11.


5.3 (2022-10-06)
================

- Add support for Python 3.10.

- Do not try to send queued emails to an empty address
  (`#45 <https://github.com/zopefoundation/zope.sendmail/issues/45>`_).


5.2 (2021-01-18)
================

- Add minimal savepoint support, so we do not fail if any code tries to create a savepoint.
  (`#35 <https://github.com/zopefoundation/zope.sendmail/issues/35>`_).

- Fix TypeError: 'error' object is not subscriptable during error handling on
  Windows (`#33 <https://github.com/zopefoundation/zope.sendmail/pull/33>`_).

- Add support for Python 3.9.


5.1 (2020-07-31)
================

- Use ``pywin32`` again, not any longer the meanwhile outdated fork named ``pypiwin32``.
  Add some information for installation with buildout.
  (`#30 <https://github.com/zopefoundation/zope.sendmail/issues/30>`_)

- Support ``bytes`` messages; consistently convert messages
  using a "text" type (i.e. ``str`` for Python 3, ``unicode`` for Python 2)
  into ``bytes`` via utf-8 encoding.
  Prerequisite to fix
  `Products.MailHost#30
  <https://github.com/zopefoundation/Products.MailHost/issues/30>`_.



5.0 (2019-04-03)
================

- Drop support for Python 3.4.

- Add support for Python 3.8a3.

- Fix text/bytes issue in MailDir for Python 3.
  (`#24 <https://github.com/zopefoundation/zope.sendmail/pull/24>`_)


4.2.1 (2019-02-07)
==================

- Fix SMTP authentication on Python 3. See `issue 16
  <https://github.com/zopefoundation/zope.sendmail/issues/16>`_.



4.2 (2018-10-10)
================

- Add support for Python 3.7.


4.1.0 (2017-09-02)
==================

- Host documentation at https://zopesendmail.readthedocs.io/

- Make the data manager sort key a string, this fixes Python 3 where
  strings and integers are not sortable. This would happen when using
  other data managers with string sort keys.

- Add support for Python 3.5 and 3.6.

- Drop support for Python 2.6 and 3.3.

- Declare explicit dependency on ``pywin32`` on Windows.

- Replace hard-coded constants with equivalents from the standard
  ``errno`` module.

- Fix SSL support on Python 3. See `issue 9
  <https://github.com/zopefoundation/zope.sendmail/issues/9>`_.

- Reach 100% test coverage and maintain it via tox.ini and CI.

- Replaced deprecated dependency on ``optparse`` with equivalent
  ``argparse``. The help messages have changed and errors are
  generally more clear. Specifying a ``--config`` path that doesn't
  exist is now an error instead of being silently ignored.

- Fix SMTPMailer sending more than one message. It now reconnects to
  the SMTP server as needed. Previously it could only send one message
  since it closed the connection after each send. This also makes the
  SMTPMailer thread safe. See `issue 1
  <https://github.com/zopefoundation/zope.sendmail/issues/1>`_.


4.0.1 (2014-12-29)
==================

- Add support for PyPy3.


4.0.0 (2014-12-20)
==================

- Add support for testing in CI against supported Python verisons.

- Drop use of ``zope.testrunner`` for testing.

- Drop dependency on ``six``.

- Replace doctests with equivalent unittests.


4.0.0a2 (2013-02-26)
====================

- Fix license Trove classifier.


4.0.0a1 (2013-02-25)
====================

- Add support for Python 3.3.

- Delete event fossils (interfaces ``zope.sendmail.interfaces.IMailSent`` and
  ``zope.sendmail.interfaces.IMailError``. plus the ``zope.sendmail.events``
  module and associated tests).  These events were never emitted, and couldn't
  have been used safely even if they had been, due to two-phase commit.
  https://bugs.launchpad.net/zope3/+bug/177739

- Replace deprecated ``zope.interface.classProvides`` usage with equivalent
  ``zope.interface.provider`` decorator.

- Replace deprecated ``zope.interface.implements`` usage with equivalent
  ``zope.interface.implementer`` decorator.

- Drop support for Python 2.4 and 2.5.

- Add a vote method to Mailer implementations to allow them to abort a
  transaction if it is known to be unsafe.

- Prevent fatal errors in mail delivery causing potential database corruption.

- Add not declared, but needed test dependency on `zope.component [test]`.

- Add handling for unicode usernames and passwords, encoding them to UTF-8.
  Fix for https://bugs.launchpad.net/zope.sendmail/+bug/597143

- Give the background queue processor thread a name.

- Document the ini file keys for ``zope-sendmail --config`` in the help
  message printed by ``zope-sendmail --help``.  Also rewrote the command-line
  parsing to use optparse (not argparse, since Python 2.6 is still supported).

3.7.5 (2012-05-23)
==================

- Ensure that the 'queuedDelivery' directive has the same discriminator
  as the 'directDelivery' directive (they are mutually incompatible).
  https://bugs.launchpad.net/zope.sendmail/+bug/191143

- Avoid requeuing messages after an SMTP "recipients refused" error.
  https://bugs.launchpad.net/zope.sendmail/+bug/1003288

3.7.4 (2010-10-01)
==================

- Handle unicode usernames and passwords, encoding them to UTF-8. Fix for
  https://bugs.launchpad.net/zope.sendmail/+bug/597143

3.7.3 (2010-09-25)
==================

- Add not declared, but needed test dependency on `zope.component [test]`.

3.7.2 (2010-04-30)
==================

- Remove no longer required testing dependency on zope.testing.

- Maildir storage for queue can now handle unicode passed in for message or
  to/from addresses (change backported from repoze.sendmail).

- Tests use stdlib doctest instead of zope.testing.doctest.

3.7.1 (2010-01-13)
==================

- Backward compatibility import of zope.sendmail.queue.QueueProcessorThread in
  zope.sendmail.delivery.

3.7.0 (2010-01-12)
==================

- Remove dependency on ``zope.security``: the security support is optional,
  and only available if the ``zope.security`` package is available. This change
  is similar to the optional security support introduced in ``zope.component``
  3.8.0, and in fact it uses the same helpers.

- Sort by modification time the messages in zope.sendmail.maildir so earlier
  messages are sent before later messages during queue processing.

- Add the new parameter ``processorThread`` to the queuedDelivery ZCML
  directive: if False, the QueueProcessorThread is not started and thus an
  independent process must process the queue; it defaults to True for b/c.

- Provide a console script ``zope-sendmail`` which can be used to process the
  delivery queue in case processorThread is False. The console script can
  either process the messages in the queue once, or run in "daemon" mode.

3.6.1 (2009-11-16)
==================

- Depend on ``zope.component`` >= 3.8.0, which supports the new semantic of
  zope.component.zcml.proxify needed by zope.sendmail.zcml.

3.6.0 (2009-09-14)
==================

- Use simple vocabulary factory function instead of custom `UtilityTerm`
  and `UtilityVocabulary` classes, copied from ``zope.app.component`` in
  the previous release.

- Depend on the ``transaction`` package instead of ``ZODB3``.

- Remove zcml slugs and zpkg-related files.

- Work around problem when used with Python >=2.5.1.  See
  https://bugs.edge.launchpad.net/zope.sendmail/+bug/413335 .

3.5.1 (2009-01-26)
==================

- Copyover the UtilityTerm and UtilityVocabulary implementation from
  zope.app.component to avoid a dependency.

- Work around a problem when smtp quit fails, the mail was considered not
  delivered where just the quit failed.

3.5.0 (2008-07-05)
==================

- final release (identical with 3.5.0b2)

3.5.0b2 (2007-12-19)
====================

- If the SMTP server rejects a message (for example, when the sender or
  recipient address is malformed), that email stays in the queue forever
  (https://bugs.launchpad.net/zope3/+bug/157104).

3.5.0b1 (2007-11-08)
====================

- Add README.txt
- Can now talk to servers that don't implement EHLO
- Fix bug that caused files with very long names to be created
- Fix for https://bugs.launchpad.net/zope3/+bug/157104: move aside mail that's
  causing 5xx server responses.


3.5.0a2 (2007-10-23)
====================

- Clean up ``does_esmtp`` in faux SMTP connection classes provided by the
  tests.
- If the ``QueueProcessorThread`` is asked to stop while sending messages, do
  so after sending the current message; previously if there were many, many
  messages to send, the thread could stick around for quite a while.


3.5.0a1 (2007-10-23)
====================

- ``QueueProcessorThread`` now accepts an optional parameter *interval* for
  defining how often to process the mail queue (default is 3 seconds)

- Several ``QueueProcessorThreads`` (either in the same process, or multiple
  processes) can now deliver messages from a single maildir without duplicates
  being sent.


3.4.0 (2007-08-20)
==================

- Bugfix: Don't keep open files around for every email message
  to be sent on transaction commit.  People who try to send many emails
  in a single transaction now will not run out of file descriptors.


3.4.0a1 (2007-04-22)
====================

Initial release as a separate project, corresponds to ``zope.sendmail``
from Zope 3.4.0a1.
