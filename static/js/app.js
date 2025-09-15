// app.js

// 验证函数
const validations = {
    username: (value) => !value ? '请输入账号！' : '',
    name: (value) => {
        if (!value) return '请输入账号！';
        if (!/^[a-zA-Z0-9]+$/.test(value)) return '账号只能包含英文和数字！';
        return '';
    },
    email: (value) => {
        if (!value) return '请输入邮箱！';
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return '请输入有效的邮箱地址！';
        return '';
    },
    qq: (value) => {
        if (!value) return '请输入QQ！';
        if (!/^\d{5,11}$/.test(value)) return '请输入有效的QQ号码！';
        return '';
    },
    password: (value) => {
        if (!value) return '请输入密码！';
        if (value.length < 6) return '密码长度至少为6个字符！';
        return '';
    },
    code: (value) => !value ? '请输入验证码！' : ''
};

// 当 DOM 加载完成时执行的函数
document.addEventListener('DOMContentLoaded', function () {
    updateFooterContent();
    setupClipboard();
    initializeForms();
    initializePasswordToggle();
    initializeApiUsageChart();
    fetchBackgroundImage();
    initializeFlashAlerts(); // 使用简单的Alert自动消失
    initializeRememberMe(); // 初始化记住我功能
});

// 更新页脚内容
function updateFooterContent() {
    const currentYear = new Date().getFullYear();
    const currentYearElement = document.getElementById("current-year");
    if (currentYearElement) currentYearElement.textContent = currentYear;
}

// 设置剪贴板功能
function setupClipboard() {
    if (typeof ClipboardJS !== 'undefined') {
        new ClipboardJS('.copy-btn');
    }
}

// 初始化表单
function initializeForms() {
    initializeForm('loginForm', ['username', 'password', 'code']);
    initializeForm('registerForm', ['name', 'email', 'password', 'qq']);
    // 初始化时获取验证码
    refreshCaptcha();
}

// 初始化单个表单
function initializeForm(formId, inputIds) {
    const form = document.getElementById(formId);
    if (form) {
        inputIds.forEach(id => {
            const input = document.getElementById(id);
            const errorElement = document.getElementById(`${id}Error`);
            if (input && errorElement) {
                input.addEventListener('blur', () => validateInput(input, errorElement, validations[id]));
                input.addEventListener('input', () => {
                    if (input.dataset.touched) validateInput(input, errorElement, validations[id]);
                });
            }
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            let hasError = false;

            inputIds.forEach(id => {
                const input = document.getElementById(id);
                const errorElement = document.getElementById(`${id}Error`);
                if (input && errorElement) {
                    input.dataset.touched = 'true';
                    validateInput(input, errorElement, validations[id]);
                    if (errorElement.textContent) hasError = true;
                }
            });

            if (!hasError) {
                showLoadingIndicator(formId === 'loginForm' ? '登录中...' : '注册中...');
                this.submit();
            }
        });
    }
}

// 验证输入
function validateInput(input, errorElement, validationFunction) {
    const value = input.value.trim();
    const error = validationFunction(value);
    if (error && input.dataset.touched) {
        input.classList.add('is-invalid');
        errorElement.textContent = error;
    } else {
        input.classList.remove('is-invalid');
        errorElement.textContent = '';
    }
}

