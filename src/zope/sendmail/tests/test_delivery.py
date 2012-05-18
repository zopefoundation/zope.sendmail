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

import smtplib
from unittest import TestCase, TestSuite, makeSuite, main
import doctest

import transaction
from zope.interface import implementer
from zope.interface.verify import verifyObject
from zope.sendmail.interfaces import IMailer


@implementer(IMailer)
class MailerStub(object):

    def __init__(self, *args, **kw):
        self.sent_messages = []

    def send(self, fromaddr, toaddrs, message):
        self.sent_messages.append((fromaddr, toaddrs, message))
    
    abort = None
    vote = None


class TestMailDataManager(TestCase):

    def testInterface(self):
        from transaction.interfaces import IDataManager
        from zope.sendmail.delivery import MailDataManager
        manager = MailDataManager(object, (1, 2))
        verifyObject(IDataManager, manager)
        self.assertEqual(manager.callable, object)
        self.assertEqual(manager.args, (1, 2))


def print_success(*args):
    print "message successfully sent, args: %s" % (args, )

def print_abort():
    print "message aborted"


def doctest_successful_commit():
    """Regression test for http://www.zope.org/Collectors/Zope3-dev/590

    Let's do a full two-phase commit.

        >>> from zope.sendmail.delivery import MailDataManager
        >>> manager = MailDataManager(print_success, ('foo', 'bar'),
        ...                           onAbort=print_abort)
        >>> transaction = object()
        >>> manager.tpc_begin(transaction)
        >>> manager.commit(transaction)
        >>> manager.tpc_vote(transaction)
        >>> manager.tpc_finish(transaction)
        message successfully sent, args: ('foo', 'bar')

    """


def doctest_unsuccessful_commit():
    """Regression test for http://www.zope.org/Collectors/Zope3-dev/590

    Let's start a two-phase commit, then abort it.

        >>> from zope.sendmail.delivery import MailDataManager
        >>> manager = MailDataManager(print_success, onAbort=print_abort)
        >>> manager.tpc_begin(transaction)
        >>> manager.commit(transaction)
        >>> manager.tpc_vote(transaction)
        >>> manager.tpc_abort(transaction)
        message aborted

    """


