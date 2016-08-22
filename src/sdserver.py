#!/usr/bin/env python

"""
sdserver: Tornado-based web server to serve Slidoc html files (with authentication)
          - Handles digest authentication using HMAC key
          - Can be used as a simple static file server (with authentication), AND
          - As a proxy server that handles spreadsheet operations on cached data and copies them to Google sheets

        Use 'sdserver.py --proxy_wait=0 --gsheet_url=...' and
            'slidoc.py --gsheet_url=... --proxy_url=/_websocket/ ...' to proxy user calls to Google sheet (but not slidoc.py setup calls, which are still directed to gsheet_url)
        Can specify 'slidoc.py --gsheet_url=http:/hostname/_proxy/ --proxy_url=/_websocket/ ...' to re-direct session setup calls to proxy as well.

        For proxying without websocket:
            'slidoc.py --gsheet_url=... --proxy_url=http://localhost/_proxy'
        
Command arguments:
    debug: Enable debug mode (can be used for testing local proxy data without gsheet_url)
    gsheet_url: Google sheet URL (required if proxy and not debugging)
    auth_key: Digest authentication key for admin user (enables login protection for website)
    port: Web server port number to listen on (default=8888)
    private: path component string identifying private files (if omitted, entire website is login protected if auth_key is specified)
    proxy: Enable proxy mode (cache copies of Google Sheets)
    site_label: Site label, e.g., 'calc101'
    static_dir: path to static files directory containing Slidoc html files (default='static')
    twitter: path to Twitter JSON config file (to sign in via Twitter)
    xsrf: Enable XSRF cookies for security

Twitter auth workflow:
  - Register your application with Twitter at http://twitter.com/apps, using the Callback URL http://website/_oauth/twitter
  - Then copy your Consumer Key and Consumer Secret to file twitter.json
     {"consumer_key": ..., "consumer_secret": ...}
     sudo python sdserver.py --auth_key=... --gsheet_url=... --static_dir=... --port=80 --proxy_wait=0 --site_label=... --twitter=twitter.json
  - Create an initial Slidoc, say ex00-setup.md
  - Ask all users to ex00-setup.html using their Twitter login
  - In Google Docs, copy the first four columns of the ex00-setup sheet to a new roster_slidoc sheet
  - Once the roster_slidoc sheet is created, only users listed in that sheet can login
    Correct any name entries in the sheet, and add emails and/or ID values as needed
  - For additional users, manually add rows to roster_slidoc later
  - If some users need to change their Twitter IDs later, include a dict in twitter.json, {..., "rename": {"old_id": "new_id", ...}}
  - For admin user, include "admin_id": "admin" in rename dict
    
"""

import collections
import datetime
import importlib
import json
import logging
import math
import os.path
import sys
import time
import urllib

import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.options
import tornado.web
import tornado.websocket

from tornado.options import define, options
from tornado.ioloop import IOLoop

import sliauth
import plugins

USER_COOKIE_SECURE = "slidoc_user_secure"
SERVER_COOKIE = "slidoc_server"
EXPIRES_DAYS = 30

WS_TIMEOUT_SEC = 600

Options = {
    '_index_html': '',  # Non-command line option
    'auth_key': '',
    'debug': False,
    'gsheet_url': '',
    'no_auth': False,
    'private': '',
    'proxy_wait': None,
    'site_label': 'Slidoc',
    'static_dir': '',
    'twitter': '',
    'xsrf': False,
    }

