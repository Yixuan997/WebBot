# 工作流模板过滤器

## 这是什么？

在工作流中，你可以用 `{{xxx}}` 来显示变量的内容。

比如：
- `{{用户名}}` → 显示用户的名字
- `{{message}}` → 显示用户发送的消息

**过滤器**就是对这些变量做一些处理，比如：
- 把换行符去掉
- 把文字截断
- 设置默认值

## 怎么用？

在变量后面加一个 `|` ，然后写过滤器名字：

```
{{变量名|过滤器}}
```

还可以连续使用多个过滤器（从左到右执行）：

```
{{变量名|过滤器1|过滤器2}}
```

---

## 常用过滤器

### 1. replace - 替换内容

把某些字符替换成另外的字符。

**用法：** `replace('要替换的', '替换成的')`

**例子：**
```
# 把换行符替换成空格
{{title|replace('\n', ' ')}}

# 把“小明”替换成“小红”
{{message|replace('小明', '小红')}}
```

**输入输出：**
- 输入：`第一行\n第二行`
- 输出：`第一行 第二行`

---

### 2. default - 设置默认值

如果变量是空的，就用默认值代替。

**用法：** `default('默认值')`

**例子：**
```
# 如果用户名为空，显示“匿名用户”
{{用户名|default('匿名用户')}}

# 如果错误信息为空，显示“未知错误”
{{response_json.msg|default('未知错误')}}
```

---

### 3. trim - 去除首尾空格

去掉文字前后的空格和换行。

**例子：**
```
{{message|trim}}
```

**输入输出：**
- 输入：`  你好世界  `
- 输出：`你好世界`

---

### 4. truncate - 截断文字

如果文字太长，只显示前面一部分。

**用法：** `truncate(长度)`

**例子：**
```
# 只显示前20个字符
{{description|truncate(20)}}
```

**输入输出：**
- 输入：`这是一段很长很长很长很长的文字`
- 输出：`这是一段很长很长很长...`

---

### 5. upper / lower - 大小写转换

**例子：**
```
# 全部变大写
{{text|upper}}

# 全部变小写
{{text|lower}}
```

**输入输出：**
- `Hello` → upper → `HELLO`
- `Hello` → lower → `hello`

---

### 6. int - 转换为数字

把文字变成数字。

**例子：**
```
{{点赞数|int}}
```

---

### 7. length - 获取长度

获取文字的长度或列表的元素数量。

**例子：**
```
{{message|length}}
```

**输入输出：**
- 输入：`你好`
- 输出：`2`

---

### 8. urlencode - URL 编码

把文字转换成可以放在网址里的格式。

**例子：**
```
https://api.example.com/search?q={{keyword|urlencode}}
```

**输入输出：**
- 输入：`你好 世界`
- 输出：`%E4%BD%A0%E5%A5%BD%20%E4%B8%96%E7%95%8C`

---

### 9. json_safe - JSON 安全转义

在 **自定义端点节点** 的 JSON 参数中使用变量时，如果变量里有引号 `"` 或反斜杠 `\`，会导致 JSON 格式错误。

用这个过滤器可以自动处理这些特殊字符。

**例子：**
```
"title": "{{response_json.data.title|json_safe}}"
```

**输入输出：**
- 输入：`他说"你好"`
- 输出：`他说\"你好\"`

---

## 实战例子

### 例子 1：处理 API 返回的标题

API 返回的标题可能包含换行符，在发送消息时需要去掉：

```
{{response_json.data.title|replace('\n', ' ')}}
```

### 例子 2：处理可能为空的变量

如果描述为空，显示默认文字，并截断到 50 个字：

```
{{description|default('暂无描述')|truncate(50)}}
```

### 例子 3：在自定义端点中使用变量

在 endpoint 节点的 JSON 参数中，如果变量可能包含特殊字符：

```json
{
  "title": "{{response_json.data.title|replace('\n', ' ')|json_safe}}",
  "author": "{{response_json.data.author|json_safe}}"
}
```

### 例子 4：拼接 URL

```
https://api.example.com/search?keyword={{keyword|urlencode}}&page=1
```

---

## 全部过滤器列表

### 文字处理
| 过滤器 | 说明 | 例子 |
|--------|------|------|
| replace | 替换内容 | `{{x\|replace('a', 'b')}}` |
| default | 默认值 | `{{x\|default('空')}}` |
| trim | 去除首尾空格 | `{{x\|trim}}` |
| truncate | 截断 | `{{x\|truncate(20)}}` |
| upper | 转大写 | `{{x\|upper}}` |
| lower | 转小写 | `{{x\|lower}}` |
| capitalize | 首字母大写 | `{{x\|capitalize}}` |
| title | 每词首字母大写 | `{{x\|title}}` |
| length | 获取长度 | `{{x\|length}}` |
| reverse | 反转 | `{{x\|reverse}}` |
| first | 取第一个 | `{{x\|first}}` |
| last | 取最后一个 | `{{x\|last}}` |

### 数字处理
| 过滤器 | 说明 | 例子 |
|--------|------|------|
| int | 转整数 | `{{x\|int}}` |
| float | 转小数 | `{{x\|float}}` |
| round | 四舍五入 | `{{x\|round(2)}}` |
| abs | 绝对值 | `{{x\|abs}}` |

### 列表处理
| 过滤器 | 说明 | 例子 |
|--------|------|------|
| join | 连接成字符串 | `{{x\|join(', ')}}` |
| sort | 排序 | `{{x\|sort}}` |
| unique | 去重 | `{{x\|unique}}` |
| random | 随机选一个 | `{{x\|random}}` |

> 说明：模板环境没有内置 `split` 过滤器。需要分割字符串时，建议使用 `string_operation` 节点的 `split` 操作。

### 特殊处理
| 过滤器 | 说明 | 例子 |
|--------|------|------|
| urlencode | URL编码 | `{{x\|urlencode}}` |
| json_safe | JSON安全转义 | `{{x\|json_safe}}` |
| escape | HTML转义 | `{{x\|escape}}` |
| striptags | 去除HTML标签 | `{{x\|striptags}}` |
