#!/usr/bin/env python
#
# Copyright 2010 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#

"""client module tests."""



import logging
import sys


import mox
import stubout

from google.apputils import app
from google.apputils import basetest

from simian import auth
from simian.client import client

if hasattr(mox.MockAnything, '__str__'): del(mox.MockAnything.__str__)
logging.basicConfig(filename='/dev/null')


class GenericException(Exception):
  """A generic exception that can be used for mocks."""
  pass


class ClientModuleTest(mox.MoxTestBase):
  """Test the client module."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testConstants(self):
    for a in [
        'SERVER_HOSTNAME', 'SERVER_PORT', 'AUTH_DOMAIN',
        'CLIENT_SSL_PATH', 'SEEK_SET', 'SEEK_CUR', 'SEEK_END',
        'DEBUG', 'URL_UPLOADPKG']:
      self.assertTrue(hasattr(client, a))


class MultiBodyConnectionTest(mox.MoxTestBase):
  """Test MultiBodyConnection class."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()
    self.mbc = client.MultiBodyConnection()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testSetProgressCallback(self):
    """Test SetProgressCallback()."""

    fn = lambda x: 1

    self.mox.ReplayAll()
    self.assertFalse(hasattr(self.mbc, '_progress_callback'))
    self.mbc.SetProgressCallback(fn)
    self.assertEqual(self.mbc._progress_callback, fn)
    self.assertRaises(
        client.Error,
        self.mbc.SetProgressCallback, 1)
    self.mox.VerifyAll()

  def testProgressCallback(self):
    """Test _ProgressCallback()."""

    callback = self.mox.CreateMockAnything()
    callback(1, 2).AndReturn(None)

    self.mox.ReplayAll()
    self.mbc._ProgressCallback(1, 2)
    self.mbc._progress_callback = callback
    self.mbc._ProgressCallback(1, 2)
    self.mox.VerifyAll()

  def testRequest(self):
    """Test request()."""
    f_body = 'x' * 10000
    f = self.mox.CreateMockAnything()
    method = 'GET'
    url = '/foo'
    body = ['hello', f]
    content_length = len(body[0]) + len(f_body)
    headers = {
        'Content-Length': content_length,
    }

    self.mbc._is_https = False

    mock_request = self.mox.CreateMockAnything()
    self.stubs.Set(client.httplib.HTTPConnection, 'request', mock_request)
    self.mbc.send = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(self.mbc, '_ProgressCallback')

    f.tell().AndReturn(0)
    f.seek(0, client.SEEK_END).AndReturn(None)
    f.tell().AndReturn(len(f_body))
    f.seek(0, client.SEEK_SET).AndReturn(None)

    mock_request(
        self.mbc,
        method, url, headers=headers).AndReturn(None)
    self.mbc._ProgressCallback(0, content_length)
    self.mbc.send(body[0]).AndReturn(None)
    self.mbc._ProgressCallback(len(body[0]), content_length).AndReturn(None)
    f.read(8192).AndReturn(f_body[:8192])
    self.mbc.send(f_body[:8192]).AndReturn(None)
    self.mbc._ProgressCallback(
        len(body[0]) + 8192, content_length).AndReturn(None)
    f.read(8192).AndReturn(f_body[8192:])
    self.mbc.send(f_body[8192:]).AndReturn(None)
    self.mbc._ProgressCallback(
        len(body[0]) + len(f_body), content_length).AndReturn(None)
    f.read(8192).AndReturn('')
    self.mbc._ProgressCallback(
        len(body[0]) + len(f_body), content_length).AndReturn(None)

    self.mox.ReplayAll()
    self.mbc.request(method, url, body=body)
    self.mox.VerifyAll()


