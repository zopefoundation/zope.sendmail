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
import smtplib
import sys
import tempfile
import unittest

import transaction
from zope.interface import implementer
from zope.interface.verify import verifyObject

from zope.sendmail.delivery import AbstractMailDelivery
from zope.sendmail.delivery import DirectMailDelivery
from zope.sendmail.interfaces import IDirectMailDelivery
from zope.sendmail.interfaces import IMailer


@implementer(IMailer)
class MailerStub:

    def __init__(self, *args, **kw):
        self.sent_messages = []

    def send(self, fromaddr, toaddrs, message):
        self.sent_messages.append((fromaddr, toaddrs, message))

    abort = None
    vote = None


class TestMailDataManager(unittest.TestCase):

    def testInterface(self):
        from transaction.interfaces import IDataManager

        from zope.sendmail.delivery import MailDataManager
        manager = MailDataManager(object, (1, 2))
        verifyObject(IDataManager, manager)
        self.assertEqual(manager.callable, object)
        self.assertEqual(manager.args, (1, 2))
        # required by IDataManager
        self.assertIsInstance(manager.sortKey(), str)

    def test_successful_commit(self):
        # Regression test for http://www.zope.org/Collectors/Zope3-dev/590
        from zope.sendmail.delivery import MailDataManager

        _success = []

        def _on_success(*args):
            _success.append(args)

        def _on_abort(*args):
            self.fail("Should not abort")

        manager = MailDataManager(_on_success, ('foo', 'bar'),
                                  onAbort=_on_abort)
        xact = object()
        manager.tpc_begin(xact)
        manager.commit(xact)
        manager.tpc_vote(xact)
        manager.tpc_finish(xact)
        self.assertEqual(_success, [('foo', 'bar')])

    def test_unsuccessful_commit(self):
        # Regression test for http://www.zope.org/Collectors/Zope3-dev/590
        from zope.sendmail.delivery import MailDataManager

        _success = []
        _abort = []

        def _on_success(*args):
            self.fail("Should not succeed")

        def _on_abort(*args):
            _abort.append(args)
        manager = MailDataManager(_on_success, ('foo', 'bar'),
                                  onAbort=_on_abort)
        xact = object()
        manager.tpc_begin(xact)
        manager.commit(xact)
        manager.tpc_vote(xact)
        manager.tpc_abort(xact)
        self.assertEqual(_success, [])


class TestAbstractMailDelivery(unittest.TestCase):

    def test_bad_message_id(self):
        class Parser:
            def parsestr(self, s, headersonly=False):
                return {'Message-Id': 'bad id'}

        import email.parser
        orig_parser = email.parser.Parser
        self.addCleanup(setattr, email.parser, 'Parser', orig_parser)
        email.parser.Parser = Parser

        delivery = AbstractMailDelivery()
        with self.assertRaisesRegex(ValueError,
                                    "Malformed Message-Id header"):
            delivery.send(None, None, None)