class TestDirectMailDelivery(TestCase):

    def testInterface(self):
        from zope.sendmail.interfaces import IDirectMailDelivery
        from zope.sendmail.delivery import DirectMailDelivery
        mailer = MailerStub()
        delivery = DirectMailDelivery(mailer)
        verifyObject(IDirectMailDelivery, delivery)
        self.assertEqual(delivery.mailer, mailer)

    def testSend(self):
        from zope.sendmail.delivery import DirectMailDelivery
        mailer = MailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',
                   'Steve <steve@examplecom>')
        opt_headers = ('From: Jim <jim@example.org>\n'
                       'To: some-zope-coders:;\n'
                       'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       'Message-Id: <20030519.1234@example.org>\n')
        message =     ('Subject: example\n'
                       '\n'
                       'This is just an example\n')

        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEquals(msgid, '20030519.1234@example.org')
        self.assertEquals(mailer.sent_messages, [])
        transaction.commit()
        self.assertEquals(mailer.sent_messages,
                          [(fromaddr, toaddrs, opt_headers + message)])

        mailer.sent_messages = []
        msgid = delivery.send(fromaddr, toaddrs, message)
        self.assert_('@' in msgid)
        self.assertEquals(mailer.sent_messages, [])
        transaction.commit()
        self.assertEquals(len(mailer.sent_messages), 1)
        self.assertEquals(mailer.sent_messages[0][0], fromaddr)
        self.assertEquals(mailer.sent_messages[0][1], toaddrs)
        self.assert_(mailer.sent_messages[0][2].endswith(message))
        new_headers = mailer.sent_messages[0][2][:-len(message)]
        self.assert_(new_headers.find('Message-Id: <%s>' % msgid) != -1)

        mailer.sent_messages = []
        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEquals(mailer.sent_messages, [])
        transaction.abort()
        self.assertEquals(mailer.sent_messages, [])
    
    def testBrokenMailerErrorsAreEaten(self):
        from zope.sendmail.delivery import DirectMailDelivery
        mailer = BrokenMailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',
                   'Steve <steve@examplecom>')
        opt_headers = ('From: Jim <jim@example.org>\n'
                       'To: some-zope-coders:;\n'
                       'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       'Message-Id: <20030519.1234@example.org>\n')
        message =     ('Subject: example\n'
                       '\n'
                       'This is just an example\n')

        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        try:
            transaction.commit()
        finally:
            # Clean up after ourselves
            transaction.abort()
    
    def testRefusingMailerDiesInVote(self):
        from zope.sendmail.delivery import DirectMailDelivery
        mailer = RefusingMailerStub()
        delivery = DirectMailDelivery(mailer)
        fromaddr = 'Jim <jim@example.com'
        toaddrs = ('Guido <guido@example.com>',
                   'Steve <steve@examplecom>')
        opt_headers = ('From: Jim <jim@example.org>\n'
                       'To: some-zope-coders:;\n'
                       'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       'Message-Id: <20030519.1234@example.org>\n')
        message =     ('Subject: example\n'
                       '\n'
                       'This is just an example\n')

        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        try:
            try:
                transaction.commit()
            except:
                if transaction.get()._voted:
                    # We voted for commit then failed, reraise
                    raise
                else:
                    # We vetoed a commit, that's good.
                    pass
            else:
                self.fail("Did not raise an exception in vote")
        finally:
            # Clean up after ourselves
            transaction.abort()

class MaildirWriterStub(object):

    data = ''
    commited_messages = []  # this list is shared among all instances
    aborted_messages = []   # this one too
    _closed = False

    def write(self, str):
        if self._closed:
            raise AssertionError('already closed')
        self.data += str

    def writelines(self, seq):
        if self._closed:
            raise AssertionError('already closed')
        self.data += ''.join(seq)

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


class MaildirStub(object):

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


class LoggerStub(object):

    def __init__(self):
        self.infos = []
        self.errors = []

    def getLogger(self, name):
        return self

    def error(self, msg, *args, **kwargs):
        self.errors.append((msg, args, kwargs))

    def info(self, msg, *args, **kwargs):
        self.infos.append((msg, args, kwargs))


class BizzarreMailError(IOError):
    pass


@implementer(IMailer)
class BrokenMailerStub(object):

    def __init__(self, *args, **kw):
        pass

    def send(self, fromaddr, toaddrs, message):
        raise BizzarreMailError("bad things happened while sending mail")
    
    vote = None
    abort = None


@implementer(IMailer)
class RefusingMailerStub(object):

    def __init__(self, *args, **kw):
        pass

    def vote(self, fromaddr, toaddrs, message):
        raise BizzarreMailError("bad things happened while sending mail")

    def send(self, fromaddr, toaddrs, message):
        return

    abort = None

@implementer(IMailer)
class SMTPResponseExceptionMailerStub(object):

    def __init__(self, code):
        self.code = code

    def send(self, fromaddr, toaddrs, message):
        raise smtplib.SMTPResponseException(self.code,  'Serious Error')


class TestQueuedMailDelivery(TestCase):

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
        from zope.sendmail.interfaces import IQueuedMailDelivery
        from zope.sendmail.delivery import QueuedMailDelivery
        delivery = QueuedMailDelivery('/path/to/mailbox')
        verifyObject(IQueuedMailDelivery, delivery)
        self.assertEqual(delivery.queuePath, '/path/to/mailbox')

    def testSend(self):
        from zope.sendmail.delivery import QueuedMailDelivery
        delivery = QueuedMailDelivery('/path/to/mailbox')
        fromaddr = 'jim@example.com'
        toaddrs = ('guido@example.com',
                   'steve@examplecom')
        zope_headers = ('X-Zope-From: jim@example.com\n'
                       'X-Zope-To: guido@example.com, steve@examplecom\n')
        opt_headers = ('From: Jim <jim@example.org>\n'
                       'To: some-zope-coders:;\n'
                       'Date: Mon, 19 May 2003 10:17:36 -0400\n'
                       'Message-Id: <20030519.1234@example.org>\n')
        message =     ('Subject: example\n'
                       '\n'
                       'This is just an example\n')

        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEquals(msgid, '20030519.1234@example.org')
        self.assertEquals(MaildirWriterStub.commited_messages, [])
        self.assertEquals(MaildirWriterStub.aborted_messages, [])
        transaction.commit()
        self.assertEquals(MaildirWriterStub.commited_messages,
                          [zope_headers + opt_headers + message])
        self.assertEquals(MaildirWriterStub.aborted_messages, [])

        MaildirWriterStub.commited_messages = []
        msgid = delivery.send(fromaddr, toaddrs, message)
        self.assert_('@' in msgid)
        self.assertEquals(MaildirWriterStub.commited_messages, [])
        self.assertEquals(MaildirWriterStub.aborted_messages, [])
        transaction.commit()
        self.assertEquals(len(MaildirWriterStub.commited_messages), 1)
        self.assert_(MaildirWriterStub.commited_messages[0].endswith(message))
        new_headers = MaildirWriterStub.commited_messages[0][:-len(message)]
        self.assert_(new_headers.find('Message-Id: <%s>' % msgid) != -1)
        self.assert_(new_headers.find('X-Zope-From: %s' % fromaddr) != 1)
        self.assert_(new_headers.find('X-Zope-To: %s' % ", ".join(toaddrs)) != 1)
        self.assertEquals(MaildirWriterStub.aborted_messages, [])

        MaildirWriterStub.commited_messages = []
        msgid = delivery.send(fromaddr, toaddrs, opt_headers + message)
        self.assertEquals(MaildirWriterStub.commited_messages, [])
        self.assertEquals(MaildirWriterStub.aborted_messages, [])
        transaction.abort()
        self.assertEquals(MaildirWriterStub.commited_messages, [])
        self.assertEquals(len(MaildirWriterStub.aborted_messages), 1)


def test_suite():
    return TestSuite((
        makeSuite(TestMailDataManager),
        makeSuite(TestDirectMailDelivery),
        makeSuite(TestQueuedMailDelivery),
        doctest.DocTestSuite(),
        ))

if __name__ == '__main__':
    main()
