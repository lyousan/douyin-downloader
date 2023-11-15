import json
import os
import re

import requests

from playwright.sync_api import Page, sync_playwright
from config import *


class DouyinVideoSpider:
    def __init__(self, page: Page, save_path):
        self.page = page
        self.save_path = save_path
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

    def open_page(self, url):
        retry = 3
        while retry > 0:
            try:
                self.page.goto(url=url, wait_until="load")
                break
            except Exception as e:
                print(e)
                retry -= 1
                if retry > 0:
                    print(f"打开页面失败，重试 {retry} 次")
                    continue
                else:
                    raise Exception("打开页面失败，请重试")

    def parse_by_js(self):
        """
        从js中提取已经失效
        :return:
        """
        url = self.page.evaluate('window.getSpecValue(SSR_RENDER_DATA,"playApi")')
        if url.startswith("//"):
            url = "https:" + url
        return url

    def download(self, url, filename):
        print(f"开始下载 {url} ......")
        r = requests.get(url=url, stream=True)
        # filename = str(int(time.time() * 1000)) + ".mp4"
        filename += ".mp4"
        with open(self.save_path + "/" + filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"下载完成，保存在 {self.save_path}/{filename}")

    def parse_by_api(self):
        with self.page.expect_response(
            lambda r: "aweme/detail" in r.url
            and "0" != r.header_value("content-length"),
            timeout=0,
        ) as response:
            res = response.value.text()
            data = json.loads(res)
            print(data)
            video_url = data["aweme_detail"]["video"]["play_addr"]["url_list"][0]
            title = data["aweme_detail"]["preview_title"]
            return (video_url, title)

    def login(self):
        self.page.goto(url="https://www.douyin.com/", wait_until="load")
        try:
            if not self.page.is_visible("//*[text()='登录'][1]"):
                # 已登录
                return
            login_modal = self.page.locator("#login-pannel")
            if not login_modal.is_visible():
                # 点击登录按钮，弹出登录框
                self.page.locator("//*[text()='登录'][1]").click()
            print("请登录.....")
            # 等待登录框消失
            login_modal.wait_for(timeout=24 * 60 * 60 * 1000, state="hidden")
        except TimeoutError as e:
            print("登录超时")

    def run(self, share_url):
        url_reg = re.compile(
            "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        share_url = re.findall(url_reg, share_url)
        if len(share_url) == 0:
            print("链接格式不正确，请重新输入")
            return
        share_url = share_url[0]
        if share_url.find("v.douyin.com") == -1:
            print("链接格式不正确，请重新输入")
            return
        print("正在解析链接，请稍后......")
        print("遇到验证码请及时处理......")
        self.open_page(share_url)
        video_url, filename = self.parse_by_api()
        self.page.context.storage_state(path=storage_path)
        print("视频链接如下：")
        print(video_url)
        self.download(video_url, filename)
        print("=" * 50)


def create_spider(pw: sync_playwright, headless: bool = True, channel: str = "chrome"):
    browser = pw.chromium.launch(headless=headless, channel=channel)
    context = browser.new_context(storage_state=storage_path)
    context.add_init_script(
        'window.getSpecValue=function(obj,key){if (obj === undefined || obj === null) return obj;if(obj&&obj[key]){return obj[key]}let keys=Object.keys(obj);let res=undefined;for(let i=0;i<keys.length;i++){let k=obj[keys[i]];if(typeof k==="object"&&k!=null){res=window.getSpecValue(k,key);if(res)return res}}return res}'
    )
    context.add_init_script("stealth.min.js")
    page = context.new_page()
    return DouyinVideoSpider(page, os.path.abspath(video_path)), browser


def init_resources():
    if not os.path.exists(storage_path):
        with open(storage_path, "w") as f:
            f.write("{}")
    if not os.path.exists(video_path):
        os.makedirs(video_path)


if __name__ == "__main__":
    print("本工具仅供学习交流使用，严禁用于商业用途")
    print("准备中，请稍后......")
    init_resources()
    with sync_playwright() as pw:
        spider, browser = create_spider(pw, headless=False)
        spider.login()
        print("欢迎使用抖音视频下载工具，输入q回车退出")
        while True:
            print("请将作品的分享链接粘贴到此处后回车：")
            share_url = input()
            if share_url == "q":
                break
            spider.run(share_url)
