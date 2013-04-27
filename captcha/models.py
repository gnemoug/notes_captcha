from captcha.conf import settings as captcha_settings
from django.db import models
from django.conf import settings
import datetime
import random
import time
#This module provides various time-related functions. For related functionality, see also the datetime and calendar modules.
import unicodedata

#unicodedata:除了实现输入输出之外, 使用 Unicode 的程序必然会有测试 Unicode 字符属性的需要（是否大小写、是否数字、是否空白等等）。 unicodedata 模块提供了这些 unicode字符数据库。. 常规字符属性可以通过 unicodedata.category(c) 函数得到. 例如, unicodedata.category(u"A") 返回 'Lu', 表示这个字符是一个大写字符。更多关于Unicode 字符数据库及 unicodedata 模块的细节

# Heavily based on session key generation in Django
# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange
    #Return a randomly selected element from range(start, stop, step). This is equivalent to choice(range(start, stop, step)), but doesn’t actually build a range object.
MAX_RANDOM_KEY = 18446744073709551616L     # 2 << 63


try:
    import hashlib  # sha for Python 2.5+
except ImportError:
    import sha  # sha for Python 2.4 (deprecated in Python 2.6)
    hashlib = False


def get_safe_now():
    try:
        from django.utils.timezone import utc
        if settings.USE_TZ:
            return datetime.datetime.utcnow().replace(tzinfo=utc)
    except:
        pass
    return datetime.datetime.now()


class CaptchaStore(models.Model):
    challenge = models.CharField(blank=False, max_length=32)
    response = models.CharField(blank=False, max_length=32)
    hashkey = models.CharField(blank=False, max_length=40, unique=True)
    expiration = models.DateTimeField(blank=False)

    def save(self, *args, **kwargs):
        self.response = self.response.lower()
        if not self.expiration:
            #self.expiration = datetime.datetime.now() + datetime.timedelta(minutes=int(captcha_settings.CAPTCHA_TIMEOUT))
            #########设置过期日期############
            self.expiration = get_safe_now() + datetime.timedelta(minutes=int(captcha_settings.CAPTCHA_TIMEOUT))
        #############用于产生加密hashkey###########
        if not self.hashkey:
            key_ = unicodedata.normalize('NFKD', str(randrange(0, MAX_RANDOM_KEY)) + str(time.time()) + unicode(self.challenge)).encode('ascii', 'ignore') + unicodedata.normalize('NFKD', unicode(self.response)).encode('ascii', 'ignore')
            if hashlib:
                self.hashkey = hashlib.sha1(key_).hexdigest()
            else:
                self.hashkey = sha.new(key_).hexdigest()
            del(key_)
        super(CaptchaStore, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.challenge

    def remove_expired(cls):
        cls.objects.filter(expiration__lte=get_safe_now()).delete()
    remove_expired = classmethod(remove_expired)
