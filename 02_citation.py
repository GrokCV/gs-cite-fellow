import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import json
import sys
import re
from utils import load_json, save_json
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import random


def main():
    config = load_json("config.json")
    start_article_id = int(sys.argv[1])
    d = open_browser()
    articles = load_json("data/articles.json")
    new_articles = articles.copy()
    citation_threshold = config.get("citation_threshold", 0)
    citation_limit = config.get("citation_limit", 1000000)
    print(citation_threshold, citation_limit)
    for article_id, info in enumerate(articles):
        if article_id < start_article_id:
            continue
        if info["cites"] < citation_threshold or info["cites"] > citation_limit:
            continue
        base_url = info["cite_url"]
        name = info["name"]
        get_all_cite_name_list(d, base_url, name, article_id, new_articles)


def get_all_cite_name_list(d, base_url, name, article_id, new_articles):
    # 加载配置文件获取 citation_since_year
    config = load_json("config.json")
    citation_since_year = config.get("citation_since_year", 0)

    all_cite_info_list = []
    for start in range(0, 100000, 10):
        print("Page {}".format(start // 10))
        url = get_specify_url(base_url, start)

        # 添加重试机制
        max_retries = 3
        for retry in range(max_retries):
            try:
                enter_url(d, url)

                # 添加随机延迟，模拟人类行为
                delay = random.uniform(0.5, 1.5)
                print(f"等待 {delay:.2f} 秒...")
                time.sleep(delay)

                cite_info_list = get_cite_name_list(d)

                # 如果成功获取到数据，跳出重试循环
                if cite_info_list:
                    break

                # 如果没有获取到数据但不是因为到达末页，可能是被反爬
                if retry < max_retries - 1:
                    print(
                        f"未获取到数据，等待更长时间后重试 ({retry+1}/{max_retries})..."
                    )
                    time.sleep(random.uniform(1, 2))  # 更长的等待时间
            except Exception as e:
                print(f"发生错误: {e}, 重试 ({retry+1}/{max_retries})...")
                if retry < max_retries - 1:
                    time.sleep(random.uniform(1, 2))

        # 如果重试后仍然没有数据，可能是到达了末页
        if len(cite_info_list) == 0:
            print("没有更多数据，可能已到达末页")
            break

        # 过滤出符合年份要求的引用
        filtered_cite_info_list = [
            info
            for info in cite_info_list
            if info["year"] is not None and info["year"] >= citation_since_year
        ]

        if filtered_cite_info_list:
            print(
                f"获取到 {len(cite_info_list)} 条引用，其中 {len(filtered_cite_info_list)} 条符合年份要求（>= {citation_since_year}）"
            )
            all_cite_info_list.extend(filtered_cite_info_list)
        else:
            print(
                f"获取到 {len(cite_info_list)} 条引用，但没有符合年份要求（>= {citation_since_year}）的数据"
            )

        # 每处理一页就保存一次结果，避免中途失败导致数据丢失
        new_articles[article_id]["cite_list"] = []
        for cite_info in all_cite_info_list:
            new_articles[article_id]["cite_list"].append(
                {"title": cite_info["title"], "year": cite_info["year"]}
            )
            print(f"{cite_info['title']} ({cite_info['year']})")
        save_json(new_articles, "data/articles.json")

        # 每页之间添加随机延迟，避免频繁请求
        if len(cite_info_list) > 0:  # 如果还有下一页
            delay = random.uniform(1, 2)
            print(f"准备获取下一页，等待 {delay:.2f} 秒...")
            time.sleep(delay)


def open_browser():
    print("start openning browser")
    d = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    d.set_window_size(1400, 800)
    print("finish openning browser")
    return d


def get_specify_url(base_url, start):
    url = base_url.replace("oi=bibs", "start={}".format(start))
    return url


def enter_url(d, url):
    print("开始访问网址", url)

    # 添加用户代理，模拟正常浏览器
    d.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    # 访问页面
    d.get(url)

    # 随机延迟，模拟人类行为
    base_delay = random.uniform(0.5, 1)
    print(f"基础等待 {base_delay:.2f} 秒...")
    time.sleep(base_delay)

    # 模拟人类滚动行为
    try:
        # 随机滚动几次页面
        scroll_count = random.randint(1, 2)
        for i in range(scroll_count):
            # 随机滚动距离
            scroll_amount = random.randint(300, 700)
            d.execute_script(f"window.scrollBy(0, {scroll_amount});")
            scroll_delay = random.uniform(0.2, 0.5)
            time.sleep(scroll_delay)

        # 随机滚回顶部
        if random.random() > 0.5:
            d.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.2, 0.5))
    except Exception as e:
        print(f"滚动页面时出错: {e}")

    print("完成访问网址", url)
    check_verification_code(d)


