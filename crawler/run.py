#coding=utf-8
import datetime
import re

import requests
from lxml import etree
from model import Top

url = 'http://weixin.sogou.com/'
req = requests.get(url)

page = etree.HTML(req._content)
# ----------- 获取微信滚动 banner新闻 start -----------
wx_news = page.xpath('//div[@class="wx-news"]')
today = datetime.datetime.today()
for news in wx_news:
    news_ele = news.getchildren()
    title_ele = news_ele[0].getchildren()[0]
    top = Top()
    top.title = title_ele.text
    top.top_link = title_ele.attrib.get('href', '')
    top.desc = news_ele[1].getchildren()[0].text
    top.profile = news.getchildren()[2].getchildren()[0].getchildren()[0].text
    top.profile_link = news.getchildren()[2].getchildren()[0].attrib.get('href', '')
    top.publish_time = news.getchildren()[2].text
    publish_time = etree.tostring(news.getchildren()[2].getchildren()[0]).split('</span>')[0].split('</a>')[1].strip()
    if publish_time.find(';') != -1:
        top.publish_time = '%s-%s-%s' % (today.year, publish_time.split(';')[0].split('&')[0], publish_time.split(';')[1].split('&')[0])
    else:
        top.publish_time = '%s-%s-%s %s' % (today.year, today.month, today.day, publish_time)
    #print top
    del news
# ----------- 获取微信滚动 banner新闻 end -----------

# ----------- 微信热搜榜 start -----------
wx_ph = page.xpath('//div[@class="wx-ph"]//a')
for item in wx_ph:
    print item.attrib.get('title'), item.attrib.get('href')
# ----------- 微信热搜榜 end -----------

# ----------- 订阅热词 start -----------
re_box = page.xpath('//div[@class="re-box"]//span')
for item in re_box:
    print item.text
# ----------- 订阅热词 end -----------

# ----------- 最热收藏 start -----------
sc_news = page.xpath('//ul[@class="sc_news"]//li')
for item in sc_news:
    news_img = item.find('.//img')
    tit = item.find('.//p[@class="tit"]//a')
    tit_profile = item.find('.//p[@class="time"]//a')
    tit_time = item.find('.//p[@class="time"]//span')

    img_src = news_img.attrib.get('src')
    title = tit.text
    link = tit.attrib.get('href')
    profile = tit_profile.text
    profile_link = tit_profile.attrib.get('href')
    pub_time = tit_time.text
    print title,pub_time

# ----------- 最热收藏 end -----------

# ----------- 最热内容 start -----------
# ----------- 最热内容 end -----------

# ----------- 分类 start -----------
cate = page.xpath('//ul[@id="pc_0_subd"]//li')
regx = re.compile(r'"^//d+$"')
for item in cate:
    content_img = item.find('.//div[@class="wx-img-box"]//img')

    profile = item.findall('.//div[@class="pos-wxrw"]//p')
    profile_logo = profile[0].find('.//img').attrib.get('src')
    profile_name = profile[1].attrib.get('title')
    profile_link = item.find('.//div[@class="pos-wxrw"]//a').attrib.get('href')
    profile_qrcode = item.find('.//div[@class="fxf"]//img').attrib.get('src')

    article = item.find('.//div[@class="wx-news-info2"]//a')
    title = article.text
    article_link = article.attrib.get('href')
    article_short = item.find('.//div[@class="wx-news-info2"]//a[@class="wx-news-info"]').text
    article_info = item.find('.//div[@class="s-p"]')
    read_count = etree.tostring(article_info, encoding='utf-8').split('<bb t="tm"')[0].split('</span>')
    count = re.findall(r'[0-9]+', read_count[-1].decode('utf-8'))[0]
    pub_time = item.find('.//div[@class="s-p"]//bb[@t="tm"]').attrib.get('v')


# ----------- 分类 end -----------