class HTTPSMultiBodyConnectionTest(mox.MoxTestBase):
  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()
    self.hostname = 'foohost'
    self.mbc = client.HTTPSMultiBodyConnection(self.hostname)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testParentClassRequestAssumption(self):
    """Test assumptions of parent class request()."""
    method = 'GET'
    url = '/foo'
    body = None
    headers = {}
    mock_fn = self.mox.CreateMockAnything()
    self.stubs.Set(
        client.httplib.HTTPConnection, '_send_request', mock_fn)
    mock_fn(method, url, body, headers).AndReturn(-1)
    self.mox.ReplayAll()
    c = client.httplib.HTTPConnection(self.hostname)
    self.assertEqual(None, c.request(method, url))
    self.mox.VerifyAll()

  def testParentClassSendRequestAssumption(self):
    """Test assumptions of parent class _send_request()."""
    method = 'GET'
    url = '/foo'
    body1 = None
    body2 = 'howdy'
    headers = {'foo': 'bar'}

    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'putrequest')
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'putheader')
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'endheaders')
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'send')

    # with a None body supplied, send() is never called.  on >=2.7
    # endheaders is still called with the body contents, even if they
    # are None.
    client.httplib.HTTPConnection.putrequest(method, url).AndReturn(None)
    client.httplib.HTTPConnection.putheader(
        'foo', headers['foo']).AndReturn(None)
    if sys.version_info[0] >= 2 and sys.version_info[1] >= 7:
      client.httplib.HTTPConnection.endheaders(body1).AndReturn(None)
    else:
      client.httplib.HTTPConnection.endheaders().AndReturn(None)

    # with a body supplied, send() is called inside _send_request() on
    # httplib < 2.6. in >=2.7 endheaders() sends the body and headers
    # all at once.
    client.httplib.HTTPConnection.putrequest(method, url).AndReturn(None)
    client.httplib.HTTPConnection.putheader(
        'Content-Length', str(len(body2)))
    client.httplib.HTTPConnection.putheader(
        'foo', headers['foo']).AndReturn(None)
    if sys.version_info[0] >= 2 and sys.version_info[1] >= 7:
      client.httplib.HTTPConnection.endheaders(body2).AndReturn(None)
    else:
      client.httplib.HTTPConnection.endheaders().AndReturn(None)
      client.httplib.HTTPConnection.send(body2).AndReturn(None)

    self.mox.ReplayAll()
    c = client.httplib.HTTPConnection(self.hostname)
    c._send_request(method, url, body1, headers)
    c._send_request(method, url, body2, headers)
    self.mox.VerifyAll()

  def testDirectSendTypes(self):
    """Test the DIRECT_SEND_TYPES constant for sane values."""
    self.assertTrue(type(self.mbc.DIRECT_SEND_TYPES) is list)

  def testRequestSimple(self):
    """Test request with one body element."""
    method = 'GET'
    url = '/foo'
    body = 'hello'
    headers = {
        'Content-Length': len(body),
        'Host': self.hostname,
    }
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'request')
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'send')
    client.httplib.HTTPConnection.request(
        self.mbc,
        method, url, headers=headers).AndReturn(None)
    client.httplib.HTTPConnection.send(body).AndReturn(None)
    self.mox.ReplayAll()
    self.mbc.request(method, url, body=body)
    self.mox.VerifyAll()

  def testRequestMultiString(self):
    """Test request() with multiple body string elements."""
    method = 'GET'
    url = '/foo'
    body = ['hello', 'there']
    headers = {
        'Content-Length': sum(map(len, body)),
        'Host': self.hostname,
    }
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'request')
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'send')
    client.httplib.HTTPConnection.request(
        self.mbc,
        method, url, headers=headers).AndReturn(None)
    for s in body:
      client.httplib.HTTPConnection.send(s).AndReturn(None)
    self.mox.ReplayAll()
    self.mbc.request(method, url, body=body)
    self.mox.VerifyAll()

  def testRequestMultiMixed(self):
    """Test request() with multiple mixed body elements."""
    f_body = 'there'
    f = self.mox.CreateMockAnything()
    method = 'GET'
    url = '/foo'
    body = ['hello', f]
    content_length = len(body[0]) + len(f_body)
    headers = {
        'Content-Length': content_length,
        'Host': self.hostname,
    }

    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'request')
    self.mox.StubOutWithMock(client.httplib.HTTPConnection, 'send')

    f.tell().AndReturn(0)
    f.seek(0, client.SEEK_END).AndReturn(None)
    f.tell().AndReturn(len(f_body))
    f.seek(0, client.SEEK_SET).AndReturn(None)

    client.httplib.HTTPConnection.request(
        self.mbc,
        method, url, headers=headers).AndReturn(None)
    client.httplib.HTTPConnection.send(body[0]).AndReturn(None)
    f.read(8192).AndReturn(f_body)
    client.httplib.HTTPConnection.send(f_body).AndReturn(None)
    f.read(8192).AndReturn('')

    self.mox.ReplayAll()
    self.mbc.request(method, url, body=body)
    self.mox.VerifyAll()

  def testSetCACertChain(self):
    """Test SetCACertChain()."""
    self.mbc.SetCACertChain('foo')
    self.assertEqual(self.mbc._ca_cert_chain, 'foo')

  def testIsValidCert(self):
    """Test _IsValidCert()."""
    store = self.mox.CreateMockAnything()

    self.mox.ReplayAll()
    self.assertEqual(1, self.mbc._IsValidCert(1, store))
    self.mox.VerifyAll()

  def testIsValidCertOkZero(self):
    """Test _IsValidCert()."""
    store = self.mox.CreateMockAnything()
    store.get_current_cert().AndReturn(store)
    store.get_subject().AndReturn(store)
    store.__str__().AndReturn('valid')

    self.mox.ReplayAll()
    self.assertEqual(0, self.mbc._IsValidCert(0, store))
    self.mox.VerifyAll()

  def testLoadCACertChain(self):
    """Test _LoadCACertChain()."""
    ctx = self.mox.CreateMockAnything()
    tf = self.mox.CreateMockAnything()
    cert_chain = 'cert chain la la ..'

    self.mbc._ca_cert_chain = cert_chain
    self.mox.StubOutWithMock(client.tempfile, 'NamedTemporaryFile')

    client.tempfile.NamedTemporaryFile().AndReturn(tf)
    tf.write(cert_chain).AndReturn(None)
    tf.flush().AndReturn(None)
    tf.name = '/tmp/somefilename'

    ctx.load_verify_locations(cafile=tf.name).AndReturn(1)
    ctx.set_verify(
        client.SSL.verify_peer | client.SSL.verify_fail_if_no_peer_cert,
        depth=9,
        callback=self.mbc._IsValidCert).AndReturn(None)
    tf.close()

    self.mox.ReplayAll()
    self.mbc._LoadCACertChain(ctx)
    self.mox.VerifyAll()

  def testLoadCACertChainWhenLoadError(self):
    """Test _LoadCACertChain()."""
    ctx = self.mox.CreateMockAnything()
    tf = self.mox.CreateMockAnything()
    cert_chain = 'cert chain la la ..'

    self.mbc._ca_cert_chain = cert_chain
    self.mox.StubOutWithMock(client.tempfile, 'NamedTemporaryFile')

    client.tempfile.NamedTemporaryFile().AndReturn(tf)
    tf.write(cert_chain).AndReturn(None)
    tf.flush().AndReturn(None)
    tf.name = '/tmp/somefilename'

    ctx.load_verify_locations(cafile=tf.name).AndReturn(-1)
    tf.close()

    self.mox.ReplayAll()
    self.assertRaises(
        client.SimianClientError, self.mbc._LoadCACertChain, ctx)
    self.mox.VerifyAll()

  def testLoadCACertChainWhenNone(self):
    """Test _LoadCACertChain()."""
    ctx = self.mox.CreateMockAnything()

    self.mox.ReplayAll()
    self.assertRaises(
        client.SimianClientError, self.mbc._LoadCACertChain, ctx)
    self.mox.VerifyAll()

  def testConnect(self):
    """Test connect()."""
    context = self.mox.CreateMockAnything()
    conn = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(client, 'SSL')
    self.mox.StubOutWithMock(client.SSL, 'Context')
    self.mox.StubOutWithMock(client.SSL, 'Connection')
    self.mox.StubOutWithMock(self.mbc, '_LoadCACertChain')

    self.mbc._ca_cert_chain = 'cert chain foo'

    client.SSL.Context(client._SSL_VERSION).AndReturn(context)
    if client._CIPHER_LIST:
      context.set_cipher_list(client._CIPHER_LIST).AndReturn(None)

    self.mbc._LoadCACertChain(context).AndReturn(None)

    def __connect(address):  # pylint: disable=g-bad-name
      self.assertEqual(address, (self.mbc.host, self.mbc.port))
      return None

    client.SSL.Connection(context).AndReturn(conn)
    conn.connect = __connect

    self.mox.ReplayAll()
    self.mbc.connect()
    self.assertEqual(self.mbc.sock, conn)
    self.mox.VerifyAll()

  def testConnectWhenNoCACertChain(self):
    """Test connect()."""
    context = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(client, 'SSL')
    self.mox.StubOutWithMock(client.SSL, 'Context')

    client.SSL.Context(client._SSL_VERSION).AndReturn(context)
    if client._CIPHER_LIST:
      context.set_cipher_list(client._CIPHER_LIST).AndReturn(None)

    self.mox.ReplayAll()
    self.assertRaises(client.SimianClientError, self.mbc.connect)
    self.mox.VerifyAll()


