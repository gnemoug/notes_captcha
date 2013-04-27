from captcha.conf import settings
from captcha.models import CaptchaStore
from cStringIO import StringIO
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
import os
import random
import re
import tempfile

try:
    import Image
    import ImageDraw
    import ImageFont
except ImportError:
    from PIL import Image, ImageDraw, ImageFont


NON_DIGITS_RX = re.compile('[^\d]')


def captcha_image(request, key):
    store = get_object_or_404(CaptchaStore, hashkey=key)
    text = store.challenge

    #获取字体对应的文件
    if settings.CAPTCHA_FONT_PATH.lower().strip().endswith('ttf'):
        font = ImageFont.truetype(settings.CAPTCHA_FONT_PATH, settings.CAPTCHA_FONT_SIZE)
    else:
        font = ImageFont.load(settings.CAPTCHA_FONT_PATH)

#获取最终要生成的图片的基础模板，其中其大小合适，注意若是CAPTCHA_FONT_SIZE过大，则会发生错误。。。。注意。。。。，而且此时不包含文本数据
    size = font.getsize(text)
    size = (size[0] * 2, int(size[1] * 1.2))
    image = Image.new('RGB', size, settings.CAPTCHA_BACKGROUND_COLOR)

#sub( pattern, repl, string[, count]) 
#   repl可以时候字符串，也可以式函数
#   当repl是字符串的时候，
#   就是把string 内符合pattern的子串，用repl替换了
#   
#   当repl是函数的时候，对每一个在string内的，不重叠的，匹配pattern
#   的子串，调用repl（substring），然后用返回值替换substring

    try:
        PIL_VERSION = int(NON_DIGITS_RX.sub('', Image.VERSION))
    except:
        PIL_VERSION = 116
    #增加x轴字母之间的字符间距
    xpos = 2
#punctution :标点
    charlist = []
    for char in text:
        if char in settings.CAPTCHA_PUNCTUATION and len(charlist) >= 1:
            charlist[-1] += char
        else:
            charlist.append(char)
    for char in charlist:
        fgimage = Image.new('RGB', size, settings.CAPTCHA_FOREGROUND_COLOR)
        charimage = Image.new('L', font.getsize(' %s ' % char), '#000000')
        chardraw = ImageDraw.Draw(charimage)
        chardraw.text((0, 0), ' %s ' % char, font=font, fill='#ffffff')
        if settings.CAPTCHA_LETTER_ROTATION:
            if PIL_VERSION >= 116:
                charimage = charimage.rotate(random.randrange(*settings.CAPTCHA_LETTER_ROTATION), expand=0, resample=Image.BICUBIC)
            else:
                charimage = charimage.rotate(random.randrange(*settings.CAPTCHA_LETTER_ROTATION), resample=Image.BICUBIC)
        charimage = charimage.crop(charimage.getbbox())
        maskimage = Image.new('L', size)

        maskimage.paste(charimage, (xpos, 4, xpos + charimage.size[0], 4 + charimage.size[1]))
        size = maskimage.size
        #使用蒙板，将图像绘制到指定的图像中去
        image = Image.composite(fgimage, image, maskimage)
        xpos = xpos + 2 + charimage.size[0]

    image = image.crop((0, 0, xpos + 1, size[1]))
    draw = ImageDraw.Draw(image)

#为了防止识别，则调用加入杂音函数，实现了在图像上加点和加弧线及直线的干扰
    for f in settings.noise_functions():
        draw = f(draw, image)
    #在原来基础上加了滤镜效果
    for f in settings.filter_functions():
        image = f(image)
#使用stringio则操作全部在内存中，减少了高耗资源的文件读写操作
    out = StringIO()
    image.save(out, "PNG")
    out.seek(0)

    response = HttpResponse()
    response['Content-Type'] = 'image/png'
    response.write(out.read())

    return response


def captcha_audio(request, key):
    if settings.CAPTCHA_FLITE_PATH:
        store = get_object_or_404(CaptchaStore, hashkey=key)
        text = store.challenge
        if 'captcha.helpers.math_challenge' == settings.CAPTCHA_CHALLENGE_FUNCT:
            text = text.replace('*', 'times').replace('-', 'minus')
        else:
            text = ', '.join(list(text))
        path = str(os.path.join(tempfile.gettempdir(), '%s.wav' % key))
        cline = '%s -t "%s" -o "%s"' % (settings.CAPTCHA_FLITE_PATH, text, path)
        os.popen(cline).read()
        if os.path.isfile(path):
            response = HttpResponse()
            f = open(path, 'rb')
            response['Content-Type'] = 'audio/x-wav'
            response.write(f.read())
            f.close()
            os.unlink(path)
            return response
    raise Http404
