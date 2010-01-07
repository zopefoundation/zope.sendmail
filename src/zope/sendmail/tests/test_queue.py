##############################################################################
#
# Copyright (c) 2003 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Mail Delivery Tests

Simple implementation of the MailDelivery, Mailers and MailEvents.

$Id$
"""

import os.path
import shutil

from tempfile import mkdtemp
from unittest import TestCase, TestSuite, makeSuite, main

from zope.sendmail.tests.test_delivery import MaildirStub, LoggerStub, \
    BrokenMailerStub, SMTPResponseExceptionMailerStub, MailerStub


class TestQueueProcessorThread(TestCase):

    def setUp(self):
        from zope.sendmail.queue import QueueProcessorThread
        self.md = MaildirStub('/foo/bar/baz')
        self.thread = QueueProcessorThread()
        self.thread.setMaildir(self.md)
        self.mailer = MailerStub()
        self.thread.setMailer(self.mailer)
        self.thread.log = LoggerStub()
        self.dir = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_parseMessage(self):
        hdr = ('X-Zope-From: foo@example.com\n'
               'X-Zope-To: bar@example.com, baz@example.com\n')
        msg = ('Header: value\n'
               '\n'
               'Body\n')
        f, t, m = self.thread._parseMessage(hdr + msg)
        self.assertEquals(f, 'foo@example.com')
        self.assertEquals(t, ('bar@example.com', 'baz@example.com'))
        self.assertEquals(m, msg)

    def test_deliveration(self):
        self.filename = os.path.join(self.dir, 'message')
        temp = open(self.filename, "w+b")
        temp.write('X-Zope-From: foo@example.com\n'
                   'X-Zope-To: bar@example.com, baz@example.com\n'
                   'Header: value\n\nBody\n')
        temp.close()
        self.md.files.append(self.filename)
        self.thread.run(forever=False)
        self.assertEquals(self.mailer.sent_messages,
                          [('foo@example.com',
                            ('bar@example.com', 'baz@example.com'),
                            'Header: value\n\nBody\n')])
        self.failIf(os.path.exists(self.filename), 'File exists')
        self.assertEquals(self.thread.log.infos,
                          [('Mail from %s to %s sent.',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com'),
                            {})])

    def test_error_logging(self):
        self.thread.setMailer(BrokenMailerStub())
        self.filename = os.path.join(self.dir, 'message')
        temp = open(self.filename, "w+b")
        temp.write('X-Zope-From: foo@example.com\n'
                   'X-Zope-To: bar@example.com, baz@example.com\n'
                   'Header: value\n\nBody\n')
        temp.close()
        self.md.files.append(self.filename)
        self.thread.run(forever=False)
        self.assertEquals(self.thread.log.errors,
                          [('Error while sending mail from %s to %s.',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com'),
                            {'exc_info': 1})])

    def test_smtp_response_error_transient(self):
        # Test a transient error
        self.thread.setMailer(SMTPResponseExceptionMailerStub(451))
        self.filename = os.path.join(self.dir, 'message')
        temp = open(self.filename, "w+b")
        temp.write('X-Zope-From: foo@example.com\n'
                   'X-Zope-To: bar@example.com, baz@example.com\n'
                   'Header: value\n\nBody\n')
        temp.close()
        self.md.files.append(self.filename)
        self.thread.run(forever=False)

        # File must remail were it was, so it will be retried
        self.failUnless(os.path.exists(self.filename))
        self.assertEquals(self.thread.log.errors,
                          [('Error while sending mail from %s to %s.',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com'),
                            {'exc_info': 1})])

    def test_smtp_response_error_permanent(self):
        # Test a permanent error
        self.thread.setMailer(SMTPResponseExceptionMailerStub(550))
        self.filename = os.path.join(self.dir, 'message')
        temp = open(self.filename, "w+b")
        temp.write('X-Zope-From: foo@example.com\n'
                   'X-Zope-To: bar@example.com, baz@example.com\n'
                   'Header: value\n\nBody\n')
        temp.close()
        self.md.files.append(self.filename)
        self.thread.run(forever=False)

        # File must be moved aside
        self.failIf(os.path.exists(self.filename))
        self.failUnless(os.path.exists(os.path.join(self.dir,
                                                    '.rejected-message')))
        self.assertEquals(self.thread.log.errors,
                          [('Discarding email from %s to %s due to a '
                            'permanent error: %s',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com',
                             "(550, 'Serious Error')"), {})])


def test_suite():
    return TestSuite((
        makeSuite(TestQueueProcessorThread),
        ))

if __name__ == '__main__':
    main()
