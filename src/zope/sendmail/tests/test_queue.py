##############################################################################
#
# Copyright (c) 2003 Zope Foundation and Contributors.
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

from zope.sendmail.queue import ConsoleApp
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

    def test_smtp_recipients_refused(self):
        # Test a permanent error
        self.thread.setMailer(SMTPRecipientsRefusedMailerStub(
                               ['bar@example.com']))
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
                          [('Email recipients refused: %s',
                           ('bar@example.com',), {})])

test_ini = """[app:zope-sendmail]
interval = 33
hostname = testhost
port = 2525
username = Chris
password = Rossi
force_tls = False
no_tls = True
queue_path = hammer/dont/hurt/em
"""

class TestConsoleApp(TestCase):
    def setUp(self):
        from zope.sendmail.delivery import QueuedMailDelivery
        from zope.sendmail.maildir import Maildir
        self.dir = mkdtemp()
        self.queue_dir = os.path.join(self.dir, "queue")
        self.delivery = QueuedMailDelivery(self.queue_dir)
        self.maildir = Maildir(self.queue_dir, True)
        self.mailer = MailerStub()
        
    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_args_processing(self):
        # simplest case that works
        cmdline = "zope-sendmail %s" % self.dir
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEquals("zope-sendmail", app.script_name)
        self.assertFalse(app._error)
        self.assertEquals(self.dir, app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEquals(3, app.interval)
        self.assertEquals("localhost", app.hostname)
        self.assertEquals(25, app.port)
        self.assertEquals(None, app.username)
        self.assertEquals(None, app.password)
        self.assertFalse(app.force_tls)
        self.assertFalse(app.no_tls)
        # simplest case that doesn't work
        cmdline = "zope-sendmail"
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEquals("zope-sendmail", app.script_name)
        self.assertTrue(app._error)
        self.assertEquals(None, app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEquals(3, app.interval)
        self.assertEquals("localhost", app.hostname)
        self.assertEquals(25, app.port)
        self.assertEquals(None, app.username)
        self.assertEquals(None, app.password)
        self.assertFalse(app.force_tls)
        self.assertFalse(app.no_tls)
        # use (almost) all of the options
        cmdline = "zope-sendmail --daemon --interval 7 --hostname foo --port 75 " \
            "--username chris --password rossi --force-tls " \
            "%s" % self.dir
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEquals("zope-sendmail", app.script_name)
        self.assertFalse(app._error)
        self.assertEquals(self.dir, app.queue_path)
        self.assertTrue(app.daemon)
        self.assertEquals(7, app.interval)
        self.assertEquals("foo", app.hostname)
        self.assertEquals(75, app.port)
        self.assertEquals("chris", app.username)
        self.assertEquals("rossi", app.password)
        self.assertTrue(app.force_tls)
        self.assertFalse(app.no_tls)
        # test username without password
        cmdline = "zope-sendmail --username chris %s" % self.dir
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertTrue(app._error)
        # test --tls and --no-tls together
        cmdline = "zope-sendmail --tls --no-tls %s" % self.dir
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertTrue(app._error)
        # test force_tls and no_tls
        comdline = "zope-sendmail --force-tls --no-tls %s" % self.dir
        self.assertTrue(app._error)
        
    def test_ini_parse(self):
        ini_path = os.path.join(self.dir, "zope-sendmail.ini")
        f = open(ini_path, "w")
        f.write(test_ini)
        f.close()
        # override most everything
        cmdline = """zope-sendmail --config %s""" % ini_path
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEquals("zope-sendmail", app.script_name)
        self.assertFalse(app._error)
        self.assertEquals("hammer/dont/hurt/em", app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEquals(33, app.interval)
        self.assertEquals("testhost", app.hostname)
        self.assertEquals(2525, app.port)
        self.assertEquals("Chris", app.username)
        self.assertEquals("Rossi", app.password)
        self.assertFalse(app.force_tls)
        self.assertTrue(app.no_tls)
        # override nothing, make sure defaults come through
        f = open(ini_path, "w")
        f.write("[app:zope-sendmail]\n\nqueue_path=foo\n")
        f.close()
        cmdline = """zope-sendmail --config %s %s""" % (ini_path, self.dir)
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEquals("zope-sendmail", app.script_name)
        self.assertFalse(app._error)
        self.assertEquals(self.dir, app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEquals(3, app.interval)
        self.assertEquals("localhost", app.hostname)
        self.assertEquals(25, app.port)
        self.assertEquals(None, app.username)
        self.assertEquals(None, app.password)
        self.assertFalse(app.force_tls)
        self.assertFalse(app.no_tls)


class SMTPRecipientsRefusedMailerStub(object):

    def __init__(self, recipients):
        self.recipients = recipients

    def send(self, fromaddr, toaddrs, message):
        import smtplib
        raise smtplib.SMTPRecipientsRefused(self.recipients)


def test_suite():
    return TestSuite((
        makeSuite(TestQueueProcessorThread),
        makeSuite(TestConsoleApp),
        ))

if __name__ == '__main__':
    main()