class HttpsClientTest(mox.MoxTestBase):
  """Test HttpsClient class."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()
    self.hostname = 'hostname'
    self.port = None
    self.client = client.HttpsClient(self.hostname)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testInit(self):
    """Test __init__()."""
    mock_lh = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(self.client, '_LoadHost')
    self.stubs.Set(client.HttpsClient, '_LoadHost', mock_lh)
    mock_lh(self.hostname, None, None).AndReturn(None)
    self.mox.ReplayAll()
    i = client.HttpsClient(self.hostname)
    self.assertEqual(i._progress_callback, None)
    self.assertEqual(i._ca_cert_chain, None)
    self.mox.VerifyAll()

  def testLoadHost(self):
    """Test _LoadHost()."""

    self.mox.ReplayAll()

    self.client._LoadHost('host')
    self.assertEqual(self.client.hostname, 'host')
    self.assertEqual(self.client.port, None)
    self.assertTrue(self.client.use_https)

    self.client._LoadHost('host', 12345)
    self.assertEqual(self.client.hostname, 'host')
    self.assertEqual(self.client.port, 12345)
    self.assertTrue(self.client.use_https)

    self.client._LoadHost('https://tsoh:54321')
    self.assertEqual(self.client.hostname, 'tsoh')
    self.assertEqual(self.client.port, 54321)
    self.assertTrue(self.client.use_https)

    self.client._LoadHost('https://tsoh:54321', 9999)
    self.assertEqual(self.client.hostname, 'tsoh')
    self.assertEqual(self.client.port, 54321)
    self.assertTrue(self.client.use_https)

    self.client._LoadHost('foo.bar:5555')
    self.assertEqual(self.client.hostname, 'foo.bar')
    self.assertEqual(self.client.port, 5555)
    self.assertTrue(self.client.use_https)

    self.client._LoadHost('http://nonsecurehost')
    self.assertEqual(self.client.hostname, 'nonsecurehost')
    self.assertEqual(self.client.port, None)
    self.assertFalse(self.client.use_https)

    self.client._LoadHost('https://dev1.latest.%s' % client.SERVER_HOSTNAME)
    self.assertEqual(
        self.client.hostname, 'dev1.latest.%s' % client.SERVER_HOSTNAME)
    self.assertEqual(self.client.port, None)
    self.assertTrue(self.client.use_https)

    self.client._LoadHost('http://dev2.latest.%s' % client.SERVER_HOSTNAME)
    self.assertEqual(
        self.client.hostname, 'dev2.latest.%s' % client.SERVER_HOSTNAME)
    self.assertEqual(self.client.port, None)
    self.assertFalse(self.client.use_https)

    self.client._LoadHost('http://nonsecurehost:1234')
    self.assertEqual(self.client.hostname, 'nonsecurehost')
    self.assertEqual(self.client.port, 1234)
    self.assertFalse(self.client.use_https)

    self.client._LoadHost(u'http://unicodehost')
    self.assertTrue(type(self.client.hostname) is str)
    self.assertEqual(self.client.hostname, 'unicodehost')

    self.client._LoadHost(u'http://unicodehost', proxy=u'http://evilproxy:9')
    self.assertTrue(type(self.client.hostname) is str)
    self.assertEqual(self.client.hostname, 'unicodehost')
    self.assertTrue(type(self.client.proxy_hostname) is str)
    self.assertEqual(self.client.proxy_hostname, 'evilproxy')
    self.assertEqual(self.client.proxy_port, 9)
    self.assertFalse(self.client.proxy_use_https)

    self.client._LoadHost(u'http://unicodehost', proxy=u'https://evilprxssl:8')
    self.assertTrue(type(self.client.hostname) is str)
    self.assertEqual(self.client.hostname, 'unicodehost')
    self.assertTrue(type(self.client.proxy_hostname) is str)
    self.assertEqual(self.client.proxy_hostname, 'evilprxssl')
    self.assertEqual(self.client.proxy_port, 8)
    self.assertTrue(self.client.proxy_use_https)

    self.mox.VerifyAll()

  def testSetCACertChain(self):
    """Test SetCACertChain()."""
    self.client.SetCACertChain('foo')
    self.assertEqual(self.client._ca_cert_chain, 'foo')

  def _TestConnect(self, test_client, hostname, port):
    """Test _Connect()."""
    m = self.mox.CreateMockAnything()
    # we stub this out weirdly because the parent class isn't an object,
    # it's an oldschool Python class.
    test_client._ca_cert_chain = 'cert chain'
    use_https = (
        (not test_client.proxy_hostname and test_client.use_https) or
        (test_client.proxy_hostname and test_client.proxy_use_https))
    if use_https:
      self.stubs.Set(client, 'HTTPSMultiBodyConnection', m)
    else:
      self.stubs.Set(client, 'HTTPMultiBodyConnection', m)
    m(hostname, port).AndReturn(m)
    if use_https:
      m.SetCACertChain('cert chain').AndReturn(None)
    m.connect().AndReturn(None)
    self.mox.ReplayAll()
    test_client._Connect()
    self.mox.VerifyAll()

  def testConnect(self):
    self._TestConnect(self.client, self.hostname, self.port)

  def testConnectWithProxy(self):
    test_client = client.HttpsClient(self.hostname, proxy='proxyhost:123')
    self._TestConnect(test_client, 'proxyhost', 123)

  def testGetResponseNoFile(self):
    """Test _GetResponse() storing body directly into response obj."""
    headers = {'foo': 1}
    status = 200
    body = 'howdy sir'
    body_len = len(body)

    conn = self.mox.CreateMockAnything()
    response = self.mox.CreateMockAnything()
    conn.getresponse().AndReturn(response)
    response.getheaders().AndReturn(headers)
    response.status = status
    response.read().AndReturn(body)

    self.mox.ReplayAll()
    r = self.client._GetResponse(conn)
    self.assertEqual(r.headers, headers)
    self.assertEqual(r.status, status)
    self.assertEqual(r.body, body)
    self.assertEqual(r.body_len, body_len)
    self.mox.VerifyAll()

  def testGetResponseOutputFile(self):
    """Test _GetResponse() sending the body to output_file."""
    headers = {'foo': 1}
    status = 200
    body = 'howdy sir'
    body_len = len(body)

    conn = self.mox.CreateMockAnything()
    response = self.mox.CreateMockAnything()
    output_file = self.mox.CreateMockAnything()

    conn.getresponse().AndReturn(response)
    response.getheaders().AndReturn(headers)
    response.status = status
    response.read(8192).AndReturn(body)
    output_file.write(body).AndReturn(None)
    response.read(8192).AndReturn(None)

    self.mox.ReplayAll()
    r = self.client._GetResponse(conn, output_file=output_file)
    self.assertEqual(r.headers, headers)
    self.assertEqual(r.status, status)
    self.assertEqual(r.body, None)
    self.assertEqual(r.body_len, body_len)
    self.mox.VerifyAll()

  def testRequest(self):
    """Test _Request()."""
    method = 'zGET'
    url = u'/url'
    body1 = {'encodeme': 1}
    body1_encoded = 'encodeme:: 1'
    body2 = 'leave this alone'
    headers = {'User-Agent': 'gzip'}

    conn = self.mox.CreateMockAnything()

    self.stubs.Set(
        client, 'urllib', self.mox.CreateMockAnything(client.urllib))
    client.urllib.urlencode(body1).AndReturn(body1_encoded)
    conn.request(
        method, str(url), body=body1_encoded, headers=headers).AndReturn(None)
    conn.request(
        method, str(url), body=body2, headers=headers).AndReturn(None)

    self.mox.ReplayAll()
    self.client._Request(method, conn, url, body1, headers)
    self.client._Request(method, conn, url, body2, headers)
    self.mox.VerifyAll()

  def _TestDoRequestResponse(self, test_client, url, req_url):
    """Test _DoRequestResponse()."""
    method = 'zomg'
    conn = self.mox.CreateMockAnything()
    body = 'body'
    headers = 'headers'
    output_file = None
    response = self.mox.CreateMockAnything()
    response.status = 200
    proxy_use_https = test_client.proxy_use_https

    self.mox.StubOutWithMock(test_client, '_Connect')
    self.mox.StubOutWithMock(test_client, '_Request')
    self.mox.StubOutWithMock(test_client, '_GetResponse')

    test_client._Connect().AndReturn(conn)
    test_client._Request(
        method, conn, req_url, body=body, headers=headers).AndReturn(None)
    test_client._GetResponse(
        conn, output_file=output_file).AndReturn(response)

    test_client._Connect().AndRaise(client.httplib.HTTPException)

    self.mox.ReplayAll()
    self.assertEqual(
        response,
        test_client._DoRequestResponse(
            method, url, body, headers, output_file))
    self.assertRaises(
        client.HTTPError,
        test_client._DoRequestResponse,
        method, url, body, headers, output_file)
    self.mox.VerifyAll()

  def testDoRequestResponse(self):
    self._TestDoRequestResponse(self.client, '/url', '/url')

  def testDoHttpRequestResponseWithHttpProxy(self):
    """Test a https request via a http proxy."""
    test_client = client.HttpsClient(
        'http://%s' % self.hostname, proxy='proxyhost:123')
    req_url = 'http://' + self.hostname + '/url'
    self._TestDoRequestResponse(test_client, '/url', req_url)

  def testDoHttpsRequestResponseWithHttpProxy(self):
    """Test a https request via a http proxy."""
    # default is https
    test_client = client.HttpsClient(
        self.hostname, proxy='http://proxyhost:124')
    req_url = 'https://' + self.hostname + '/url'
    self._TestDoRequestResponse(test_client, '/url', req_url)

  def testDoHttpRequestResponseWithHttpsProxy(self):
    """Test a https request via a http proxy."""
    test_client = client.HttpsClient(
        'http://%s' % self.hostname, proxy='https://proxyhost:125')
    req_url = 'http://' + self.hostname + '/url'
    self._TestDoRequestResponse(test_client, '/url', req_url)

  def testDoHttpsRequestResponseWithHttpsProxy(self):
    """Test a https request via a http proxy."""
    # default is https
    test_client = client.HttpsClient(
        self.hostname, proxy='https://proxyhost:126')
    req_url = 'https://' + self.hostname + '/url'
    self._TestDoRequestResponse(test_client, '/url', req_url)

  def testDoWithInvalidMethod(self):
    """Test Do() with invalid method."""
    self.assertRaises(
        NotImplementedError,
        self.client.Do, 'badmethod', '/url')

  def testDo(self):
    """Test Do() with correct arguments and no output_filename."""
    method = 'GET'
    url = 'url'
    body = None
    headers = None
    output_file = None
    output_filename = None

    self.mox.StubOutWithMock(client.time, 'sleep')
    self.mox.StubOutWithMock(self.client, '_DoRequestResponse')
    # HTTP 500 should retry.
    mock_response_fail = self.mox.CreateMockAnything()
    mock_response_fail.status = 500
    client.time.sleep(0).AndReturn(None)
    self.client._DoRequestResponse(
        method, url, body=body, headers={}, output_file=output_file).AndReturn(
            mock_response_fail)
    # HTTP 200 should succeed.
    mock_response = self.mox.CreateMockAnything()
    mock_response.status = 200
    client.time.sleep(5).AndReturn(None)
    self.client._DoRequestResponse(
        method, url, body=body, headers={}, output_file=output_file).AndReturn(
            mock_response)
    self.mox.ReplayAll()
    self.client.Do(method, url, body, headers, output_filename)
    self.mox.VerifyAll()

  def testDoWithRetryHttp500(self):
    """Test Do() with a HTTP 500, thus a retry."""
    method = 'GET'
    url = 'url'
    body = None
    headers = None
    output_file = None
    output_filename = None

    self.mox.StubOutWithMock(client.time, 'sleep')
    mock_response = self.mox.CreateMockAnything()
    mock_response.status = 500
    self.mox.StubOutWithMock(self.client, '_DoRequestResponse')
    for i in xrange(0, client.DEFAULT_HTTP_ATTEMPTS):
      client.time.sleep(i * 5).AndReturn(None)
      self.client._DoRequestResponse(
          method, url, body=body, headers={},
          output_file=output_file).AndReturn(mock_response)

    self.mox.ReplayAll()
    r = self.client.Do(method, url, body, headers, output_filename)
    self.mox.VerifyAll()

  def testDoWithRetryHttpError(self):
    """Test Do() with a HTTP 500, thus a retry, but ending with HTTPError."""
    method = 'GET'
    url = 'url'
    body = None
    headers = None
    output_file = None
    output_filename = None

    self.mox.StubOutWithMock(client.time, 'sleep')
    self.mox.StubOutWithMock(self.client, '_DoRequestResponse')
    for i in xrange(0, client.DEFAULT_HTTP_ATTEMPTS):
      client.time.sleep(i * 5).AndReturn(None)
      self.client._DoRequestResponse(
          method, url, body=body, headers={},
          output_file=output_file).AndRaise(client.HTTPError)

    self.mox.ReplayAll()
    self.assertRaises(
        client.HTTPError,
        self.client.Do,
        method, url, body, headers, output_filename)
    self.mox.VerifyAll()

  def testDoWithOutputFilename(self):
    """Test Do() where an output_filename is supplied."""
    method = 'GET'
    url = 'url'
    body = None
    headers = {}
    mock_open = self.mox.CreateMockAnything()
    output_file = self.mox.CreateMockAnything()
    output_filename = '/tmpfile'

    mock_response = self.mox.CreateMockAnything()
    mock_response.status = 200
    self.mox.StubOutWithMock(self.client, '_DoRequestResponse')
    mock_open(output_filename, 'w').AndReturn(output_file)
    self.client._DoRequestResponse(
        method, url, body=body, headers={}, output_file=output_file).AndReturn(
            mock_response)
    output_file.close().AndReturn(None)
    self.mox.ReplayAll()
    self.client.Do(
        method, url, body, headers, output_filename, _open=mock_open)
    self.mox.VerifyAll()

  def testDoWithProxy(self):
    """Test Do() with a proxy specified."""
    method = 'GET'
    url = 'url'
    proxy = 'proxyhost:123'

    # Working case.
    mock_response = self.mox.CreateMockAnything()
    mock_response.status = 200
    test_client = client.HttpsClient(self.hostname, proxy=proxy)
    self.mox.StubOutWithMock(test_client, '_DoRequestResponse')
    test_client._DoRequestResponse(
        method, url, body=None, headers={}, output_file=None).AndReturn(
            mock_response)
    self.mox.ReplayAll()
    test_client.Do(method, url)
    self.mox.VerifyAll()
    # No port case.
    proxy = 'proxyhost'
    self.assertRaises(
        client.Error,
        client.HttpsClient, self.hostname, proxy=proxy)
    # Bad port case.
    proxy = 'proxyhost:alpha'
    self.assertRaises(
        client.Error,
        client.HttpsClient, self.hostname, proxy=proxy)


class HttpsAuthClientTest(mox.MoxTestBase):
  """Test HttpsAuthClient."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()
    self.hostname = 'hostname'
    self.port = None
    self.client = client.HttpsAuthClient(self.hostname)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testInit(self):
    """Test __init__()."""
    self.mox.StubOutWithMock(client.HttpsAuthClient, '_LoadRootCertChain')
    client.HttpsAuthClient._LoadRootCertChain().AndReturn(None)
    self.mox.ReplayAll()
    c = client.HttpsAuthClient(self.hostname)
    self.assertEqual(c._auth1, None)
    self.assertEqual(c._cookie_token, None)
    self.mox.VerifyAll()


  def testPlatformSetup(self):
    """Test PlatformSetup()."""
    self.mox.StubOutWithMock(client.platform, 'system')
    client.platform.system().AndReturn('Darwin')
    client.platform.system().AndReturn('other')

    self.mox.ReplayAll()
    self.client.facter_cache_path = 'x'
    self.client._PlatformSetup()
    self.assertEqual(
        self.client.facter_cache_path, self.client.FACTER_CACHE_OSX_PATH)
    self.client.facter_cache_path = 'x'
    self.client._PlatformSetup()
    self.assertEqual(
        self.client.facter_cache_path, self.client.FACTER_CACHE_DEFAULT_PATH)
    self.mox.VerifyAll()

  def testGetFacter(self):
    """Test GetFacter()."""
    st_dt = client.datetime.datetime.now()
    self.client.facter_cache_path = '/x'

    mock_open = self.mox.CreateMockAnything()
    mock_file = self.mox.CreateMockAnything()
    stat = self.mox.CreateMockAnything()
    mock_dt = self.mox.CreateMockAnything()

    self.stubs.Set(client.datetime, 'datetime', mock_dt)
    self.mox.StubOutWithMock(client.os, 'stat')
    self.mox.StubOutWithMock(client.os, 'geteuid')

    self.mox.StubOutWithMock(client.os.path, 'isfile')
    client.os.path.isfile(self.client.facter_cache_path).AndReturn(True)

    stat.st_uid = 0
    stat.st_mtime = int(st_dt.strftime('%s'))
    facter = {'foo': 'bar', 'one': '1'}
    lines = [
        'foo => bar',
        'one => 1',
        'I_am_invalid',
    ]

    client.os.stat(self.client.facter_cache_path).AndReturn(stat)
    client.os.geteuid().AndReturn(0)
    client.os.geteuid().AndReturn(0)
    mock_dt.fromtimestamp(stat.st_mtime).AndReturn(st_dt)

    mock_open(self.client.facter_cache_path, 'r').AndReturn(mock_file)
    for line in lines:
      mock_file.readline().AndReturn(line)
    mock_file.readline().AndReturn(None)
    mock_file.close().AndReturn(None)

    self.mox.ReplayAll()
    self.assertEqual(facter, self.client.GetFacter(open_fn=mock_open))
    self.mox.VerifyAll()

  def testGetFacterWhenInsecureFileForRoot(self):
    """Test GetFacter()."""
    self.client.facter_cache_path = '/x'

    mock_open = self.mox.CreateMockAnything()
    stat = self.mox.CreateMockAnything()
    mock_dt = self.mox.CreateMockAnything()

    self.mox.StubOutWithMock(client.os, 'stat')
    self.mox.StubOutWithMock(client.os, 'geteuid')

    self.mox.StubOutWithMock(client.os.path, 'isfile')
    client.os.path.isfile(self.client.facter_cache_path).AndReturn(True)

    stat.st_uid = 100

    client.os.stat(self.client.facter_cache_path).AndReturn(stat)
    client.os.geteuid().AndReturn(0)

    self.mox.ReplayAll()
    self.assertEqual({}, self.client.GetFacter(open_fn=mock_open))
    self.mox.VerifyAll()

  def testGetFacterWhenInsecureFileForNonRoot(self):
    """Test GetFacter()."""
    self.client.facter_cache_path = '/x'

    mock_open = self.mox.CreateMockAnything()
    stat = self.mox.CreateMockAnything()
    mock_dt = self.mox.CreateMockAnything()

    self.stubs.Set(client.datetime, 'datetime', mock_dt)
    self.mox.StubOutWithMock(client.os, 'stat')
    self.mox.StubOutWithMock(client.os, 'geteuid')

    self.mox.StubOutWithMock(client.os.path, 'isfile')
    client.os.path.isfile(self.client.facter_cache_path).AndReturn(True)

    stat.st_uid = 100

    client.os.stat(self.client.facter_cache_path).AndReturn(stat)
    client.os.geteuid().AndReturn(200)
    client.os.geteuid().AndReturn(200)
    client.os.geteuid().AndReturn(200)

    self.mox.ReplayAll()
    self.assertEqual({}, self.client.GetFacter(open_fn=mock_open))
    self.mox.VerifyAll()

  def testGetFacterWhenCacheDoesNotExist(self):
    """Test GetFacter() with a nonexistent cache file."""
    self.client.facter_cache_path = '/x'
    self.mox.StubOutWithMock(client.os.path, 'isfile')
    client.os.path.isfile(self.client.facter_cache_path).AndReturn(False)

    self.mox.ReplayAll()
    self.assertEqual({}, self.client.GetFacter())
    self.mox.VerifyAll()

  def testGetFacterWhenCachePathIsNone(self):
    """Test GetFacter() with facter_cache_path is None."""
    self.client.facter_cache_path = None

    self.mox.ReplayAll()
    self.assertEqual({}, self.client.GetFacter())
    self.mox.VerifyAll()

  def testGetAuthTokenFromHeadersSuccess(self):
    token = '%s=123; secure; httponly;' % auth.AUTH_TOKEN_COOKIE
    result = self.client._GetAuthTokenFromHeaders(
        {'set-cookie': 'other=value;,%s,something=else;' % token})
    self.assertEqual(token, result)

  def testGetAuthTokenFromHeadersMissingHeader(self):
    self.assertRaises(
        client.SimianClientError,
        self.client._GetAuthTokenFromHeaders,
        {'set-cookie': ''})