class UserIdMixin(object):
    def set_id(self, username, origId='', token='', displayName=''):
        if ':' in username or ':' in origId:
            raise Exception('Colon character not allowed in username/origId')
        cookieStr = username+':'+origId+':'+urllib.quote(token, safe='')+':'+urllib.quote(displayName, safe='')
        self.set_secure_cookie(USER_COOKIE_SECURE, cookieStr, expires_days=EXPIRES_DAYS)
        self.set_cookie(SERVER_COOKIE, cookieStr, expires_days=EXPIRES_DAYS)

    def clear_id(self):
        self.clear_cookie(USER_COOKIE_SECURE)
        self.clear_cookie(SERVER_COOKIE)

    def check_access(self, username, token):
        if username == "admin":
            return token == Options['auth_key']
        else:
            return token == sliauth.gen_user_token(Options['auth_key'], username)

    def get_id_from_cookie(self, orig=False):
        # Ensure SERVER_COOKIE is also set before retrieving id from secure cookie (in case one of them gets deleted)
        cookieStr = self.get_secure_cookie(USER_COOKIE_SECURE) if self.get_cookie(SERVER_COOKIE) else ''
        if not cookieStr:
            return None
        try:
            userId, origId, token, displayName = cookieStr.split(':')
            return origId if orig else userId
        except Exception, err:
            print >> sys.stderr, 'sdserver: Cookie error - '+str(err)
            self.clear_id()
            return None


class BaseHandler(tornado.web.RequestHandler, UserIdMixin):
    def get_current_user(self):
        if not Options['auth_key']:
            self.clear_id()
            return "noauth"
        return self.get_id_from_cookie() or None


class HomeHandler(BaseHandler):
    def get(self):
        if Options.get('_index_html'):
            # Not authenticated
            self.write(Options['_index_html'])
        else:
            # Authenticated by static file handler, if need be
            self.redirect("/index.html")


class ActionHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, subpath, inner=None):
        if self.get_current_user() != '"admin"':
            self.write('Action not permitted')
            return
        action, sep, sessionName = subpath.partition('/')
        import sdproxy
        if action == '_shutdown':
            sdproxy.start_shutdown()
            self.write('Starting shutdown')
        elif action == '_unlock':
            if sessionName in Lock_cache:
                del sdproxy.Lock_cache[sessionName]
            if sessionName in Sheet_cache:
                del sdproxy.Sheet_cache[sessionName]
            self.write('Unlocked '+sessionName)
        elif action == '_lock':
            if sessionName:
                sdproxy.Lock_cache[sessionName] = True
            self.write('Locked sessions: %s' % (', '.join(sdproxy.get_locked())) )
        elif action == '_stats':
            self.write('<pre>')
            self.write('Cache:\n')
            self.write('  No. of updates (retries): %d (%d)\n  Average update time = %ss\n' % (sdproxy.TotalCacheResponseCount, sdproxy.TotalCacheRetryCount, sdproxy.TotalCacheResponseInterval/(1000*max(1,sdproxy.TotalCacheRetryCount)) ) )
            curTime = time.time()
            wsKeys = WSHandler._connections.keys()
            sorted(wsKeys)
            wsInfo = []
            for pathUser in wsKeys:
                wsInfo += [(pathUser[0], pathUser[1]+('/'+ws.origId if ws.origId else ''), math.floor(curTime-ws.msgTime)) for ws in WSHandler._connections[pathUser]]
            sorted(wsInfo)
            self.write('\nConnections:\n')
            for x in wsInfo:
                self.write("  %s: %s (idle: %ds)\n" % x)
            self.write('</pre>')


class ProxyHandler(BaseHandler):
    def get(self):
        self.handleResponse()

    def post(self):
        self.handleResponse()

    def handleResponse(self):
        jsonPrefix = ''
        jsonSuffix = ''
        mimeType = 'application/json'
        if self.get_argument('prefix',''):
            jsonPrefix = self.get_argument('prefix','') + '(' + (self.get_argument('callback') or '0') + ', '
            jsonSuffix = ')'
            mimeType = 'application/javascript'

        import sdproxy
        args = {}
        for arg_name in self.request.arguments:
            args[arg_name] = self.get_argument(arg_name)

        if Options['debug']:
            print "DEBUG: URI", self.request.uri

        retObj = sdproxy.handleResponse(args)

        self.set_header('Content-Type', mimeType)
        self.write(jsonPrefix+json.dumps(retObj, default=sliauth.json_default)+jsonSuffix)

