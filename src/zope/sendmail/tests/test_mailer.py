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
"""Tests for mailers.

$Id$
"""

import socket
import unittest
import smtplib
import logging
from StringIO import StringIO

from zope.interface.verify import verifyObject

from zope.sendmail.interfaces import (ISMTPMailer,
                                      MailerTemporaryFailureException,
                                      MailerPermanentFailureException)
from zope.sendmail.mailer import SMTPMailer
from zope.sendmail.tests.test_delivery import LoggerStub


class TestSMTPMailer(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.test_kwargs = {'fromaddr': 'me@example.com',
                          'toaddrs': ('you@example.com', 'him@example.com'),
                          'message': 'Headers: headers\n\nbodybodybody\n-- \nsig\n',
                          'message_id': 'dummy_file_name_XXX345YZ'}

    def setUp(self, port=None, exception=None, exception_args=None, 
              send_errors=None):
        global SMTP
        class SMTP(object):
            _exception = None
            _exception_args = None
            _send_errors = None

            def __init__(myself, h, p):
                myself.hostname = h
                myself.port = p
                self.smtp = myself
                if type(p) == type(u""):
                    raise socket.error("Int or String expected")
                if p == '0':
                    raise socket.error("Emulated connect() failure")

            def sendmail(self, f, t, m):
                self.fromaddr = f
                self.toaddrs = t
                self.msgtext = m
                if hasattr(self, '_exception'):
                    if self._exception and issubclass(self._exception, Exception):
                        if hasattr(self, '_exception_args') \
                            and type(self._exception_args) is tuple:
                                raise self._exception(*self._exception_args)
                        else:
                            raise self._exception('Crazy Arguments WANTED!')
                if self._send_errors:
                    return self._send_errors

            def login(self, username, password):
                self.username = username
                self.password = password

            def quit(self):
                self.quit = True

            def has_extn(self, ext):
                return True

            def ehlo(self):
                self.does_esmtp = True
                return (200, 'Hello, I am your stupid MTA mock')

            def starttls(self):
                pass


        if port is None:
            self.mailer = SMTPMailer()
        else:
            self.mailer = SMTPMailer(u'localhost', port)
        self.mailer.smtp = SMTP
        self.mailer.logger = LoggerStub()
        SMTP._exception = exception
        SMTP._exception_args = exception_args
        SMTP._send_errors = send_errors

    def test_interface(self):
        verifyObject(ISMTPMailer, self.mailer)

    def test_set_logger(self):
        # Do this with throw away instances...
        test_mailer = SMTPMailer()
        log_object = logging.getLogger('test_logger')
        test_mailer.set_logger(log_object)
        self.assertEquals(isinstance(test_mailer.logger, logging.Logger), True)

    def test_send(self):
        for run in (1,2):
            if run == 2:
                self.setUp(u'25')
            else:
                self.setUp()
            td = self.test_kwargs
            result = self.mailer.send(**self.test_kwargs)
            self.assertEquals(self.smtp.fromaddr, td['fromaddr'])
            self.assertEquals(self.smtp.toaddrs, td['toaddrs'])
            self.assertEquals(self.smtp.msgtext, td['message'])
            self.assert_(self.smtp.quit)
            self.assertEquals(result, ['you@example.com', 'him@example.com'])

    def test_mailer_no_connect(self):
        # set up test value to raise socket.error exception
        self.setUp('0')
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerTemporaryFailureException:
            pass
        self.assertEquals(self.mailer.logger.infos,
                         [('%s - SMTP server %s:%s - could not connect(), %s.',
                           ('dummy_file_name_XXX345YZ', u'localhost', '0',
                            'Emulated connect() failure'), {})])

    def test_mailer_smtp_data_error(self):
        self.setUp(exception=smtplib.SMTPDataError,
                   exception_args=(471, 'SMTP Data Error'))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerTemporaryFailureException:
            pass
        self.assertEquals(self.mailer.logger.warnings,
                [('%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s',
                  ('dummy_file_name_XXX345YZ', '471', 'SMTP Data Error',
                   'me@example.com', 'you@example.com, him@example.com'),
                  {})])


    def test_mailer_smtp_really_bad_error(self):
        self.setUp(exception=smtplib.SMTPResponseException,
                   exception_args=(550, 'SMTP Really Bad Error'))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerPermanentFailureException:
            pass
        self.assertEquals(self.mailer.logger.warnings,
                [('%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s',
                  ('dummy_file_name_XXX345YZ', '550', 'SMTP Really Bad Error',
                   'me@example.com', 'you@example.com, him@example.com'),
                  {})])

    def test_mailer_smtp_crazy_error(self):
        self.setUp(exception=smtplib.SMTPResponseException,
                   exception_args=(200, 'SMTP Crazy Error'))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerTemporaryFailureException:
            pass
        self.assertEquals(self.mailer.logger.warnings,
                [('%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s',
                  ('dummy_file_name_XXX345YZ', '200', 'SMTP Crazy Error',
                   'me@example.com', 'you@example.com, him@example.com'),
                  {})])

    def test_mailer_smtp_server_disconnected(self):
        self.setUp(exception=smtplib.SMTPServerDisconnected,
                   exception_args=('TCP RST - unexpected dissconnection',))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerTemporaryFailureException:
            pass
        self.assertEquals(self.mailer.logger.infos,
            [('%s - SMTP server %s:%s - %s',
              ('dummy_file_name_XXX345YZ',
               'localhost', '25',
               'TCP RST - unexpected dissconnection'),
              {})])

    def test_mailer_smtp_sender_refused(self):
        self.setUp(exception=smtplib.SMTPSenderRefused,
                   exception_args=(550, 'SMTP Sender Refused',
                                   'iamasender@bogus.com'))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerTemporaryFailureException:
            pass
        self.assertEquals(self.mailer.logger.warnings,
            [('%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s',
              ('dummy_file_name_XXX345YZ', '550', 'SMTP Sender Refused',
               'iamasender@bogus.com', 'you@example.com, him@example.com'),
              {})])

    def test_mailer_smtp_recipients_refused(self):
        self.setUp(exception=smtplib.SMTPRecipientsRefused,
         exception_args=({'you@example.com': (451, 'SMTP Recipient A Refused'),
                     'him@example.com': (450, 'SMTP Recipient B Refused')},))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerTemporaryFailureException:
            pass
        self.assertEquals(self.mailer.logger.warnings,
            [('%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s',
              ('dummy_file_name_XXX345YZ', '450', 'SMTP Recipient B Refused',
               'me@example.com', 'you@example.com, him@example.com'),
              {})])

    def test_mailer_smtp_exception(self):
        self.setUp(exception=smtplib.SMTPException,
                   exception_args=('SMTP Permanent Failure',))
        try:
            self.mailer.send(**self.test_kwargs)
        except MailerPermanentFailureException:
            pass
        self.assertEquals(self.mailer.logger.warnings,
            [('%s - SMTP failure: %s',
              ('dummy_file_name_XXX345YZ',
               'SMTP Permanent Failure'),
              {})])

    def test_mailer_partial_send_failure(self):
        self.setUp(send_errors={'you@example.com': (550, 'User unknown')})
        td = self.test_kwargs
        result = self.mailer.send(**self.test_kwargs)
        self.assertEquals(self.smtp.fromaddr, td['fromaddr'])
        self.assertEquals(self.smtp.toaddrs, td['toaddrs'])
        self.assertEquals(self.smtp.msgtext, td['message'])
        self.assert_(self.smtp.quit)
        self.assertEquals(self.mailer.logger.warnings,
            [('%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s',
              ('dummy_file_name_XXX345YZ', '550', 'User unknown',
               'me@example.com', 'you@example.com'),
              {})])
        self.assertEquals(result, ['him@example.com'])

    def test_send_auth(self):
        self.setUp()
        self.mailer.username = 'foo'
        self.mailer.password = 'evil'
        self.mailer.hostname = 'spamrelay'
        self.mailer.port = 31337
        td = self.test_kwargs
        result = self.mailer.send(**self.test_kwargs)
        self.assertEquals(self.smtp.username, 'foo')
        self.assertEquals(self.smtp.password, 'evil')
        self.assertEquals(self.smtp.hostname, 'spamrelay')
        self.assertEquals(self.smtp.port, '31337')
        self.assertEquals(self.smtp.fromaddr, td['fromaddr'])
        self.assertEquals(self.smtp.toaddrs, td['toaddrs'])
        self.assertEquals(self.smtp.msgtext, td['message'])
        self.assert_(self.smtp.quit)
        self.assertEquals(result, ['you@example.com', 'him@example.com'])


class TestSMTPMailerWithNoEHLO(TestSMTPMailer):

    def setUp(self, port=None, exception=None, exception_args=None,
             send_errors=None):

        class SMTPWithNoEHLO(SMTP):
            does_esmtp = False

            def __init__(myself, h, p):
                myself.hostname = h
                myself.port = p
                self.smtp = myself
                if type(p) == type(u""):
                    raise socket.error("Int or String expected")
                if p == '0':
                    raise socket.error("Emulated connect() failure")

            def helo(self):
                return (200, 'Hello, I am your stupid MTA mock')

            def ehlo(self):
                return (502, 'I don\'t understand EHLO')


        if port is None:
            self.mailer = SMTPMailer()
        else:
            self.mailer = SMTPMailer(u'localhost', port)
        self.mailer.smtp = SMTPWithNoEHLO
        self.mailer.logger = LoggerStub()
        SMTPWithNoEHLO._exception = exception
        SMTPWithNoEHLO._exception_args = exception_args
        SMTPWithNoEHLO._send_errors = send_errors

    def test_send_auth(self):
        # This test requires ESMTP, which we're intentionally not enabling
        # here, so pass.
        pass

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSMTPMailer))
    suite.addTest(unittest.makeSuite(TestSMTPMailerWithNoEHLO))
    return suite


if __name__ == '__main__':
    unittest.main()
