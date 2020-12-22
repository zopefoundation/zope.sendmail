# coding=utf-8
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
"""Tests for mailers.
"""

import unittest
from functools import partial
from ssl import SSLError

from zope.interface.verify import verifyObject
from zope.sendmail.interfaces import ISMTPMailer
from zope.sendmail.mailer import SMTPMailer


# This works for both, Python 2 and 3.
port_types = (int, str)


class SMTP(object):

    fail_on_quit = False

    def __init__(self, h, p):
        self.hostname = h
        self.port = p
        self.quitted = False
        self.closed = False
        assert isinstance(p, port_types)

    def sendmail(self, f, t, m):
        assert not self.closed
        assert not self.quitted
        self.fromaddr = f
        self.toaddrs = t
        self.msgtext = m

    def login(self, username, password):
        self.username = username
        self.password = password

    def quit(self):
        if self.fail_on_quit:
            raise SSLError("dang")
        self.quitted = True
        self.close()

    def close(self):
        self.closed = True

    def has_extn(self, ext):
        return True

    ehlo_code = 200
    ehlo_msg = 'Hello, I am your stupid MTA mock'

    def ehlo(self):
        self.does_esmtp = True
        return (self.ehlo_code, self.ehlo_msg)

    def starttls(self):
        pass


class SMTPWithNoEHLO(SMTP):
    does_esmtp = False

    def helo(self):
        return (200, 'Hello, I am your stupid MTA mock')

    ehlo_code = 502
    ehlo_msg = "I don't understand EHL"


