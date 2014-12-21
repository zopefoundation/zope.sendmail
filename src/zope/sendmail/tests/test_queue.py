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
"""
import os.path
import shutil
import sys
from tempfile import mkdtemp
from unittest import TestCase, TestSuite, makeSuite, main

from zope.sendmail.queue import ConsoleApp
from zope.sendmail.tests.test_delivery import MaildirStub, LoggerStub, \
    BrokenMailerStub, SMTPResponseExceptionMailerStub, MailerStub

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO


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

    def test_threadName(self):
        self.assertEqual(self.thread.getName(),
                          "zope.sendmail.queue.QueueProcessorThread")

    def test_parseMessage(self):
        hdr = ('X-Zope-From: foo@example.com\n'
               'X-Zope-To: bar@example.com, baz@example.com\n')
        msg = ('Header: value\n'
               '\n'
               'Body\n')
        f, t, m = self.thread._parseMessage(hdr + msg)
        self.assertEqual(f, 'foo@example.com')
        self.assertEqual(t, ('bar@example.com', 'baz@example.com'))
        self.assertEqual(m, msg)

    def test_deliveration(self):
        self.filename = os.path.join(self.dir, 'message')
        with open(self.filename, "w+b") as temp:
            temp.write(b'X-Zope-From: foo@example.com\n'
                       b'X-Zope-To: bar@example.com, baz@example.com\n'
                       b'Header: value\n\nBody\n')
        self.md.files.append(self.filename)
        self.thread.run(forever=False)
        self.assertEqual(self.mailer.sent_messages,
                          [('foo@example.com',
                            ('bar@example.com', 'baz@example.com'),
                            'Header: value\n\nBody\n')])
        self.assertFalse(os.path.exists(self.filename), 'File exists')
        self.assertEqual(self.thread.log.infos,
                          [('Mail from %s to %s sent.',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com'),
                            {})])

    def test_error_logging(self):
        self.thread.setMailer(BrokenMailerStub())
        self.filename = os.path.join(self.dir, 'message')
        with open(self.filename, "w+b") as temp:
            temp.write(b'X-Zope-From: foo@example.com\n'
                       b'X-Zope-To: bar@example.com, baz@example.com\n'
                       b'Header: value\n\nBody\n')
        self.md.files.append(self.filename)
        self.thread.run(forever=False)
        self.assertEqual(self.thread.log.errors,
                          [('Error while sending mail from %s to %s.',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com'),
                            {'exc_info': 1})])

    def test_smtp_response_error_transient(self):
        # Test a transient error
        self.thread.setMailer(SMTPResponseExceptionMailerStub(451))
        self.filename = os.path.join(self.dir, 'message')
        with open(self.filename, "w+b") as temp:
            temp.write(b'X-Zope-From: foo@example.com\n'
                       b'X-Zope-To: bar@example.com, baz@example.com\n'
                       b'Header: value\n\nBody\n')
        self.md.files.append(self.filename)
        self.thread.run(forever=False)

        # File must remail were it was, so it will be retried
        self.assertTrue(os.path.exists(self.filename))
        self.assertEqual(self.thread.log.errors,
                          [('Error while sending mail from %s to %s.',
                            ('foo@example.com',
                             'bar@example.com, baz@example.com'),
                            {'exc_info': 1})])

    def test_smtp_response_error_permanent(self):
        # Test a permanent error
        self.thread.setMailer(SMTPResponseExceptionMailerStub(550))
        self.filename = os.path.join(self.dir, 'message')
        with open(self.filename, "w+b") as temp:
            temp.write(b'X-Zope-From: foo@example.com\n'
                       b'X-Zope-To: bar@example.com, baz@example.com\n'
                       b'Header: value\n\nBody\n')
        self.md.files.append(self.filename)
        self.thread.run(forever=False)

        # File must be moved aside
        self.assertFalse(os.path.exists(self.filename))
        self.assertTrue(os.path.exists(os.path.join(self.dir,
                                                    '.rejected-message')))
        self.assertEqual(self.thread.log.errors,
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
        with open(self.filename, "w+b") as temp:
            temp.write(b'X-Zope-From: foo@example.com\n'
                       b'X-Zope-To: bar@example.com, baz@example.com\n'
                       b'Header: value\n\nBody\n')
        self.md.files.append(self.filename)
        self.thread.run(forever=False)

        # File must be moved aside
        self.assertFalse(os.path.exists(self.filename))
        self.assertTrue(os.path.exists(os.path.join(self.dir,
                                                    '.rejected-message')))
        self.assertEqual(self.thread.log.errors,
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
        self.real_stderr = sys.stderr
        self.stderr = StringIO()

    def tearDown(self):
        sys.stderr = self.real_stderr
        shutil.rmtree(self.dir)

    def test_args_processing(self):
        # simplest case that works
        cmdline = "zope-sendmail %s" % self.dir
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEqual("zope-sendmail", app.script_name)
        self.assertEqual(self.dir, app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEqual(3, app.interval)
        self.assertEqual("localhost", app.hostname)
        self.assertEqual(25, app.port)
        self.assertEqual(None, app.username)
        self.assertEqual(None, app.password)
        self.assertFalse(app.force_tls)
        self.assertFalse(app.no_tls)

    def test_args_processing_no_queue_path(self):
        # simplest case that doesn't work: no queue path specified
        cmdline = "zope-sendmail"
        sys.stderr = self.stderr
        self.assertRaises(SystemExit, ConsoleApp, cmdline.split(), verbose=False)

    def test_args_processing_almost_all_options(self):
        # use (almost) all of the options
        cmdline = "zope-sendmail --daemon --interval 7 --hostname foo --port 75 " \
            "--username chris --password rossi --force-tls " \
            "%s" % self.dir
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEqual("zope-sendmail", app.script_name)
        self.assertEqual(self.dir, app.queue_path)
        self.assertTrue(app.daemon)
        self.assertEqual(7, app.interval)
        self.assertEqual("foo", app.hostname)
        self.assertEqual(75, app.port)
        self.assertEqual("chris", app.username)
        self.assertEqual("rossi", app.password)
        self.assertTrue(app.force_tls)
        self.assertFalse(app.no_tls)

    def test_args_processing_username_without_password(self):
        # test username without password
        cmdline = "zope-sendmail --username chris %s" % self.dir
        sys.stderr = self.stderr
        self.assertRaises(SystemExit, ConsoleApp, cmdline.split(), verbose=False)

    def test_args_processing_force_tls_and_no_tls(self):
        # test force_tls and no_tls
        cmdline = "zope-sendmail --force-tls --no-tls %s" % self.dir
        sys.stderr = self.stderr
        self.assertRaises(SystemExit, ConsoleApp, cmdline.split(), verbose=False)

    def test_ini_parse(self):
        ini_path = os.path.join(self.dir, "zope-sendmail.ini")
        with open(ini_path, "w") as f:
            f.write(test_ini)
        # override most everything
        cmdline = """zope-sendmail --config %s""" % ini_path
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEqual("zope-sendmail", app.script_name)
        self.assertEqual("hammer/dont/hurt/em", app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEqual(33, app.interval)
        self.assertEqual("testhost", app.hostname)
        self.assertEqual(2525, app.port)
        self.assertEqual("Chris", app.username)
        self.assertEqual("Rossi", app.password)
        self.assertFalse(app.force_tls)
        self.assertTrue(app.no_tls)
        # override nothing, make sure defaults come through
        with open(ini_path, "w") as f:
            f.write("[app:zope-sendmail]\n\nqueue_path=foo\n")
        cmdline = """zope-sendmail --config %s %s""" % (ini_path, self.dir)
        app = ConsoleApp(cmdline.split(), verbose=False)
        self.assertEqual("zope-sendmail", app.script_name)
        self.assertEqual(self.dir, app.queue_path)
        self.assertFalse(app.daemon)
        self.assertEqual(3, app.interval)
        self.assertEqual("localhost", app.hostname)
        self.assertEqual(25, app.port)
        self.assertEqual(None, app.username)
        self.assertEqual(None, app.password)
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
