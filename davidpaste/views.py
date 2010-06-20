#coding:utf-8
from datetime import datetime
import time, cgi, random, hashlib
import web
from forms import *
from settings import render, pageCount
from sqlalchemy.orm import scoped_session, sessionmaker
from models import *
from utils import Pagination, getCaptcha
from markdown import markdown

d = dict()

outputs = (
        'html', 'code'
    )

def getTags():
    return web.ctx.orm.query(Tag).order_by('tags.name').all()

def getSyntaxs():
    return web.ctx.orm.query(Syntax).order_by('syntaxs.name').all()

def my_loadhook():
    web.ctx.session = web.config._session

def my_handler(handler):
    web.ctx.orm = scoped_session(sessionmaker(bind=engine))
    try:
        return handler()
    except web.HTTPError:
        web.ctx.orm.commit()
        raise
    except:
        web.ctx.orm.rollback()
        raise
    finally:
        web.ctx.orm.commit()

class captcha:
    def GET(self):
        web.header('Content-type', 'image/gif')
        captcha = getCaptcha()
        web.ctx.session.captcha = captcha[0]
        return captcha[1].read()

class oauth(object):
    def GET(self):
        import urllib2
        sha = hashlib.sha1()
        sha.update(str(random.random))
        post_data = 'scope=http://www.google.com/base/feeds/'
        headers = {
                'Content-Type':'application/x-www-form-urlencoded',
                'Authorization':'OAuth',
                'oauth_consumer_key':'davidpaste.com',
                'oauth_signature_method':'HMAC-SHA1',
                'oauth_signature':'24K+l1CC/rlFdWNAEp47s2v0',
                'oauth_timestamp':str(int(time.time())),
                'oauth_nonce':sha.hexdigest(),
                'oauth_callback':'http://davidpaste.com/login/',
            }
        req = urllib2.Request('https://www.google.com/accounts/OAuthGetRequestToken', post_data, headers)
        try:
            response = urllib2.urlopen(req)
        except:
            raise web.internalerror()
        headers = response.headers
        oauth_token = headers['oauth_token']
        oauth_token_secret = headers['oauth_token_secret']
        req = urllib2.Request('https://www.google.com/accounts/OAuthAuthorizeToken?oauth_token=%s&hl=zh_CN' % oauth_token)
        try:
            response = urllib2.urlopen(req)
        except:
            raise web.internalerror()

class login(object):
    def GET(self):
        i = web.input(token=None, verifier=None)
        if i.token and i.verifier:
            import urllib2
            sha = hashlib.sha1()
            sha.update(str(random.random))
            headers = {
                    'Content-Type':'application/x-www-form-urlencoded',
                    'Authorization':'OAuth',
                    'oauth_token':i.token,
                    'oauth_consumer_key':'davidpaste.com',
                    'oauth_verifier':i.verifier,
                    'oauth_signature_method':'HMAC-SHA1',
                    'oauth_signature':'24K+l1CC/rlFdWNAEp47s2v0',
                    'oauth_timestamp':str(int(time.time())),
                    'oauth_nonce':sha.hexdigest(),
                }
            req = urllib2.Request('https://www.google.com/accounts/OAuthGetAccessToken')
            try:
                response = urllib2.urlopen(req)
            except:
                raise web.interalerror()
            return response.read()
        return render.index(**d)

class paste_view(object):
    def getPaste(self, id):
        return web.ctx.orm.query(Paste).filter_by(id=id).first()

    def GET(self, id):
        i = web.input(output='html')
        output = 'html'
        if i.output in outputs:
            output = i.output
        d['paste'] = self.getPaste(id)
        if d['paste']:
            if output == 'html':
                d['paste'].view_num = d['paste'].view_num + 1 
                return render.paste_view(**d)
            elif output == 'code':
                web.header('Content-Type', 'text')
                return render.paste_view_code(**d)
        else:
            raise web.notfound()

    def POST(self, id):
        entry, p = self.getEntry(slug)
        f = commentForm()
        if f.validates():
            comment = Comment(entry.id, f.username.value, f.email.value, f.url.value, f.comment.value)
            entry.commentNum = entry.commentNum + 1
            entry.viewNum = entry.viewNum - 1
            web.ctx.orm.add(comment)
            raise web.seeother('/entry/%s/' % slug)
        else:
            d['p'] = p
            d['entry'] = entry
            d['f'] = f
            d['usedTime'] = time.time() - d['startTime']
            return render.entry(**d)