class WSHandler(tornado.websocket.WebSocketHandler, UserIdMixin):
    _connections = collections.defaultdict(list)
    def open(self, path=''):
        self.msgTime = time.time()
        self.locked = ''
        self.timeout = None
        self.userId = self.get_id_from_cookie()
        self.origId = self.get_id_from_cookie(orig=True)
        if self.origId == self.userId:
            self.origId = ''
        self.pathUser = (path, self.userId)
        self._connections[self.pathUser].append(self)
        self.pluginInstances = {}
        self.awaitBinary = None

        if Options['debug']:
            print "DEBUG: WSopen", self.userId
        if not self.userId:
            self.close()

    def on_close(self):
        try:
            self._connections[self.pathUser].remove(self)
            if not self._connections[self.pathUser]:
                del self._connections[self.pathUser]
        except Exception, err:
            pass

    def _close_on_timeout(self):
        if self.ws_connection:
            self.close()

    def on_message(self, message):
        binaryContent = None
        if isinstance(message, bytes):
            # Binary message (treat as additional argument for last text message)
            if not self.awaitBinary:
                return
            binaryContent = message
            message = self.awaitBinary   # Restore buffered text message
            self.awaitBinary = None

        elif self.awaitBinary:
            # New text message; discard previous text message awaiting binary data
            self.awaitBinary = None

        self.msgTime = time.time()
        if self.timeout:
            IOLoop.current().remove_timeout(self.timeout)
            self.timeout = None
        import sdproxy
        outMsg = None
        callback_index = None
        try:
            obj = json.loads(message)
            callback_index = obj[0]
            method = obj[1]
            args = obj[2]
            retObj = None
            if method == 'close':
                self.close()

            elif method == 'proxy':
                if args.get('write'):
                    if self.locked:
                        raise Exception(self.locked)
                    else:
                        for connection in self._connections[self.pathUser]:
                            if connection is self:
                                continue
                            if not connection.locked:
                                connection.locked = 'Session locked due to modifications by another user. Reload page, if necessary.'
                                connection.write_message(json.dumps([0, 'lock', connection.locked]))

                retObj = sdproxy.handleResponse(args)

            elif method == 'plugin':
                if len(args) < 2:
                    raise Exception('Too few arguments to invoke plugin method: '+' '.join(args))
                pluginName, pluginMethodName = args[:2]
                if pluginName not in self.pluginInstances:
                    pluginModule = getattr(plugins, pluginName, None)
                    if not pluginModule:
                        raise Exception('Plugin '+pluginName+' not loaded!')
                    pluginClass = getattr(pluginModule, pluginName)
                    if not pluginClass:
                        raise Exception('Plugin class '+pluginName+'.'+pluginName+' not defined!')
                    try:
                        self.pluginInstances[pluginName] = pluginClass(self.pathUser[0], self.pathUser[1])
                    except Exception, err:
                        raise Exception('Error in creating instance of plugin '+pluginName+': '+err.message)

                pluginMethod = getattr(self.pluginInstances[pluginName], pluginMethodName, None)
                if not pluginMethod:
                    raise Exception('Plugin '+pluginName+' has no method '+pluginMethodName)

                if pluginMethodName == 'uploadData':
                    # plugin.uploadData(arg1, ..., binaryData)
                    print >> sys.stderr, 'sdserver: %s.uploadData' % pluginName, args, not binaryContent
                    if not binaryContent:
                        # Buffer text message and wait for final binary argument
                        self.awaitBinary = message
                        return
                    # Append binary data as final argument
                    args.append(binaryContent)
                    binaryContent = None
                try:
                    retObj = pluginMethod(*args[2:])
                except Exception, err:
                    raise Exception('Error in calling method '+pluginMethodName+' of plugin '+pluginName+': '+err.message)

            if callback_index:
                outMsg = json.dumps([callback_index, '', retObj], default=sliauth.json_default)
        except Exception, err:
            if Options['debug']:
                raise Exception('Error in response: '+err.message)
            elif callback_index:
                    retObj = {"result":"error", "error": err.message, "value": None, "messages": ""}
                    outMsg = json.dumps([callback_index, '', retObj], default=sliauth.json_default)

        if outMsg:
            self.write_message(outMsg)
        self.timeout = IOLoop.current().call_later(WS_TIMEOUT_SEC, self._close_on_timeout)


class BaseStaticFileHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        # Disable cache
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
    

class AuthStaticFileHandler(BaseStaticFileHandler, UserIdMixin):
    def get_current_user(self):
        if not Options['auth_key']:
            self.clear_id()
            return "noauth"
        if Options['private'] and Options['private'] not in self.request.path:
            return "noauth"
        return self.get_id_from_cookie() or None

    # Override this method because overriding the get method of StaticFileHandler is problematic
    @tornado.web.authenticated
    def validate_absolute_path(self, *args, **kwargs):
        return super(AuthStaticFileHandler, self).validate_absolute_path(*args, **kwargs)
    

class AuthLoginHandler(BaseHandler):
    def get(self):
        error_msg = self.get_argument("error", "")
        username = self.get_argument("username", "")
        token = self.get_argument("token", "")
        next = self.get_argument("next", "/")
        if not error_msg and username and token:
            self.login(username, token, next=next)
        else:
            self.render("login.html", error_msg=error_msg, next=next, site_label=Options['site_label'],
                        login_url=Login_url, password='NO AUTHENTICATION' if Options['no_auth'] else 'Token:')

    def post(self):
        self.login(self.get_argument("username", ""), self.get_argument("token", ""), next=self.get_argument("next", "/"))

    def login(self, username, token, next="/"):
        if Options['no_auth'] and Options['debug'] and not Options['gsheet_url'] and username != 'admin':
            # No authentication option for testing local-only proxy
            token = sliauth.gen_user_token(Options['auth_key'], username)
        auth = self.check_access(username, token)
        if auth:
            self.set_id(username, '', token)
            self.redirect(next)
        else:
            error_msg = "?error=" + tornado.escape.url_escape("Incorrect username or token")
            self.redirect("/_auth/login/" + error_msg)

            
class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_id()
        self.write('Logged out.<p></p><a href="/">Home</a>')


class TwitterLoginHandler(tornado.web.RequestHandler,
                          tornado.auth.TwitterMixin, UserIdMixin):
    @tornado.gen.coroutine
    def get(self):
        if self.get_argument("oauth_token", None):
            user = yield self.get_authenticated_user()
            # Save the user using e.g. set_secure_cookie()
            username = user['username']
            if 'rename' in Twitter_config and username in Twitter_config['rename']:
                username = Twitter_config['rename'][username]
            displayName = user['name']
            token = Options['auth_key'] if username == 'admin' else sliauth.gen_user_token(Options['auth_key'], username)
            self.set_id(username, user['username'], token, displayName)
            self.redirect(self.get_argument("next", "/"))
        else:
            yield self.authorize_redirect()


