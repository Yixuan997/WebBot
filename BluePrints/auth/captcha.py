"""
@Project：WebBot 
@File   ：captcha.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/8 09:30 
"""
import random
import uuid
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from flask import make_response

from Database.Redis import set_value

# 字体路径
FONT_PATH = "static/fonts/DejaVuSans.ttf"


# 生成随机字符串作为验证码
def generate_captcha():
    # 排除容易混淆的字符
    captcha_text = ''.join(random.choices('23456789ABCDEFGHJKLMNPQRSTUVWXYZ', k=5))
    captcha_id = str(uuid.uuid4())

    img = Image.new('RGB', (120, 40), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    # 尝试使用字体，如果失败则使用默认字体
    try:
        font = ImageFont.truetype(FONT_PATH, 24)
    except:
        try:
            # 尝试系统字体
            font = ImageFont.truetype('arial.ttf', 24)
        except:
            font = ImageFont.load_default()

    # 绘制文字（添加颜色变化）
    for i, char in enumerate(captcha_text):
        x = 20 + i * 20 + random.randint(-3, 3)
        y = 8 + random.randint(-3, 3)
        color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
        d.text((x, y), char, fill=color, font=font)

    # 添加随机线条
    for _ in range(3):
        x1, y1 = random.randint(0, 120), random.randint(0, 40)
        x2, y2 = random.randint(0, 120), random.randint(0, 40)
        color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        d.line([(x1, y1), (x2, y2)], fill=color, width=1)

    # 添加随机点
    for _ in range(50):
        x, y = random.randint(0, 120), random.randint(0, 40)
        color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        d.point([x, y], fill=color)

    output = BytesIO()
    img.save(output, 'PNG')
    output.seek(0)

    # 将验证码存储在 Redis 中
    set_value(f'captcha:{captcha_id}', captcha_text.lower(), 300)  # 5分钟过期

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'image/png'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['X-Captcha-ID'] = captcha_id  # 在响应头中返回验证码ID

    return resp