// 显示加载指示器
function showLoadingIndicator(message) {
    const submitButton = document.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${message}`;
    }
}

// 密码可见性切换
function initializePasswordToggle() {
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');
    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', function (e) {
            e.preventDefault();
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.querySelector('svg').classList.toggle('icon-tabler-eye');
            this.querySelector('svg').classList.toggle('icon-tabler-eye-off');
        });
    }
}

// 刷新验证码
function refreshCaptcha() {
    const img = document.getElementById('captchaImage');
    const captchaIdInput = document.getElementById('captcha_id');
    if (img && captchaIdInput) {
        const timestamp = new Date().getTime();
        fetch("/auth/captcha?t=" + timestamp)
            .then(response => {
                if (!response.ok) {
                    throw new Error('验证码获取失败');
                }
                const captchaId = response.headers.get('X-Captcha-ID');
                if (!captchaId) {
                    throw new Error('验证码ID未找到');
                }
                captchaIdInput.value = captchaId;
                return response.blob();
            })
            .then(blob => {
                const imageUrl = URL.createObjectURL(blob);
                img.src = imageUrl;
                // 释放之前的 URL 对象
                if (img.dataset.prevUrl) {
                    URL.revokeObjectURL(img.dataset.prevUrl);
                }
                img.dataset.prevUrl = imageUrl;
            })
            .catch(error => {
                console.error('验证码加载失败:', error);
                img.alt = '验证码加载失败，点击重试';
            });
    }
}

// 初始化 API 使用图表
function initializeApiUsageChart() {
    const chartElement = document.getElementById('chart-api-usage');
    if (chartElement && typeof ApexCharts !== 'undefined') {
        const chartDates = JSON.parse(chartElement.dataset.dates);
        const chartCounts = JSON.parse(chartElement.dataset.counts);
        const options = {
            chart: {
                type: 'area',
                height: 300,
                zoom: {enabled: false}
            },
            dataLabels: {enabled: false},
            stroke: {curve: 'smooth'},
            series: [{name: 'API调用次数', data: chartCounts}],
            xaxis: {
                type: 'datetime',
                categories: chartDates,
                labels: {
                    formatter: (value, timestamp) => {
                        const date = new Date(timestamp);
                        const month = '一二三四五六七八九十十一十二'.charAt(date.getMonth());
                        return `${month}月${date.getDate()}日`;
                    }
                }
            },
            tooltip: {
                x: {
                    formatter: (value) => {
                        const date = new Date(value);
                        const year = date.getFullYear();
                        const month = '一二三四五六七八九十十一十二'.charAt(date.getMonth());
                        const day = date.getDate();
                        return `${year}年${month}月${day}日`;
                    }
                },
            },
            fill: {
                type: 'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.7,
                    opacityTo: 0.9,
                    stops: [0, 100]
                }
            }
        };

        new ApexCharts(chartElement, options).render();
    }
}

// 获取背景图片
function fetchBackgroundImage() {
    const backgroundDiv = document.getElementById('backgroundDiv');
    if (backgroundDiv) {
        fetch('https://api.makuo.cc/api/get.img.bing?token=ik-uxz8ZPMsHLQgQ46PICw')
            .then(response => response.json())
            .then(data => {
                const randomImageUrl = data.data[Math.floor(Math.random() * data.data.length)].image_url;
                backgroundDiv.style.backgroundImage = `url(${randomImageUrl})`;
            })
            .catch(error => console.error('Error:', error));
    }
}
// 初始化Flash Alert自动消失
function initializeFlashAlerts() {
    // 获取所有alert元素
    const alertElements = document.querySelectorAll('.alert-dismissible');

    alertElements.forEach(function(alertElement) {
        // 添加鼠标悬停暂停功能
        let timeoutId;
        let isPaused = false;

        // 开始计时
        function startTimer() {
            if (!isPaused) {
                timeoutId = setTimeout(function() {
                    // 添加淡出动画
                    alertElement.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
                    alertElement.style.opacity = '0';
                    alertElement.style.transform = 'translateX(100%)';

                    // 动画完成后移除元素
                    setTimeout(function() {
                        if (alertElement.parentNode) {
                            alertElement.remove();
                        }
                    }, 500);
                }, 3000);
            }
        }

        // 鼠标悬停暂停
        alertElement.addEventListener('mouseenter', function() {
            isPaused = true;
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        });

        // 鼠标离开继续
        alertElement.addEventListener('mouseleave', function() {
            isPaused = false;
            startTimer();
        });

        // 开始计时
        startTimer();
    });
}

// 初始化记住我功能
function initializeRememberMe() {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const rememberCheckbox = document.querySelector('input[name="remember_me"]');

    // 如果不在登录页面，直接返回
    if (!loginForm || !usernameInput || !passwordInput || !rememberCheckbox) {
        return;
    }

    // 页面加载时，检查是否有保存的登录信息
    loadRememberedCredentials();

    // 表单提交时，处理记住我功能
    loginForm.addEventListener('submit', function(e) {
        handleRememberMe();
    });

    // 记住我复选框变化时的处理
    rememberCheckbox.addEventListener('change', function() {
        if (!this.checked) {
            // 取消勾选时，清除保存的信息
            clearRememberedCredentials();
        }
    });
}

// 加载保存的登录凭据
function loadRememberedCredentials() {
    try {
        const savedCredentials = localStorage.getItem('WebBot_remember_credentials');
        if (savedCredentials) {
            const credentials = JSON.parse(savedCredentials);

            // 解码并填充用户名和密码
            if (credentials.username) {
                document.getElementById('username').value = atob(credentials.username);
            }
            if (credentials.password) {
                document.getElementById('password').value = atob(credentials.password);
            }

            // 勾选记住我复选框
            const rememberCheckbox = document.querySelector('input[name="remember_me"]');
            if (rememberCheckbox) {
                rememberCheckbox.checked = true;
            }
        }
    } catch (error) {
        // 如果解析失败，清除损坏的数据
        clearRememberedCredentials();
    }
}

// 处理记住我功能
function handleRememberMe() {
    const rememberCheckbox = document.querySelector('input[name="remember_me"]');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');

    if (rememberCheckbox && rememberCheckbox.checked) {
        // 保存登录凭据
        const credentials = {
            username: btoa(usernameInput.value), // Base64编码
            password: btoa(passwordInput.value), // Base64编码
            timestamp: Date.now()
        };

        try {
            localStorage.setItem('WebBot_remember_credentials', JSON.stringify(credentials));
        } catch (error) {
            console.warn('无法保存登录凭据:', error);
        }
    } else {
        // 清除保存的凭据
        clearRememberedCredentials();
    }
}

// 清除保存的登录凭据
function clearRememberedCredentials() {
    try {
        localStorage.removeItem('WebBot_remember_credentials');
    } catch (error) {
        console.warn('无法清除保存的凭据:', error);
    }
}