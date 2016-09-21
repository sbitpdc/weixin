#coding=utf-8
import datetime
import re

import requests
from lxml import etree

html = """
"""
url = 'http://mp.weixin.qq.com/s?src=3&timestamp=1468658532&ver=1&signature=CiQkznJRsrvadQct3RUIwf8vdtUpGzUD2qjAoB1fZpraz2qZJElk4tqJ9oG*SeegjKorF5D1-JsOnlnrDKclrWQd8LIO8OysBIzk7JHT1C*OGTU9XrCV7icUpnq8hJ*4izCxyUrOBXbQiaTW2HRxgHkyvJbHB7wGu7Llnu1emhs='
req = requests.get(url)
page = etree.HTML(req._content)
title = page.find('.//h2[@id="activity-name"]').text.strip()
js_content = page.xpath('//div[@id="js_content"]//p')
content = []
for item in js_content:
    text = item.xpath('string()')
    if text.strip() != '':
        content.append('<p>%s</p>' % text)
    # img = item.find('.//img')
    # if img is not None:
    #     content.append('<img src="%s">' % img.attrib.get('data-src'))

content = ''.join(content)

profile_qrcode = page.find('.//img[@id="js_pc_qr_code_img"]')
pub_time = page.find('.//em[@id="post-date"]')
post_user = page.find('.//a[@id="post-user"]')
print content