class SimianClientTest(mox.MoxTestBase):
  """Test SimianClient class."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()
    self.hostname = 'hostname'
    self.port = None
    self.client = client.SimianClient(self.hostname)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testInitWithoutHostname(self):
    """Test __init__() without a hostname passed."""
    user = 'foouser'
    self.mox.StubOutWithMock(
        client.SimianClient, '_GetLoggedOnUser', self.mox.CreateMockAnything())
    client.SimianClient._GetLoggedOnUser().AndReturn(user)

    self.mox.ReplayAll()
    clienttmp = client.SimianClient()
    self.assertEqual(clienttmp.hostname, client.SERVER_HOSTNAME)
    self.assertEqual(clienttmp._user, user)
    self.mox.VerifyAll()

  def testInitWithHostname(self):
    """Test __init__() with a hostname passed."""
    user = 'foouser'
    self.mox.StubOutWithMock(
        client.SimianClient, '_GetLoggedOnUser', self.mox.CreateMockAnything())
    client.SimianClient._GetLoggedOnUser().AndReturn(user)

    self.mox.ReplayAll()
    clienttmp = client.SimianClient('foo')
    self.assertEqual(clienttmp.hostname, 'foo')
    self.assertEqual(clienttmp._user, user)
    self.mox.VerifyAll()

  def testInitAsRoot(self):
    """Test __init__() with a hostname passed."""
    self.mox.StubOutWithMock(
        client.SimianClient, '_GetLoggedOnUser', self.mox.CreateMockAnything())
    client.SimianClient._GetLoggedOnUser().AndReturn('root')

    self.mox.ReplayAll()
    self.assertRaises(client.SimianClientError, client.SimianClient)
    self.mox.VerifyAll()

  def testIsDefaultHostClient(self):
    """Test IsDefaultHostClient()."""
    self.client._default_hostname = 'foo'
    self.assertEqual(self.client.IsDefaultHostClient(), 'foo')

  def testSimianRequest(self):
    """Test _SimianRequest()."""
    method = 'zGET'
    url = '/url'
    headers = {'foo': 'bar'}
    output_filename = None

    good_response = client.Response(status=200, body='hello there')

    self.mox.StubOutWithMock(self.client, 'Do')
    self.client.Do(
        method, url, body=None, headers=headers,
        output_filename=output_filename).AndReturn(good_response)

    self.mox.ReplayAll()
    self.assertEqual(
        good_response.body,
        self.client._SimianRequest(method, url, headers=headers))
    self.mox.VerifyAll()

  def testSimianRequestWithError(self):
    """Test _SimianRequest() with an error status returned."""
    method = 'zGET'
    url = '/url'
    headers = {'foo': 'bar'}
    output_filename = None

    error_response = client.Response(status=401, body='fooerror')

    self.mox.StubOutWithMock(self.client, 'Do')
    self.client.Do(
        method, url, body=None, headers=headers,
        output_filename=output_filename).AndReturn(error_response)

    self.mox.ReplayAll()
    self.assertRaises(
        client.SimianServerError,
        self.client._SimianRequest, method, url, headers=headers)
    self.mox.VerifyAll()

  def GenericStubTestAndReturn(
      self,
      method,
      method_return,
      method_args,
      stub_method_name, stub_method_return, *stub_args, **stub_kwargs):
    """Helper test method.

    TODO(user): Move to common.test.

    Args:
      method: method, to invoke in the test
      method_return: any, value to expect from method
      method_args: list, arguments to send to method during test
      stub_method_name: str, method name to stub out in SimianClient class
      stub_method_return: any, value to return from stubbed method call
      stub_args: list, args to expect when calling stub_method_name
      stub_kwargs: dict, kwargs to expect when calling stub_method_name
    """
    self.mox.StubOutWithMock(self.client, stub_method_name)
    getattr(self.client, stub_method_name)(
        *stub_args, **stub_kwargs).AndReturn(stub_method_return)

    self.mox.ReplayAll()
    got_rv = method(*method_args)
    self.assertEqual(got_rv, method_return)
    self.mox.VerifyAll()

  def GenericStubTest(
      self,
      method, method_args,
      stub_method_name, *stub_args, **stub_kwargs):
    """Helper test method.

    TODO(user): Move to common.test.

    Args:
      method: method, to invoke in the test
      method_args: list, arguments to send to method during test
      stub_method_name: str, method name to stub out in SimianClient class
      stub_args: list, args to expect when calling stub_method_name
      stub_kwargs: dict, kwargs to expect when calling stub_method_name
    Returns:
      string, 'returnval'
    """
    rv = 'returnval'
    return self.GenericStubTestAndReturn(
        method, rv, method_args,
        stub_method_name, rv, *stub_args, **stub_kwargs)

  def testGetCatalog(self):
    """Test GetCatalog()."""
    name = 'name'
    self.GenericStubTest(
        self.client.GetCatalog, [name],
        '_SimianRequest', 'GET', '/catalog/%s' % name)

  def testGetManifest(self):
    """Test GetManifest()."""
    name = 'name'
    self.GenericStubTest(
        self.client.GetManifest, [name],
        '_SimianRequest', 'GET', '/manifest/%s' % name)

  def testGetPackage(self):
    """Test GetPackage()."""
    name = 'name'
    self.GenericStubTest(
        self.client.GetPackage, [name],
        '_SimianRequest', 'GET', '/pkgs/%s' % name, output_filename=None)

  def testGetPackageInfo(self):
    """Test GetPackageInfo()."""
    filename = 'name.dmg'
    response = self.mox.CreateMockAnything()
    response.body = 'hello'
    self.GenericStubTestAndReturn(
        self.client.GetPackageInfo,
        'hello',
        [filename],
        '_SimianRequest',
        response,
        'GET', '/pkgsinfo/%s' % filename, full_response=True)

  def testGetPackageInfoWhenHash(self):
    """Test GetPackageInfo()."""
    filename = 'name.dmg'
    response = self.mox.CreateMockAnything()
    response.body = 'body'
    response.headers = {'x-pkgsinfo-hash': 'hash'}
    self.GenericStubTestAndReturn(
        self.client.GetPackageInfo, ('hash', 'body'),
        [filename, True],
        '_SimianRequest',
        response,
        'GET', '/pkgsinfo/%s?hash=1' % filename, full_response=True)

  def testDownloadPackage(self):
    """Test DownloadPackage()."""
    filename = 'foo'

    self.GenericStubTest(
        self.client.DownloadPackage,
        [filename],
        '_SimianRequest', 'GET',
        '/pkgs/%s' % filename, output_filename=filename)

  def testPostReport(self):
    """Test PostReport()."""
    report_type = 'foo'
    params = {'bar': 1}
    url = '/reports'
    body = '_report_type=%s&%s' % (
        report_type,
        client.urllib.urlencode(params, doseq=True))

    self.GenericStubTest(
        self.client.PostReport, [report_type, params],
        '_SimianRequest', 'POST', url, body)

  def testPostReportWhenFeedback(self):
    """Test PostReport()."""
    report_type = 'foo'
    params = {'bar': 1}
    url = '/reports'
    body = '_report_type=%s&%s&_feedback=1' % (
        report_type,
        client.urllib.urlencode(params, doseq=True))

    self.GenericStubTest(
        self.client.PostReport, [report_type, params, True],
        '_SimianRequest', 'POST', url, body)

  def testPostReportBody(self):
    """Test PostReportBody()."""
    url = '/reports'
    body = 'foo'

    self.GenericStubTest(
        self.client.PostReportBody, [body],
        '_SimianRequest', 'POST', url, body)

  def testPostReportBodyWhenFeedback(self):
    """Test PostReportBody()."""
    url = '/reports'
    body = 'foo'
    body_with_feedback = 'foo&_feedback=1'

    self.GenericStubTest(
        self.client.PostReportBody, [body, True],
        '_SimianRequest', 'POST', url, body_with_feedback)

  def testUploadFile(self):
    """Test UploadFile()."""
    self.mox.StubOutWithMock(client.os.path, 'isfile')
    self.mox.StubOutWithMock(self.client, 'Do')

    file_type = 'log'
    file_name = 'file.log'
    file_path = 'path/to/' + file_name
    url = '/uploadfile/%s/%s' % (file_type, file_name)

    mock_open = self.mox.CreateMockAnything()
    mock_open(file_path, 'r').AndReturn(mock_open)
    client.os.path.isfile(file_path).AndReturn(True)
    self.client.Do('PUT', url, mock_open).AndReturn(None)
    mock_open.close().AndReturn(None)

    self.mox.ReplayAll()
    self.client.UploadFile(file_path, file_type, _open=mock_open)
    self.mox.VerifyAll()

  def testUploadFileWhenLogNotFound(self):
    """Test UploadFile() when the file is not found."""
    self.mox.StubOutWithMock(client.os.path, 'isfile')
    self.mox.StubOutWithMock(client.logging, 'error')

    file_path = 'path/to/file.log'

    client.os.path.isfile(file_path).AndReturn(False)
    client.logging.error('UploadFile file not found: %s', file_path)

    self.mox.ReplayAll()
    self.client.UploadFile(file_path, 'foo-file-type')
    self.mox.VerifyAll()


class SimianAuthClientTest(mox.MoxTestBase):
  """Test SimianAuthClient class."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()
    self.pac = client.SimianAuthClient()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testGetAuthToken(self):
    """Test GetAuthToken()."""
    self.mox.StubOutWithMock(self.pac, 'DoSimianAuth')
    self.pac._cookie_token = 'token'
    self.pac.DoSimianAuth().AndReturn(None)
    self.mox.ReplayAll()
    self.assertEqual(self.pac.GetAuthToken(), 'token')
    self.mox.VerifyAll()

  def testLogoutAuthToken(self):
    """Test LogoutAuthToken()."""
    url = '/auth?logout=True'
    self.mox.StubOutWithMock(self.pac, '_SimianRequest')
    self.pac._SimianRequest('GET', url).AndReturn('ok')

    self.mox.ReplayAll()
    self.assertTrue(self.pac.LogoutAuthToken())
    self.mox.VerifyAll()

  def testLogoutAuthTokenWhenFail(self):
    """Test LogoutAuthToken()."""
    url = '/auth?logout=True'
    self.mox.StubOutWithMock(self.pac, '_SimianRequest')
    self.pac._SimianRequest('GET', url).AndRaise(client.SimianServerError)

    self.mox.ReplayAll()
    self.assertFalse(self.pac.LogoutAuthToken())
    self.mox.VerifyAll()


def main(unused_argv):
  basetest.main()


if __name__ == '__main__':
  app.run()