class Application(tornado.web.Application):
    def __init__(self):
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "server_templates"),
            xsrf_cookies=Options['xsrf'],
            cookie_secret=Options['auth_key'],
            login_url=Login_url,
            debug=Options['debug'],
        )

        handlers = [
            (r"/", HomeHandler),
            (r"/_auth/logout/", AuthLogoutHandler),
            (r"/_auth/login/", AuthLoginHandler),
            ]

        if Options['twitter']:
            settings.update(twitter_consumer_key=Twitter_config['consumer_key'],
                            twitter_consumer_secret=Twitter_config['consumer_secret'])

            handlers += [ ("/_oauth/twitter", TwitterLoginHandler) ]

        if Options['proxy_wait'] is not None:
            handlers += [ (r"/_proxy", ProxyHandler),
                          (r"/_websocket/(.*)", WSHandler),
                          (r"/(_lock)", ActionHandler),
                          (r"/(_lock/[-\w.]+)", ActionHandler),
                          (r"/(_unlock/[-\w.]+)", ActionHandler),
                          (r"/(_shutdown)", ActionHandler),
                          (r"/(_stats)", ActionHandler),
                           ]

        if Options['no_auth']:
            handlers += [ (r"/(.+)", BaseStaticFileHandler, {"path": Options['static_dir']}) ]
        else:
            handlers += [ (r"/(.+)", AuthStaticFileHandler, {"path": Options['static_dir']}) ]

        super(Application, self).__init__(handlers, **settings)


Login_url = '/_auth/login/'
Twitter_config = {}
def main():
    global Login_url
    define("auth_key", default="", help="Digest authentication key for admin user")
    define("debug", default=False, help="Debug mode")
    define("gsheet_url", default="", help="Google sheet URL")
    define("ssl", default="", help="SSL certs options file (JSON)")
    define("plugins", default="", help="List of plugin paths (comma separated)")
    define("no_auth", default=False, help="No authentication mode (for testing)")
    define("private", default=Options["private"], help="Private path component (to protect with login)")
    define("proxy_wait", type=int, help="Proxy wait time (>=0; omit argument for no proxy)")
    define("site_label", default=Options["site_label"], help="Site label")
    define("static_dir", default="static", help="Path to static files directory")
    define("twitter", default="", help="'consumer_key,consumer_secret' OR JSON config file for twitter authentication")
    define("xsrf", default=False, help="XSRF cookies for security")

    define("port", default=8888, help="Web server port", type=int)
    tornado.options.parse_command_line()
    for key in Options:
        if not key.startswith('_'):
            Options[key] = getattr(options, key)

    if not options.debug:
        logging.getLogger('tornado.access').disabled = True

    if options.proxy_wait is not None:
        import sdproxy
        sdproxy.Options.update(AUTH_KEY=options.auth_key, SHEET_URL=options.gsheet_url, DEBUG=options.debug,
                               MIN_WAIT_TIME=options.proxy_wait)

    if options.twitter:
        Login_url = "/_oauth/twitter"
        if ',' in options.twitter:
            comps = options.twitter.split(',')
            Twitter_config.update(consumer_key=comps[0], consumer_secret=comps[1])
        else:
            # Twitter config file (JSON): {"consumer_key": ..., "consumer_secret": ..., rename={"aaa":"bbb",...}}
            tfile = open(options.twitter)
            Twitter_config.update(json.loads(tfile.read()))
            tfile.close()

    scriptdir = os.path.dirname(os.path.realpath(__file__))
    pluginsDir = scriptdir + '/plugins'
    pluginPaths = [pluginsDir+'/'+fname for fname in os.listdir(pluginsDir) if fname[0] not in '._' and fname.endswith('.py')]
    if options.plugins:
        # Plugins with same name will override earlier plugins
        pluginPaths += options.plugins.split(',')

    plugins = []
    for pluginPath in pluginPaths:
        pluginName = os.path.basename(pluginPath).split('.')[0]
        plugins.append(pluginName)
        importlib.import_module('plugins.'+pluginName)

    if plugins:
        print >> sys.stderr, 'sdserver: Loaded plugins: '+', '.join(plugins)

    if options.ssl:
        jfile = open(options.ssl)
        ssl_options = json.loads(jfile.read())
        jfile.close()
        http_server = tornado.httpserver.HTTPServer(Application(), ssl_options=ssl_options)
    else:
        http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    print >> sys.stderr, "Listening on port", options.port
    IOLoop.current().start()


if __name__ == "__main__":
    main()