def check_verification_code(d):
    print("开始检查验证码...")
    max_wait_time = 60  # 最长等待1分钟
    start_time = time.time()

    while True:
        find_code = False

        # 检查各种可能的验证码元素
        try:
            content = d.find_element(by=By.ID, value="gs_captcha_f")
            find_code = True
            print("发现验证码表单 (gs_captcha_f)")
        except selenium.common.exceptions.NoSuchElementException:
            pass

        try:
            content = d.find_element(by=By.ID, value="recaptcha")
            find_code = True
            print("发现 reCAPTCHA (recaptcha)")
        except selenium.common.exceptions.NoSuchElementException:
            pass

        try:
            content = d.find_element(by=By.CLASS_NAME, value="g-recaptcha")
            find_code = True
            print("发现 reCAPTCHA (g-recaptcha)")
        except selenium.common.exceptions.NoSuchElementException:
            pass

        # 如果找到验证码
        if find_code:
            elapsed_time = time.time() - start_time
            remaining_time = max_wait_time - elapsed_time

            if remaining_time <= 0:
                print("等待验证码输入超时，继续执行...")
                break

            print(f"请在浏览器中完成验证码！剩余等待时间: {remaining_time:.0f} 秒")
            print("完成验证后，程序将自动继续")
            time.sleep(1)  # 每1秒检查一次
        else:
            print("未发现验证码，继续执行")
            break

    print("验证码检查完成")


def get_cite_name_list(d):
    text = d.find_element(By.XPATH, "//*").get_attribute("outerHTML")
    soup = BeautifulSoup(text, "html.parser")
    main_element = soup.find(name="div", attrs={"id": "gs_res_ccl_mid"})

    # 如果找不到主元素，尝试其他可能的元素ID
    if main_element is None:
        main_element = soup.find(name="div", attrs={"id": "gs_res_ccl_mid"})
        if main_element is None:
            main_element = soup.find(name="div", attrs={"id": "gs_ccl"})
            if main_element is None:
                main_element = soup.find(name="div", attrs={"id": "gs_res_ccl"})
                if main_element is None:
                    # 如果仍然找不到，打印页面内容以便调试
                    print("无法找到文章列表元素，可能Google Scholar页面结构已更改")
                    # 返回空列表
                    return []

    articles = main_element.find_all(name="div", attrs={"class": "gs_r"})
    # 如果找不到gs_r类的元素，尝试其他可能的类名
    if not articles:
        articles = main_element.find_all(name="div", attrs={"class": "gs_ri"})
    if not articles:
        articles = main_element.find_all(name="div", attrs={"class": "gs_or"})

    cite_info_list = []
    for article in articles:
        try:
            # 尝试找到标题元素
            title_elem = article.find(name="h3", attrs={"class": "gs_rt"})
            if title_elem is None:
                title_elem = article.find(name="h3", attrs={"class": "gs_ti"})

            # 尝试找到年份信息
            year = None
            footer_elem = article.find(name="div", attrs={"class": "gs_a"})
            if footer_elem:
                footer_text = footer_elem.text
                # 年份通常在文本的末尾，格式为四位数字
                year_match = re.search(r"(\d{4})", footer_text)
                if year_match:
                    year = int(year_match.group(1))

            if title_elem:
                name = title_elem.text
                cite_info = {"title": name, "year": year}
                cite_info_list.append(cite_info)
            else:
                print("无法找到文章标题元素")
        except Exception as e:
            print(f"处理文章时出错: {e}")

    return cite_info_list


if __name__ == "__main__":
    main()
