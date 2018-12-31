#!/usr/bin/env python
# coding: utf-8
import qrcode
import urllib, urllib2
import cookielib
import requests
import xml.dom.minidom
import json
import time, re, sys, os, random
import multiprocessing

def catchKeyboardInterrupt(fn):
	def wrapper(*args):
		try:
			return fn(*args)
		except KeyboardInterrupt:
			print '\n[*] 强制退出程序'
	return wrapper

class WebWeixin(object):
	def __str__(self):
		description = \
		"=========================\n" + \
		"[#] Web Weixin\n" + \
		"[#] Debug Mode: " + str(self.DEBUG) + "\n" + \
		"[#] Uuid: " + self.uuid + "\n" + \
		"[#] Uin: " + str(self.uin) + "\n" + \
		"[#] Sid: " + self.sid + "\n" + \
		"[#] Skey: " + self.skey + "\n" + \
		"[#] DeviceId: " + self.deviceId + "\n" + \
		"[#] PassTicket: " + self.pass_ticket + "\n" + \
		"========================="
		return description

	def __init__(self):
		self.DEBUG = False
		self.uuid = ''
		self.base_uri = ''
		self.redirect_uri= ''
		self.uin = ''
		self.sid = ''
		self.skey = ''
		self.pass_ticket = ''
		self.deviceId = 'e' + repr(random.random())[2:17]
		self.BaseRequest = {}
		self.synckey = ''
		self.SyncKey = []
		self.User = []
		self.MemberList = []
		self.ContactList = []
		self.GroupList = []
		self.autoReplyMode = True

		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
		urllib2.install_opener(opener)

	def getUUID(self):
		url = 'https://login.weixin.qq.com/jslogin'
		params = {
			'appid': 'wx782c26e4c19acffb',
			'fun': 'new',
			'lang': 'zh_CN',
			'_': int(time.time()),
		}
		data = self._post(url, params, False)
		regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
		pm = re.search(regx, data)
		if pm:
			code = pm.group(1)
			self.uuid = pm.group(2)
			return code == '200'
		return False

	def genQRCode(self):
		self._str2qr('https://login.weixin.qq.com/l/' + self.uuid)

	def waitForLogin(self, tip = 1):
		time.sleep(tip)
		url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (tip, self.uuid, int(time.time()))
		data = self._get(url)
		pm = re.search(r'window.code=(\d+);', data)
		code = pm.group(1)

		if code == '201': return True
		elif code == '200':
			pm = re.search(r'window.redirect_uri="(\S+?)";', data)
			r_uri = pm.group(1) + '&fun=new'
			self.redirect_uri = r_uri
			self.base_uri = r_uri[:r_uri.rfind('/')]
			return True
		elif code == '408':
			self._echo('[登陆超时] ')
		else:
			self._echo('[登陆异常] ')
		return False

	def login(self):
		data = self._get(self.redirect_uri)
		doc = xml.dom.minidom.parseString(data)
		root = doc.documentElement

		for node in root.childNodes:
			if node.nodeName == 'skey':
				self.skey = node.childNodes[0].data
			elif node.nodeName == 'wxsid':
				self.sid = node.childNodes[0].data
			elif node.nodeName == 'wxuin':
				self.uin = node.childNodes[0].data
			elif node.nodeName == 'pass_ticket':
				self.pass_ticket = node.childNodes[0].data

		if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
			return False

		self.BaseRequest = {
			'Uin': int(self.uin),
			'Sid': self.sid,
			'Skey': self.skey,
			'DeviceID': self.deviceId,
		}
		return True

	def webwxinit(self):
		url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (self.pass_ticket, self.skey, int(time.time()))
		params = {
			'BaseRequest': self.BaseRequest
		}
		dic = self._post(url, params)
		self.SyncKey = dic['SyncKey']
		self.User = dic['User']
		# synckey for synccheck
		self.synckey = '|'.join([ str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List'] ])

		return dic['BaseResponse']['Ret'] == 0

	def webwxstatusnotify(self):
		url = self.base_uri + '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			"Code": 3,
			"FromUserName": self.User['UserName'],
			"ToUserName": self.User['UserName'],
			"ClientMsgId": int(time.time())
		}
		dic = self._post(url, params)

		return dic['BaseResponse']['Ret'] == 0

	def webwxgetcontact(self):
		url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (self.pass_ticket, self.skey, int(time.time()))
		dic = self._post(url, {})
		self.MemberList = dic['MemberList']

		ContactList = self.MemberList[:]
		SpecialUsers = ['newsapp', 'fmessage', 'filehelper', 'weibo', 'qqmail', 'fmessage', 'tmessage', 'qmessage', 'qqsync', 'floatbottle', 'lbsapp', 'shakeapp', 'medianote', 'qqfriend', 'readerapp', 'blogapp', 'facebookapp', 'masssendapp', 'meishiapp', 'feedsapp', 'voip', 'blogappweixin', 'weixin', 'brandsessionholder', 'weixinreminder', 'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'officialaccounts', 'notification_messages', 'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'wxitil', 'userexperience_alarm', 'notification_messages']
		for i in xrange(len(ContactList) - 1, -1, -1):
			Contact = ContactList[i]
			if Contact['VerifyFlag'] & 8 != 0: # 公众号/服务号
				ContactList.remove(Contact)
			elif Contact['UserName'] in SpecialUsers: # 特殊账号
				ContactList.remove(Contact)
			elif Contact['UserName'].find('@@') != -1: # 群聊
				self.GroupList.append(Contact)
				ContactList.remove(Contact)
			elif Contact['UserName'] == self.User['UserName']: # 自己
				ContactList.remove(Contact)
		self.ContactList = ContactList

		return True

	def webwxbatchgetcontact(self):
		url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			"Count": len(self.GroupList),
			"List": [ {"UserName": g['UserName'], "EncryChatRoomId":""} for g in self.GroupList ]
		}
		dic = self._post(url, params)
		# blabla ...
		return True

	def synccheck(self):
		params = {
			'r': int(time.time()),
			'sid': self.sid,
			'uin': self.uin,
			'skey': self.skey,
			'deviceid': self.deviceId,
			'synckey': self.synckey,
			'_': int(time.time()),
		}
		url = 'https://webpush.weixin.qq.com/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode(params)
		data = self._get(url)
		pm = re.search(r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}', data)
		retcode = pm.group(1)
		selector = pm.group(2)
		return [retcode, selector]

	def webwxsync(self):
		url = self.base_uri + '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (self.sid, self.skey, self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			'SyncKey': self.SyncKey,
			'rr': ~int(time.time())
		}
		dic = self._post(url, params)
		if self.DEBUG: print dic

		if dic['BaseResponse']['Ret'] == 0:
			self.SyncKey = dic['SyncKey']
			self.synckey = '|'.join([ str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List'] ])
		return dic

	def webwxsendmsg(self, word, to = 'filehelper'):
		url = self.base_uri + '/webwxsendmsg?pass_ticket=%s' % (self.pass_ticket)
		clientMsgId = str(int(time.time()*1000)) + str(random.random())[:5].replace('.','')
		params = {
			'BaseRequest': self.BaseRequest,
			'Msg': {
				"Type": 1,
				"Content": self._transcoding(word),
				"FromUserName": self.User['UserName'],
				"ToUserName": to,
				"LocalID": clientMsgId,
				"ClientMsgId": clientMsgId
			}
		}
		headers = {'content-type': 'application/json; charset=UTF-8'}
		data = json.dumps(params, ensure_ascii=False).encode('utf8')
		r = requests.post(url, data = data, headers = headers)
		dic = r.json()
		return dic['BaseResponse']['Ret'] == 0

	def getUserRemarkName(self, id):
		name = u'这个人物名字未知'
		for member in self.MemberList:
			if member['UserName'] == id:
				name = member['RemarkName'] if member['RemarkName'] else member['NickName']
		return name.encode('utf-8')

	def getUSerID(self, name):
		name = name.decode('utf-8')
		for member in self.MemberList:
			if name == member['RemarkName'] or name == member['NickName']:
				return member['UserName']
		return None

	def handleMsg(self, r):
		for msg in r['AddMsgList']:
			print '[*] 你有新的消息，请注意查收'
			msgType = msg['MsgType']
			name = self.getUserRemarkName(msg['FromUserName'])
			content = msg['Content'].encode('utf-8')
			if msgType == 51:
				print '[*] 成功截获微信初始化消息'
			elif msgType == 1:
				if msg['ToUserName'] == 'filehelper':
					print name+' -> 文件传输助手: '+content.replace('<br/>','\n')
				elif msg['FromUserName'] == self.User['UserName']:
					pass
				elif msg['ToUserName'][:2] == '@@':
					[people, content] = content.split(':<br/>')
					print '|'+name+'| '+people+':\n'+content.replace('<br/>','\n')
				else:
					print name+': '+content
					if self.autoReplyMode:
						ans = self._xiaodoubi(content)+'\n[微信机器人自动回复]'
						if self.webwxsendmsg(ans, msg['FromUserName']):
							print '自动回复: '+ans
						else:
							print '自动回复失败'
			elif msgType == 3:
				print name+' 给你发送了一张图片，请在手机上查看'
			elif msgType == 34:
				print name+' 给你发了一段语音，请在手机上查看'
			elif msgType == 42:
				print name+' 给你发送了一张名片:'
				print '========================='
				print '= 昵称: '+self._searchContent('nickname', content)
				print '= 微信号: '+self._searchContent('alias', content)
				print '= 地区: '+self._searchContent('province', content)+' '+self._searchContent('city', content)
				print '= 性别: '+( '男' if self._searchContent('sex', content)=='1' else '女' )
				print '========================='
			elif msgType == 47:
				url = self._searchContent('cdnurl', content)
				print name+' 给你发了一个动画表情，点击下面链接查看:'
				print url
				os.system('open %s' % url)
			elif msgType == 49:
				content = content.replace('&lt;','<').replace('&gt;','>')
				print name+' 给你分享了一个链接:'
				print '========================='
				print '= 标题: '+self._searchContent('title', content, 'xml')
				print '= 描述: '+self._searchContent('des', content, 'xml')
				print '= 链接: '+self._searchContent('url', content, 'xml')
				print '========================='
			elif msgType == 62:
				print name+' 给你发了一个小视频，请在手机上查看'
			elif msgType == 10002:
				print name+' 撤回消息'
			else:
				print '[*] 该消息类型为: %d，可能是表情，图片或链接' % msg['MsgType']
				print msg

	def listenMsgMode(self):
		print '[*] 进入消息监听模式 ... 成功'
		playWeChat = 0
		while True:
			[retcode, selector] = self.synccheck()
			if self.DEBUG: print 'retcode: %s, selector: %s' % (retcode, selector)
			if retcode == '1100':
				print '[*] 你在手机上登出了微信，债见'
				break
			elif retcode == '0':
				if selector == '2':
					r = self.webwxsync()
					if r is not None: self.handleMsg(r)
				elif selector == '7':
					playWeChat += 1
					print '[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat
					r = self.webwxsync()
				elif selector == '0':
					time.sleep(1)

	#  这里不考虑nickname长度不为2/3的人，我联系人里大多数都有备注
	def sendAll(self, msg):
		for contact in self.ContactList:
			name = contact['RemarkName'] if contact['RemarkName'] else contact['NickName']
			userID = contact['UserName']
			zhufuyul = [
						'我的祝福从延髓出发，沿着迷走神经穿过颈静脉孔，出颅绕左锁骨下动脉，越主动脉经左肺根，达第六胸椎左前方那个叫心脏的角落汹涌而出：新年快乐！',
						'空气分子振动通过鼓膜，顺着听小骨，通过内耳毛细胞点燃蜗螺旋神经节内的双极细胞，沿着蜗神经经蜗神经腹核和背核经蜗神经腹核和背核经斜方体并交叉上行，经下丘，内侧膝状体，经听辐射，通过内囊到达颞叶颞横回，让我们听到了新年的钟声。',
						'距状沟周围皮质的神经元将焰火经角回，wernicke区，弓状束，来到broca区，经中央前回，通过皮质脑干束，经内囊膝部下行至脑干，到达面神经核下部和舌下神经核，控制着口腔和舌头，大声疾呼：新年快乐。',
						'元旦的钟声响起，是幸福的和弦，是快乐的音符；元旦的鞭炮响起，是吉祥的旋律，是美好的乐章；元旦的祝福送上，愿你元旦快乐，心情无限好，日子比蜜甜！',
						'新年到了，迎来新的生活，换上新的心情，踏上新的旅程，开启新的希望，承载新的梦想，收获新的成功，享受新的幸福。祝你元旦快乐！',
						'送你一份快乐，让你忘记烦恼；送你一份悠闲，让你自在逍遥；送你一份如意，让你事事顺心；送你一份美满，让你幸福到老。元旦将临，预祝你快乐美妙！',
						'元旦到了；愿你抱着平安，拥着健康，揣着幸福，携着快乐，搂着温馨，带着甜蜜，牵着财运，拽着吉祥，迈入新年，快乐度过每一天！',
						'美妙音乐围绕你，爽朗笑声相伴你，温馨生活跟随你，甜美祝福靠近你，健康快乐依偎你，平平安安照顾你，好运时刻守着你，真心真意祝福你，吉祥如意事事顺！',
						'愿幸福挥之不去，让机遇只争朝夕，愿身体健康如一，让好运春风化雨，愿快乐如期而至，让情谊日累月积，愿片言表我心语，愿你新年阖家幸福，事事称意！',
						'送你一份快乐，让你忘记烦恼；送你一份悠闲，让你自在逍遥；送你一份如意，让你事事顺心；送你一份美满，让你幸福到老。元旦将临，预祝你快乐美妙！',
						'有阳光照耀的地方就有我默默的祝福，当月光洒向地球的时候就有我默默的祈祷，当流星划过的刹那我许了个愿：祝你平安健康，元旦快乐！',
						'快乐之花为你尽情绽放，幸福之光为你肆意闪烁，开心之果任你随意品尝，祝福之语为你真诚祝愿，元旦到，愿你乐无边，福无尽，笑颜开！',
						'飞雪送春归，笑迎元旦到，已是万家灯火时，祝福不能少；愿您开口笑，天天没烦恼，待到春暖花开时，幸福身边绕，吉祥乐逍遥！祝元旦快乐！',
						'衷心的祝愿你在新的一年里，所有的期待都能出现，所有的梦想都能实现，所有的希望都能如愿，所有的付出都能兑现！'
						]  #隨機祝福語列表
			zfy =zhufuyul[random.randint(0,13)]
			message = self._transcoding(msg + zfy) #这里要改成随机祝福语
			greeting = name
			# print 'name的长度为' + str(len(name))
			# 去掉名字中的姓 只支持三字名 二字名直接发全名算了，四字名不管了
			if len(name) == 3:
				mingzi = name[1:]
				greeting = mingzi + u', ' + message
				if self.webwxsendmsg(greeting, userID):
					print name + u'/消息为' + greeting + u' => 三字名发送成功'
				else:
					print greeting + u' => 三字名发送失败'
				time.sleep(5) #修改为发送后等待5s
			#二字名不做处理
			elif len(name) == 2:
				greeting = name + u', ' + message
				if self.webwxsendmsg(greeting, userID):
					print name + u'/消息为'+ greeting +u' => 二字名发送成功'
				else:
					print greeting + u' => 二字名发送失败'
				time.sleep(5)  # 修改为发送后等待5s
			else:
				print name + u'/消息为' + greeting +u' => 因名字长度发送失败'
				time.sleep(5)  # 修改为发送后等待5s

	def sendMsg(self, name, word, isfile = False):
		id = self.getUSerID(name)
		if id:
			if isfile:
				with open(word, 'r') as f:
					for line in f.readlines():
						line = line.replace('\n','')
						self._echo('-> '+name+': '+line)
						if self.webwxsendmsg(line, id):
							print ' [成功]'
						else:
							print ' [失败]'
						time.sleep(1)
			else:
				if self.webwxsendmsg(word, id):
					print '[*] 消息发送成功'
				else:
					print '[*] 消息发送失败'
		else:
			print '[*] 此用户不存在'

	@catchKeyboardInterrupt
	def start(self):
		print '[*] 微信网页版 ... 开动'
		self._run('[*] 正在获取 uuid ... ', self.getUUID)
		print '[*] 正在获取二维码 ... 成功'; self.genQRCode()
		self._run('[*] 请使用微信扫描二维码以登录 ... ', self.waitForLogin)
		self._run('[*] 请在手机上点击确认以登录 ... ', self.waitForLogin, 0)
		self._run('[*] 正在登录 ... ', self.login)
		self._run('[*] 微信初始化 ... ', self.webwxinit)
		self._run('[*] 开启状态通知 ... ', self.webwxstatusnotify)
		self._run('[*] 获取联系人 ... ', self.webwxgetcontact)
		print '[*] 共有 %d 位联系人' % len(self.ContactList)
		if self.DEBUG: print self

		# if raw_input('[*] 是否开启自动回复模式(y/n): ') == 'y':
		# 	self.autoReplyMode = True
		# 	print '[*] 自动回复模式 ... 开启'
		# else:
		print '[*] 自动回复模式 ... 关闭'

		listenProcess = multiprocessing.Process(target=self.listenMsgMode)
		listenProcess.start()

		while True:
			text = raw_input('')
			if text == 'quit':
				listenProcess.terminate()
				exit('[*] 退出微信')
			elif text[:5] == 'all->':
				self.sendAll(text[5:])
			elif text[:2] == '->':
				[name, word] = text[2:].split(':')
				self.sendMsg(name, word)
			elif text[:3] == 'm->':
				[name, file] = text[3:].split(':')
				self.sendMsg(name, file, True)
			elif text[:3] == 'f->':
				print '发送文件'
			elif text[:3] == 'i->':
				print '发送图片'

	def _run(self, str, func, *args):
		self._echo(str)
		if func(*args): print '成功'
		else: exit('失败\n[*] 退出程序')

	def _echo(self, str):
		sys.stdout.write(str)
		sys.stdout.flush()

	def _printQR(self, mat):
		for i in mat:
			BLACK = '\033[40m  	\033[0m'
			WHITE = '\033[47m  	\033[0m'
			print ''.join([BLACK if j else WHITE for j in i])

	def _str2qr(self, str):
		qr = qrcode.QRCode()
		qr.border = 1
		qr.add_data(str)
		mat = qr.get_matrix()
		self._printQR(mat) # qr.print_tty() or qr.print_ascii()

	def _transcoding(self, data):
		if not data: return data
		result = None
		if type(data) == unicode:
			result = data
		elif type(data) == str:
			result = data.decode('utf-8')
		return result

	def _get(self, url):
		request = urllib2.Request(url = url)
		response = urllib2.urlopen(request)
		data = response.read()
		return data

	def _post(self, url, params, jsonfmt = True):
		if jsonfmt:
			request = urllib2.Request(url = url, data = json.dumps(params))
			request.add_header('ContentType', 'application/json; charset=UTF-8')
		else:
			request = urllib2.Request(url = url, data = urllib.urlencode(params))
		response = urllib2.urlopen(request)
		data = response.read()
		if jsonfmt: return json.loads(data)
		return data

	def _xiaodoubi(self, word):
		url = 'http://www.xiaodoubi.com/bot/chat.php'
		try:
			r = requests.post(url, data = {'chat': word})
			return r.content
		except:
			return "让我一个人静静 T_T..."

	def _simsimi(self, word):
		key = ''
		url = 'http://sandbox.api.simsimi.com/request.p?key=%s&lc=ch&ft=0.0&text=%s' % (key, word)
		r = requests.get(url)
		ans = r.json()
		if ans['result'] == '100': return ans['response']
		else: return '你在说什么，风太大听不清列'

	def _searchContent(self, key, content, fmat = 'attr'):
		if fmat == 'attr':
			pm = re.search(key+'\s?=\s?"([^"<]+)"', content)
			if pm: return pm.group(1)
		elif fmat == 'xml':
			pm=re.search('<{0}>([^<]+)</{0}>'.format(key),content)
			if pm: return pm.group(1)
		return '未知'

if __name__ == '__main__':
	webwx = WebWeixin()
	webwx.start()