class TestDirectMailDelivery(unittest.TestCase):

    def testInterface(self):
        mailer = MailerStub()
        delivery = DirectMailDelivery(mailer)
        verifyObject(IDirectMailDelivery, delivery)
        self.assertEqual(delivery.mailer, mailer)

    def testSend(self, send_unicode=False, message=None, line_sep='\n'):
        mailer = MailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',
                   'Steve <steve@examplecom>')
        sep_dict = {b'line_sep': line_sep.encode()}
        opt_headers = (
            b'From: Jim <jim@example.org>%(line_sep)s'
            b'To: some-zope-coders:;%(line_sep)s'
            b'Date: Mon, 19 May 2003 10:17:36 -0400%(line_sep)s'
            b'Message-Id: <20030519.1234@example.org>%(line_sep)s' % sep_dict)
        if message is None:
            message = (b'Subject: example%(line_sep)s'
                       b'%(line_sep)s'
                       b'This is just an example%(line_sep)s' % sep_dict)

        if send_unicode:
            opt_headers_bytes = opt_headers
            opt_headers = opt_headers.decode('utf-8')
            message_bytes = message + b'\xc3\xa4'
            message = message_bytes.decode('utf-8')
        else:
            message_bytes = message
            opt_headers_bytes = opt_headers

        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEqual(msgid, '20030519.1234@example.org')
        self.assertEqual(mailer.sent_messages, [])
        transaction.commit()
        self.assertEqual(mailer.sent_messages,
                         [(fromaddr, toaddrs,
                           opt_headers_bytes + message_bytes)])

        mailer.sent_messages = []
        msgid = delivery.send(fromaddr, toaddrs, message)
        self.assertIn('@', msgid)
        self.assertEqual(mailer.sent_messages, [])
        transaction.commit()
        self.assertEqual(len(mailer.sent_messages), 1)
        self.assertEqual(mailer.sent_messages[0][0], fromaddr)
        self.assertEqual(mailer.sent_messages[0][1], toaddrs)
        self.assertTrue(mailer.sent_messages[0][2].endswith(message_bytes))
        new_headers = mailer.sent_messages[0][2][:-len(message_bytes)]
        self.assertIn((f'Message-Id: <{msgid}>{line_sep}').encode(),
                      new_headers)

        mailer.sent_messages = []
        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEqual(mailer.sent_messages, [])
        transaction.abort()
        self.assertEqual(mailer.sent_messages, [])

    def testSendUnicode(self):
        self.testSend(send_unicode=True)

    def testSendLatin1(self):
        '''
        Test to send a mail that is not valid UTF-8. Since we are using bytes
        everywhere, this is not a problem.
        '''
        message = (b'Subject: example\n'
                   b'Content-Type: text/plain; charset="latin1"\n'
                   b'\n'
                   b'\xfc')
        self.testSend(message=message)

    def testSendCLRFLineSeparator(self):
        self.testSend(line_sep='\r\n')

    def testBrokenMailerErrorsAreEaten(self):
        from zope.testing.loggingsupport import InstalledHandler
        mailer = BrokenMailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',
                   'Steve <steve@examplecom>')
        opt_headers = ('From: Jim <jim@example.org>\n'
                       'To: some-zope-coders:;\n'
                       'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       'Message-Id: <20030519.1234@example.org>\n')
        message = ('Subject: example\n'
                   '\n'
                   'This is just an example\n')

        delivery.send(fromaddr, toaddrs, opt_headers + message)
        log_handler = InstalledHandler('MailDataManager')
        self.addCleanup(log_handler.uninstall)
        self.addCleanup(transaction.abort)
        transaction.commit()

    def testRefusingMailerDiesInVote(self):
        mailer = RefusingMailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',
                   'Steve <steve@examplecom>')
        opt_headers = ('From: Jim <jim@example.org>\n'
                       'To: some-zope-coders:;\n'
                       'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       'Message-Id: <20030519.1234@example.org>\n')
        message = ('Subject: example\n'
                   '\n'
                   'This is just an example\n')

        delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.addCleanup(transaction.abort)

        with self.assertRaises(Exception):
            transaction.commit()
        self.assertFalse(transaction.get()._voted,
                         "We voted for commit then failed, reraise")

    def test_old_mailer_without_vote(self):
        import warnings

        class OldMailer:
            def send(self):
                raise NotImplementedError()
            abort = send

        delivery = DirectMailDelivery(OldMailer())
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')

            mdm = delivery.createDataManager("from", (), "msg")
            mdm.tpc_vote(None)

        self.assertEqual(1, len(w))
        self.assertIn("does not provide a vote method", str(w[0]))

    def testSavepoint(self):
        mailer = MailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',)
        delivery.send(fromaddr, toaddrs, b'Subject: one')
        # Reminder: nothing is sent yet, sending happens after commit.
        self.assertEqual(mailer.sent_messages, [])
        # We create a savepoint.  If we rollback to this savepoint,
        # the previous mail should still remain in the queue.
        savepoint = transaction.savepoint()
        delivery.send(fromaddr, toaddrs, b'Subject: two')
        self.assertEqual(mailer.sent_messages, [])
        # We rollback to the savepoint, so mail 2 should never be send anymore.
        savepoint.rollback()
        self.assertEqual(mailer.sent_messages, [])
        # Any mail after this *should* be sent.
        delivery.send(fromaddr, toaddrs, b'Subject: three')
        self.assertEqual(mailer.sent_messages, [])
        transaction.commit()
        self.assertEqual(len(mailer.sent_messages), 2)
        # They might not necessarily be sent in the order we expect.
        # Get the subject lines.
        all_text = b'\n'.join([mail[2] for mail in mailer.sent_messages])
        lines = all_text.splitlines()
        subjects = [line for line in lines if b'Subject' in line]
        subjects.sort()
        self.assertEqual([b'Subject: one', b'Subject: three'], subjects)


class MaildirWriterStub:

    data = b''
    commited_messages = []  # this list is shared among all instances
    aborted_messages = []   # this one too
    _closed = False
    _commited = False
    _aborted = False

    def write(self, data):
        if self._closed:
            raise AssertionError('already closed')
        self.data += data

    def writelines(self, seq):
        raise NotImplementedError()

    def close(self):
        self._closed = True

    def commit(self):
        if not self._closed:
            raise AssertionError('for this test we want the message explicitly'
                                 ' closed before it is committed')
        self._commited = True
        self.commited_messages.append(self.data)

    def abort(self):
        if not self._closed:
            raise AssertionError('for this test we want the message explicitly'
                                 ' closed before it is committed')
        self._aborted = True
        self.aborted_messages.append(self.data)


class MaildirStub:

    def __init__(self, path, create=False):
        self.path = path
        self.create = create
        self.msgs = []
        self.files = []

    def __iter__(self):
        return iter(self.files)

    def newMessage(self):
        m = MaildirWriterStub()
        self.msgs.append(m)
        return m


class WritableMaildirStub(MaildirStub):

    STUB_DEFAULT_MESSAGE_LINES = (
        b'X-Zope-From: foo@example.com\n',
        b'X-Zope-To: bar@example.com, baz@example.com\n',
        b'Header: value\n\nBody\n')

    # The result of sending a message written with the default lines
    # through the stub mailer
    STUB_DEFAULT_MESSAGE_SENT = (
        'foo@example.com',
        ('bar@example.com', 'baz@example.com'),
        b'Header: value\n\nBody\n')

    STUB_DEFAULT_MESSAGE_RECPT = ('bar@example.com', 'baz@example.com')

    def __init__(self, test, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stub_directory = tempfile.mkdtemp(suffix=".test_maildir")
        test.addCleanup(shutil.rmtree, self.stub_directory)

    def stub_createFile(self, filename="message",
                        lines=STUB_DEFAULT_MESSAGE_LINES):
        """
        Create a new file in the temporary directory.

        The filename is just the base portion.
        """
        filename = os.path.join(self.stub_directory, filename)
        with open(filename, 'wb') as f:
            for line in lines:
                f.write(line)
        self.files.append(filename)
        return filename

    def stub_getTmpFilename(self, filename="message"):
        filename = os.path.join(self.stub_directory, filename)
        head, tail = os.path.split(filename)
        tmp_filename = os.path.join(head, '.sending-' + tail)
        return tmp_filename

    def stub_getFailedFilename(self, filename="message"):
        filename = os.path.join(self.stub_directory, filename)
        head, tail = os.path.split(filename)
        fail_filename = os.path.join(head, '.rejected-' + tail)
        return fail_filename

    def stub_createTmpFile(self, filename="message"):
        """
        Create a temporary version of a file that already exists by
        copying its data to a properly named file.

        Returns the complete path.
        """
        tmp_filename = self.stub_getTmpFilename(filename)
        filename = os.path.join(self.stub_directory, filename)
        shutil.copyfile(filename, tmp_filename)
        return tmp_filename


class LoggerStub:

    def __init__(self):
        self.infos = []
        self.errors = []

    def getLogger(self, name):
        raise NotImplementedError()

    def error(self, msg, *args, **kwargs):
        error = (msg, args, kwargs)
        if kwargs.get("exc_info"):
            error += sys.exc_info()[:2]
        self.errors.append(error)

    def info(self, msg, *args, **kwargs):
        self.infos.append((msg, args, kwargs))


class BizzarreMailError(IOError):
    pass


@implementer(IMailer)
class BrokenMailerStub:

    def __init__(self, *args, **kw):
        pass

    def send(self, fromaddr, toaddrs, message):
        raise BizzarreMailError("bad things happened while sending mail")

    vote = None
    abort = None


@implementer(IMailer)
class RefusingMailerStub:

    def __init__(self, *args, **kw):
        pass

    def vote(self, fromaddr, toaddrs, message):
        raise BizzarreMailError("bad things happened while sending mail")

    def send(self, fromaddr, toaddrs, message):
        raise NotImplementedError()

    abort = None


@implementer(IMailer)
class SMTPResponseExceptionMailerStub:

    def __init__(self, code):
        self.code = code

    def send(self, fromaddr, toaddrs, message):
        raise smtplib.SMTPResponseException(self.code, 'Serious Error')


class TestQueuedMailDelivery(unittest.TestCase):

    def setUp(self):
        import zope.sendmail.delivery as mail_delivery_module
        self.mail_delivery_module = mail_delivery_module
        self.old_Maildir = mail_delivery_module.Maildir
        mail_delivery_module.Maildir = MaildirStub

    def tearDown(self):
        self.mail_delivery_module.Maildir = self.old_Maildir
        MaildirWriterStub.commited_messages = []
        MaildirWriterStub.aborted_messages = []

    def testInterface(self):
        from zope.sendmail.delivery import QueuedMailDelivery
        from zope.sendmail.interfaces import IQueuedMailDelivery
        delivery = QueuedMailDelivery('/path/to/mailbox')
        verifyObject(IQueuedMailDelivery, delivery)
        self.assertEqual(delivery.queuePath, '/path/to/mailbox')

    def testSend(self):
        from zope.sendmail.delivery import QueuedMailDelivery
        delivery = QueuedMailDelivery('/path/to/mailbox')
        fromaddr = 'jim@example.com'
        toaddrs = ('guido@example.com',
                   'steve@examplecom')
        zope_headers = (b'X-Zope-From: jim@example.com\n'
                        b'X-Zope-To: guido@example.com, steve@examplecom\n')
        opt_headers = (b'From: Jim <jim@example.org>\n'
                       b'To: some-zope-coders:;\n'
                       b'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       b'Message-Id: <20030519.1234@example.org>\n')
        message = (b'Subject: example\n'
                   b'\n'
                   b'This is just an example\n')

        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEqual(msgid, '20030519.1234@example.org')
        self.assertEqual(MaildirWriterStub.commited_messages, [])
        self.assertEqual(MaildirWriterStub.aborted_messages, [])
        transaction.commit()
        self.assertEqual(MaildirWriterStub.commited_messages,
                         [zope_headers + opt_headers + message])
        self.assertEqual(MaildirWriterStub.aborted_messages, [])

        MaildirWriterStub.commited_messages = []
        msgid = delivery.send(fromaddr, toaddrs, message)
        self.assertIn('@', msgid)
        self.assertEqual(MaildirWriterStub.commited_messages, [])
        self.assertEqual(MaildirWriterStub.aborted_messages, [])
        transaction.commit()
        self.assertEqual(len(MaildirWriterStub.commited_messages), 1)
        self.assertTrue(
            MaildirWriterStub.commited_messages[0].endswith(message)
        )
        new_headers = MaildirWriterStub.commited_messages[0][:-len(message)]
        self.assertIn(('Message-Id: <%s>' % msgid).encode(), new_headers)
        self.assertIn(('X-Zope-From: %s' % fromaddr).encode(), new_headers)
        self.assertIn(('X-Zope-To: %s' % ", ".join(toaddrs)).encode(),
                      new_headers)
        self.assertEqual(MaildirWriterStub.aborted_messages, [])

        MaildirWriterStub.commited_messages = []
        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEqual(MaildirWriterStub.commited_messages, [])
        self.assertEqual(MaildirWriterStub.aborted_messages, [])
        transaction.abort()
        self.assertEqual(MaildirWriterStub.commited_messages, [])
        self.assertEqual(len(MaildirWriterStub.aborted_messages), 1)