class paste_create(object):
    def GET(self):
        d['f'] = paste_form()
        d['syntaxs'] = getSyntaxs()
        return render.paste_create(**d)

    def POST(self):
        f = paste_form()
        if f.validates():
            paste = Paste()
            paste.user_id = web.ctx.session.user_id
            paste.content = f.content.value
            paste.syntax_id = int(f.syntax.value)
            if f.title.value:
                paste.title = f.title.value
            web.ctx.orm.add(paste)
            if f.tags.value:
                for t in f.tags.value.split(','):
                    tag = web.ctx.orm.query(Tag).filter_by(name=t.strip().lower()).first()
                    if not tag:
                        tag = Tag(t.strip().lower())
                        web.ctx.orm.add(tag)
                    paste.tags.append(tag)
            try:
                web.ctx.orm.commit()
            except:
                web.ctx.orm.rollback()
                raise web.internalerror()
            else:
                raise web.seeother('/paste/%d/' % paste.id)
        d['f'] = f
        d['syntaxs'] = getSyntaxs()
        return render.paste_create(**d)

class tag(object):
    def GET(self, name):
        i = web.input(page=1)
        try:
            page = int(i.page)
        except:
            page = 1
        tag = web.ctx.orm.query(Tag).filter_by(name=name).first()
        p = Pagination(len(tag.pastes), 20, page)
        pastes = tag.pastes[::-1][p.start:p.limit]
        d['tag'] = tag
        d['p'] = p
        d['pastes'] = pastes
        d['usedTime'] = time.time() - d['startTime']
        return render.tag(**d)

class rss(object):
    def GET(self):
        entries = web.ctx.orm.query(Entry).order_by('entries.createdTime DESC').all()[:10]
        rss = '<?xml version="1.0" encoding="utf-8" ?>\n'
        rss = rss + '<rss version="2.0">\n'
        rss = rss + '<channel>\n'
        rss = rss + '<title>' + u'泥泞的沼泽' + '</title>\n'
        rss = rss + '<link>http://davidshieh.cn/</link>\n'
        rss = rss + '<description>' + u'泥泞的沼泽' + '</description>\n'
        rss = rss + '<lastBuildDate>' + datetime.now().strftime('%a, %d %b  %Y %H:%M:%S GMT') + '</lastBuildDate>\n'
        rss = rss + '<language>zh-cn</language>\n'
        for one in entries:
            rss = rss + '<item>\n'
            rss = rss + '<title>' + one.title + '</title>\n'
            rss = rss + '<link>http://davidx.me/entry/' + one.slug + '</link>\n'
            rss = rss + '<guid>http://davidx.me/entry/' + one.slug + '</guid>\n'
            rss = rss + '<pubDate>' + one.createdTime.strftime('%a, %d %b  %Y %H:%M:%S GMT') + '</pubDate>\n'
            rss = rss + '<description>' + cgi.escape(markdown(one.content)) + '</description>\n'
            rss = rss + '</item>\n'

        rss = rss + '</channel>\n'
        rss = rss + '</rss>\n'
        #web.header('Content-Type', 'text/xml')
        rss = rss.encode('utf-8')
        return rss

def notfound():
    #return web.notfound("对不起, 您所访问的地址并不存在.")
    return web.notfound(render.notfound(**d))

def internalerror():
    #return web.internalerror("对不起, 网站遇到一个不可遇见的错误.")
    return web.internalerror(render.servererror(**d))
