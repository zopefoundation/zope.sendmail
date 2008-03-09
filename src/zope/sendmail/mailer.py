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

"""These are classes which abstract different channels an email
message could be sent out by.

$Id$
"""
__docformat__ = 'restructuredtext'

import socket
import smtplib
import logging

from zope.interface import implements
from zope.interface.exceptions import DoesNotImplement
from zope.sendmail.interfaces import (ISMTPMailer, 
                                      MailerTemporaryFailureException,
                                      MailerPermanentFailureException)

SMTP_ERR_MEDIUM_LOG_MSG = '%s - SMTP Error: %s - %s, %s'
SMTP_ERR_SERVER_LOG_MSG = '%s - SMTP server %s:%s - %s'
SMTP_ERR_LOG_MSG = '%s - SMTP Error: %s - %s, Sender: %s, Rcpt: %s'

have_ssl = hasattr(socket, 'ssl')

class SMTPMailer(object):

    implements(ISMTPMailer)

    smtp = smtplib.SMTP

    def __init__(self, hostname='localhost', port=25,
                 username=None, password=None, no_tls=False, force_tls=False):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.force_tls = force_tls
        self.no_tls = no_tls
        self.logger = None

    def set_logger(self, logger):
        if not isinstance(logger, logging.Logger):
            raise DoesNotImplement('Invalid logger given')
        self.logger = logger

    def _log(self, log_level, *args):
        if self.logger is None:
            return
        # This is not elegant, but it can be fixed later
        if log_level == 'debug':
            self.logger.debug(*args)
        elif log_level =='info':
            self.logger.info(*args)
        elif log_level =='error':
            self.logger.error(*args)
        elif log_level =='warning':
            self.logger.warning(*args)

    def _handle_smtp_error(self,
                           smtp_code,
                           smtp_error,
                           fromaddr,
                           toaddrs,
                           message_id):
        """Process results of an SMTP error
           returns True to indicate break needed"""
        if 500 <= smtp_code <= 599:
            # permanent error, ditch the message
            self._log('warning',
                SMTP_ERR_LOG_MSG,
                message_id,
                str(smtp_code),
                smtp_error,
                fromaddr,
                ", ".join(toaddrs))
            raise MailerPermanentFailureException()
        elif 400 <= smtp_code <= 499:
            # Temporary error
            self._log('warning',
                SMTP_ERR_LOG_MSG,
                message_id,
                str(smtp_code),
                smtp_error,
                fromaddr,
                ", ".join(toaddrs))
            # temporary failure, go and sleep for 
            # retry_interval
            raise MailerTemporaryFailureException()
        else:
            self._log('warning',
                SMTP_ERR_LOG_MSG,
                message_id,
                str(smtp_code),
                smtp_error,
                fromaddr,
                ", ".join(toaddrs))
            raise MailerTemporaryFailureException()

    def send(self, fromaddr, toaddrs, message, message_id):
        try:
            connection = self.smtp(self.hostname, str(self.port))
        except socket.error, e:
            self._log('info',
                "%s - SMTP server %s:%s - could not connect(),"
                " %s.",
                message_id,
                self.hostname,
                str(self.port),
                str(e),)
            # temporary failure, go and sleep for 
            # retry_interval
            raise MailerTemporaryFailureException()

        # send EHLO
        code, response = connection.ehlo()
        if code < 200 or code >= 300:
            code, response = connection.helo()
            if code < 200 or code >= 300:
                self._log('warning',
                          SMTP_ERR_MEDIUM_LOG_MSG,
                          message_id,
                          code,
                          str(response),
                          'error sending HELO')
                raise MailerTemporaryFailureException()

        # encryption support
        have_tls = connection.has_extn('starttls')
        if not have_tls and self.force_tls:
            error_str = 'TLS is not available but TLS is required'
            self._log('warning',
                      SMTP_ERR_SERVER_LOG_MSG,
                      message_id,
                      self.hostname,
                      self.port,
                      error_str)
            raise MaileriTemporaryFailure(error_str)

        if have_tls and have_ssl and not self.no_tls:
            connection.starttls()
            connection.ehlo()

        if connection.does_esmtp:
            if self.username is not None and self.password is not None:
                connection.login(self.username, self.password)
        elif self.username:
            error_str = 'Mailhost does not support ESMTP but a username ' \
                        'is configured'
            self._log('warning',
                      SMTP_ERR_SERVER_LOG_MSG,
                      message_id,
                      self.hostname,
                      self.port,
                      error_str)
            raise MailerTemporaryFailureException(error_str)

        try:
            send_errors = connection.sendmail(fromaddr, toaddrs, message)
        except smtplib.SMTPSenderRefused, e:
            self._log('warning',
                SMTP_ERR_LOG_MSG,
                message_id,
                str(e.smtp_code),
                e.smtp_error,
                e.sender,
                ", ".join(toaddrs))
            # temporary failure, go and sleep for 
            # retry_interval
            raise MailerTemporaryFailureException()
        except (smtplib.SMTPAuthenticationError,
                smtplib.SMTPConnectError,
                smtplib.SMTPDataError,
                smtplib.SMTPHeloError,
                smtplib.SMTPResponseException), e:
            self._handle_smtp_error(e.smtp_code,
                                      e.smtp_error,
                                      fromaddr,
                                      toaddrs,
                                      message_id)
        except smtplib.SMTPServerDisconnected, e:
            self._log('info',
                SMTP_ERR_SERVER_LOG_MSG,
                message_id,
                self.hostname,
                str(self.port),
                str(e))
            # temporary failure, go and sleep for 
            # retry_interval
            raise MailerTemporaryFailureException()
        except smtplib.SMTPRecipientsRefused, e:
            # This exception is raised because no recipients
            # were acceptable - lets take the most common error
            # code and proceed with that
            freq = {}
            for result in e.recipients.values():
                if freq.has_key(result):
                    freq[result] += 1
                else:
                    freq[result] = 1
            max_ = 0
            for result in freq.keys():
                if freq[result] > max_:
                    most_common = result
                    max_ = freq[result]
            (smtp_code, smtp_error) = most_common
            self._handle_smtp_error(smtp_code,
                                      smtp_error,
                                      fromaddr,
                                      toaddrs,
                                      message_id)
        except smtplib.SMTPException, e:
            # Permanent SMTP failure
            self._log('warning',
                '%s - SMTP failure: %s',
                message_id,
                str(e))
            raise MailerPermanentFailureException()

        connection.quit()

        # Log ANY errors
        if send_errors is not None:
            sentaddrs = [x for x in toaddrs
                         if x not in send_errors.keys()]
            for address in send_errors.keys():
                self._log('warning',
                    SMTP_ERR_LOG_MSG,
                    message_id,
                    str(send_errors[address][0]),
                    send_errors[address][1],
                    fromaddr,
                    address)
        else:
            sentaddrs = list(toaddrs)

        return sentaddrs