class TestSMTPMailer(unittest.TestCase):

    SMTPClass = SMTP

    # Avoid DeprecationWarning for assertRaisesRegexp on Python 3 while
    # coping with Python 2 not having the Regex spelling variant
    assertRaisesRegex = getattr(unittest.TestCase, 'assertRaisesRegex',
                                unittest.TestCase.assertRaisesRegexp)

    def _makeMailer(self, port=None, smtp_hook=None):
        if port is None:
            mailer = SMTPMailer()
        else:
            mailer = SMTPMailer(u'localhost', port)

        def _make_smtp(host, port):
            smtp = self.SMTPClass(host, port)
            if smtp_hook:
                smtp_hook(smtp)
            return smtp

        mailer.smtp = _make_smtp
        return mailer

    def setUp(self, port=None):
        self.smtp = None
        self.mailer = self._makeMailer(
            port=port, smtp_hook=partial(setattr, self, 'smtp'))

    def test_interface(self):
        verifyObject(ISMTPMailer, self.mailer)

    def test_send(self):
        for run in (1, 2):
            if run == 2:
                self.setUp(u'25')
            fromaddr = 'me@example.com'
            toaddrs = ('you@example.com', 'him@example.com')
            msgtext = 'Headers: headers\n\nbodybodybody\n-- \nsig\n'
            self.mailer.send(fromaddr, toaddrs, msgtext)
            self.assertEqual(self.smtp.fromaddr, fromaddr)
            self.assertEqual(self.smtp.toaddrs, toaddrs)
            self.assertEqual(self.smtp.msgtext, msgtext)
            self.assertTrue(self.smtp.quitted)
            self.assertTrue(self.smtp.closed)

    def test_send_multiple_same_mailer(self):
        # The mailer re-opens itself as needed when sending
        # multiple mails.
        smtps = []
        mailer = self._makeMailer(smtp_hook=smtps.append)

        # Note: this test needs to be thread-safe so it must avoid mutating
        # attributes on `self`!

        for run in (1, 2):
            fromaddr = 'me@example.com' + str(run)
            toaddrs = ('you@example.com', 'him@example.com')
            msgtext = 'Headers: headers\n\nbodybodybody\n-- \nsig\n'
            mailer.send(fromaddr, toaddrs, msgtext)
            smtp = smtps[-1]
            self.assertEqual(smtp.fromaddr, fromaddr)
            self.assertEqual(smtp.toaddrs, toaddrs)
            self.assertEqual(smtp.msgtext, msgtext)
            self.assertTrue(smtp.quitted)
            self.assertTrue(smtp.closed)

        self.assertEqual(2, len(smtps))

    def test_send_multiple_threads(self):
        import threading

        results = []

        def run():
            try:
                self.test_send_multiple_same_mailer()
            except BaseException as e:  # pragma: no cover
                results.append(e)
                raise
            else:
                results.append(True)

        threads = []
        for _ in range(2):
            threads.append(threading.Thread(target=run))
        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.assertEqual([True for _ in threads], results)

    def test_send_auth(self):
        fromaddr = 'me@example.com'
        toaddrs = ('you@example.com', 'him@example.com')
        msgtext = 'Headers: headers\n\nbodybodybody\n-- \nsig\n'
        self.mailer.username = 'foo'
        self.mailer.password = 'evil'
        self.mailer.hostname = 'spamrelay'
        self.mailer.port = 31337
        self.mailer.send(fromaddr, toaddrs, msgtext)
        self.assertEqual(self.smtp.username, 'foo')
        self.assertEqual(self.smtp.password, 'evil')
        self.assertEqual(self.smtp.hostname, 'spamrelay')
        self.assertEqual(self.smtp.port, '31337')
        self.assertEqual(self.smtp.fromaddr, fromaddr)
        self.assertEqual(self.smtp.toaddrs, toaddrs)
        self.assertEqual(self.smtp.msgtext, msgtext)
        self.assertTrue(self.smtp.quitted)
        self.assertTrue(self.smtp.closed)

    def test_send_auth_unicode(self):
        fromaddr = 'me@example.com'
        toaddrs = ('you@example.com', 'him@example.com')
        msgtext = 'Headers: headers\n\nbodybodybody\n-- \nsig\n'
        self.mailer.username = u'f\u00f8\u00f8'  # double o slash
        self.mailer.password = u'\u00e9vil'  # e acute
        self.mailer.hostname = 'spamrelay'
        self.mailer.port = 31337
        self.mailer.send(fromaddr, toaddrs, msgtext)
        self.assertEqual(self.smtp.username, 'føø')
        self.assertEqual(self.smtp.password, 'évil')

    def test_send_auth_nonascii(self):
        fromaddr = 'me@example.com'
        toaddrs = ('you@example.com', 'him@example.com')
        msgtext = 'Headers: headers\n\nbodybodybody\n-- \nsig\n'
        self.mailer.username = b'f\xc3\xb8\xc3\xb8'  # double o slash
        self.mailer.password = b'\xc3\xa9vil'  # e acute
        self.mailer.hostname = 'spamrelay'
        self.mailer.port = 31337
        self.mailer.send(fromaddr, toaddrs, msgtext)
        self.assertEqual(self.smtp.username, b'f\xc3\xb8\xc3\xb8')
        self.assertEqual(self.smtp.password, b'\xc3\xa9vil')

    def test_send_failQuit(self):
        SMTP.fail_on_quit = True
        self.addCleanup(lambda: setattr(SMTP, 'fail_on_quit', False))

        fromaddr = 'me@example.com'
        toaddrs = ('you@example.com', 'him@example.com')
        msgtext = 'Headers: headers\n\nbodybodybody\n-- \nsig\n'
        self.mailer.send(fromaddr, toaddrs, msgtext)
        self.assertEqual(self.smtp.fromaddr, fromaddr)
        self.assertEqual(self.smtp.toaddrs, toaddrs)
        self.assertEqual(self.smtp.msgtext, msgtext)
        self.assertTrue(not self.smtp.quitted)
        self.assertTrue(self.smtp.closed)

    def test_vote_bad_connection(self):

        def hook(smtp):
            smtp.ehlo_code = 100
            smtp.helo = lambda: (100, "Nope")

        mailer = self._makeMailer(smtp_hook=hook)

        with self.assertRaisesRegex(RuntimeError,
                                    "Error sending HELO to the SMTP server"):
            mailer.vote(None, None, None)

    def test_abort_no_conn(self):
        self.assertIsNone(self.mailer.abort())

    def test_abort_fails_call_close(self):
        class Conn(object):
            closed = False

            def quit(self):
                raise SSLError()

            def close(self):
                self.closed = True

        conn = Conn()
        self.mailer.connection = conn
        self.mailer.abort()

        self.assertTrue(conn.closed)

    def test_send_no_tls_forced(self):
        class Conn(object):
            def has_extn(self, name):
                assert name == 'starttls'
                return False

        self.mailer.force_tls = True
        self.mailer.connection = Conn()

        with self.assertRaisesRegex(RuntimeError,
                                    'TLS is not available'):
            self.mailer.send(None, None, None)

    def test_send_no_esmtp_with_username(self):
        class Conn(object):
            does_esmtp = False

            def has_extn(self, *args):
                return False

        self.mailer.connection = Conn()
        self.mailer.username = 'user'
        with self.assertRaisesRegex(
                RuntimeError,
                "Mailhost does not support ESMTP but a username"):
            self.mailer.send(None, None, None)


class TestSMTPMailerWithNoEHLO(TestSMTPMailer):

    SMTPClass = SMTPWithNoEHLO

    def test_send_auth(self):
        self.skipTest(
            "This test requires ESMTP, which we're intentionally not enabling")

    test_send_auth_unicode = test_send_auth
    test_send_auth_nonascii = test_send_auth
