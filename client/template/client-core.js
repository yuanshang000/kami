/* ==========================================================================
   License Client Core — 统一客户端核心逻辑
   职责：配置、API 调用、会话管理、心跳、日志、UI 渲染
   接入方通常只需要修改 CONFIG 对象，其余代码无需改动
   ========================================================================== */

/* ========================= 1. 配置 ========================= */
const CONFIG = {
  /* ---- 产品信息（每个接入产品改这里） ---- */
  product: {
    name: 'Nova Studio',
    version: 'v1.0.0',
    logoText: 'N',
    subtitle: '专业版 · 订阅授权',
  },

  /* ---- 服务器配置 ---- */
  server: {
    url: 'http://127.0.0.1:8000',
    productId: 'nova_studio',
    apiKey: '',   // 填入你产品的 api_key（管理后台「产品管理」可查看）
    /* 客户端版本号，用于服务端兼容性校验 */
    clientVersion: '1.0.0',
    requestTimeout: 12000,
  },

  /* ---- 行为开关：按需关闭不需要的功能 ---- */
  features: {
    /* 显示机器 ID 输入框（默认自动生成，一般不需要用户填） */
    showMachineId: false,
    /* 心跳间隔（秒），0 表示关闭心跳 */
    heartbeatInterval: 30,
    /* 是否显示日志面板 */
    showLog: true,
    /* 记住卡密到本地，下次自动验证 */
    rememberKey: true,
    /* 是否允许用户手动切换日间/夜间主题 */
    allowThemeToggle: true,
    /* 强制固定主题：填 'light' 或 'dark' 可禁用切换按钮；不填则默认日间并允许切换 */
    forceTheme: '',
    /* 跟随系统：填 true 时首次进入按系统偏好选择（注意仍默认回落到日间） */
    followSystem: false,
  },

  /* ---- 文案定制：把界面上的话改成你自己的 ---- */
  texts: {
    verifyTitle: '输入卡密以继续',
    verifyPlaceholder: 'XXXX-XXXX-XXXX-XXXX',
    verifyButton: '验证并进入',
    getKeyButton: '获取卡密',
    /* 关闭验证页时的确认文案 */
    closeConfirmTitle: '确认退出程序？',
    closeConfirmBody: '退出后需要重新输入卡密才能使用，已保存的输入不会被保留。',
    /* 顶号提示 */
    kickNotice: '若卡密为单机授权，验证时将自动踢掉其他正在使用该卡密的机器。',
    /* 注销授权确认 */
    logoutConfirmTitle: '确认退出授权？',
    logoutConfirmBody: '退出后当前设备将解除绑定，卡密可重新在其他机器上使用。',
    logoutButton: '退出授权',
    closeButton: '关闭程序',
    sessionLabel: '会话 ID',
    expireLabel: '到期时间',
  },

  /* ---- 获取卡密：二选一 ----
     mode: 'link'    → 浏览器打开链接
     mode: 'contact' → 显示文本说明，其中的联系方式可点击复制
  */
  getKey: {
    mode: 'contact',
    /* mode='link' 时使用 */
    url: 'https://example.com/buy',
    buttonText: '获取卡密',
    /* mode='contact' 时使用 */
    title: '购买卡密',
    desc: '添加客服微信获取卡密，联系方式点击即可复制：',
    /* 需要高亮并可复制的字段，type 必须是 'contact' 才会渲染成可点击样式 */
    items: [
      { label: '客服微信', value: 'kami-support', type: 'contact' },
      { label: 'QQ 群', value: '888888888', type: 'contact' },
      { label: '购买链接', value: 'https://example.com/buy', type: 'link' },
    ],
  },
};

/* ========================= 2. 运行时状态 ========================= */
const state = {
  session: null,        // 当前会话数据
  machineId: '',
  heartbeatTimer: null,
  countdownTimer: null,
  logFilter: 'all',
  logEntries: [],
  view: 'verify',
  busy: false,
};

/* ========================= 3. 主题管理 ========================= */
const THEME_KEY = 'lc_theme';
/* 某些环境下 localStorage 访问会抛 SecurityError（隐私模式、存储被禁用、
   文档未完全就绪等）。这里做一层安全包装：读写失败时不抛错，
   并用内存兜底，保证同一次会话内主题依然稳定。 */
const themeStore = (() => {
  let memory = null;
  return {
    /* 存储不可用时只提示一次，不刷屏 */
    warnOnce() {
      if (themeStore._warned) return;
      themeStore._warned = true;
      console.warn('[license-client] localStorage 不可用，主题偏好仅在本次会话内生效');
    },
    get() {
      if (memory) return memory;
      try { return localStorage.getItem(THEME_KEY); }
      catch (e) { themeStore.warnOnce(); return null; }
    },
    set(value) {
      memory = value;
      try { localStorage.setItem(THEME_KEY, value); }
      catch (e) { themeStore.warnOnce(); }
    },
  };
})();

/** 读取用户偏好。优先级：forceTheme > 本地记忆 > 系统偏好 > 日间 */
function resolveInitialTheme() {
  const forced = CONFIG.features.forceTheme;
  if (forced === 'light' || forced === 'dark') return forced;
  const saved = themeStore.get();
  if (saved === 'light' || saved === 'dark') return saved;
  if (CONFIG.features.followSystem && window.matchMedia) {
    try {
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    } catch (e) { /* 老浏览器不支持 */ }
  }
  return 'light';
}

/** 应用主题到 <html> */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const btn = $('themeBtn');
  if (btn) {
    btn.title = theme === 'dark' ? '切换到日间主题' : '切换到夜间主题';
    btn.setAttribute('aria-label', btn.title);
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  themeStore.set(next);
  // 转个圈给个反馈，动画结束自动复位
  const btn = $('themeBtn');
  if (btn) {
    btn.classList.add('is-switching');
    setTimeout(() => btn.classList.remove('is-switching'), 200);
  }
  log('info', `已切换到${next === 'dark' ? '夜间' : '日间'}主题`);
}

/* ========================= 4. 工具函数 ========================= */
const $ = (id) => document.getElementById(id);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function pad(n) { return String(n).padStart(2, '0'); }

function fmtDateTime(input) {
  if (!input) return '-';
  const d = new Date(input);
  if (isNaN(d.getTime())) return String(input);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
         `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function fmtTime(input) {
  const d = input instanceof Date ? input : new Date(input);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/** 毫秒 → 「3天 04:22:11」形式 */
function fmtDuration(ms) {
  if (ms <= 0) return { text: '已过期', d: 0, h: 0, m: 0, s: 0, expired: true };
  const total = Math.floor(ms / 1000);
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  let text;
  if (d > 0) text = `${d}天 ${pad(h)}:${pad(m)}:${pad(s)}`;
  else text = `${pad(h)}:${pad(m)}:${pad(s)}`;
  return { text, d, h, m, s, expired: false };
}

/** 生成机器 ID：优先读取系统提供的真实标识 */
function resolveMachineId() {
  let mid = '';
  try {
    // Electron 等环境可注入真实硬件标识
    if (window.require && window.require('electron')) {
      const os = window.require('os');
      mid = `${os.hostname()}-${os.userInfo().username}`;
    }
  } catch (e) { /* 非 Electron 环境忽略 */ }
  if (!mid) {
    // 浏览器环境：用 localStorage 持久化一个随机 ID
    let saved = localStorage.getItem('lc_machine_id');
    if (!saved) {
      saved = 'M-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
      localStorage.setItem('lc_machine_id', saved);
    }
    mid = saved;
  }
  state.machineId = mid;
  const el = $('machineIdInput');
  if (el) el.value = mid;
  return mid;
}

/** 通用剪贴板，带多级降级，保证任何环境都能复制成功 */
function copyText(text) {
  // 优先使用异步剪贴板 API（需安全上下文 + 权限）
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
  }
  return Promise.resolve().then(() => legacyCopy(text));
}

/** 降级复制：execCommand 在部分环境会因元素不可见而失败，
    这里保证 textarea 在视口内且透明度极低而非 0，提高成功率。 */
function legacyCopy(text) {
  return new Promise((resolve, reject) => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:none;outline:none;box-shadow:none;background:transparent;opacity:0.01;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    if (ok) resolve();
    else reject(new Error('copy failed'));
  });
}

/* ========================= 4. 日志系统 ========================= */
const LOG_LIMIT = 300;

function log(level, message) {
  const entry = { time: new Date(), level, message: String(message) };
  state.logEntries.push(entry);
  if (state.logEntries.length > LOG_LIMIT) state.logEntries.shift();
  renderLog();
  const badge = $('logBadge');
  if (badge) {
    const hasErr = state.logEntries.some(e => e.level === 'error');
    badge.textContent = state.logEntries.length;
    badge.classList.toggle('has-error', hasErr);
  }
}

function logError(scope, err, extra) {
  const detail = extra ? ` ${extra}` : '';
  const msg = err && err.message ? err.message : String(err);
  log('error', `[${scope}] ${msg}${detail}`);
}

function renderLog() {
  const list = $('logList');
  if (!list) return;
  let entries = state.logEntries;
  if (state.logFilter === 'error') entries = entries.filter(e => e.level === 'error');
  else if (state.logFilter === 'api') entries = entries.filter(e => e.tag === 'api');

  if (!entries.length) {
    list.innerHTML = `<div class="lc-log-empty">暂无日志记录</div>`;
    return;
  }
  list.innerHTML = entries.map(e => {
    const tag = e.tag ? `<span class="lc-log-tag">${escapeHtml(e.tag)}</span>` : '';
    return `<div class="lc-log-item lv-${e.level}">
      <span class="lc-log-time">${fmtTime(e.time)}</span>
      <span class="lc-log-lv">${e.level}</span>
      <span class="lc-log-msg">${tag}${escapeHtml(e.message)}</span>
    </div>`;
  }).join('');
  list.parentElement.scrollTop = list.parentElement.scrollHeight;
}

/** 带 API 标签的日志，方便筛选出所有网络请求 */
function logApi(message, level = 'info') {
  const entry = { time: new Date(), level, message, tag: 'api' };
  state.logEntries.push(entry);
  if (state.logEntries.length > LOG_LIMIT) state.logEntries.shift();
  renderLog();
}

function clearLog() {
  state.logEntries = [];
  renderLog();
  const badge = $('logBadge');
  if (badge) { badge.textContent = '0'; badge.classList.remove('has-error'); }
  log('info', '日志已清空');
}

/* ========================= 5. API 层 ========================= */
/** 错误码 → 用户能看懂的话。服务端返回 message 为空时用这里兜底。 */
const ERROR_TEXT = {
  4001: '卡密无效',
  4002: '卡密不存在',
  4003: '卡密已过期，请续费后使用',
  4004: '卡密已被禁用，请联系客服',
  4005: '产品不匹配',
  4006: 'API Key 无效，请检查客户端配置',
  4007: '请求参数有误',
  4008: '签名验证失败',
  4009: '会话已失效，请重新验证卡密',
  4010: '会话已过期，请重新验证卡密',
  4013: '请求过于频繁，请稍后再试',
  4014: '客户端版本过低，请升级后使用',
  4015: '产品已停用',
};

class ApiError extends Error {
  constructor(code, message, requestId) {
    super(message);
    this.code = code;
    this.requestId = requestId;
  }
}

async function apiCall(path, { method = 'POST', body = null, query = null } = {}) {
  if (!CONFIG.server.apiKey) {
    logApi('未配置 API Key，跳过请求', 'warn');
    throw new ApiError(-1, '尚未配置 API Key，请先在配置中填写');
  }
  const base = CONFIG.server.url.replace(/\/$/, '');
  // GET 接口的参数必须走 query string，放 body 会被服务端判定为参数缺失
  const url = base + path + (query ? '?' + new URLSearchParams(query).toString() : '');
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + CONFIG.server.apiKey,
    'X-Client-Version': CONFIG.server.clientVersion,
  };
  if (CONFIG.server.productId) headers['X-Product-ID'] = CONFIG.server.productId;

  const started = Date.now();
  logApi(`→ ${method} ${path}`, 'info');

  let resp;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), CONFIG.server.requestTimeout);
    // GET 请求不带 body
    const init = { method, headers, signal: controller.signal };
    if (method !== 'GET' && body) init.body = JSON.stringify(body);
    resp = await fetch(url, init);
    clearTimeout(timer);
  } catch (e) {
    const msg = e.name === 'AbortError' ? '请求超时，请检查网络或服务器地址' : '网络连接失败，请检查服务器地址';
    logApi(`✗ ${method} ${path} — ${msg}`, 'error');
    throw new ApiError(-1, msg);
  }

  const cost = Date.now() - started;
  let data;
  try {
    data = await resp.json();
  } catch (e) {
    logApi(`✗ ${method} ${path} — 响应不是合法 JSON (HTTP ${resp.status})`, 'error');
    throw new ApiError(-1, `服务器返回异常 (HTTP ${resp.status})`);
  }

  const code = data.code;
  if (!resp.ok || !data.success) {
    // 优先用服务端返回的 message（它更具体，比如顶号场景会说明绑定情况），
    // ERROR_TEXT 只在服务端没给文案时兜底。
    const text = data.message || ERROR_TEXT[code] || '请求失败';
    logApi(`✗ ${method} ${path} [${code}] ${text} (${cost}ms)`, 'error');
    throw new ApiError(code, text, data.request_id);
  }
  logApi(`✓ ${method} ${path} [${code}] (${cost}ms)`, 'ok');
  return data.data;
}

/* ========================= 6. 会话操作 ========================= */
async function verifyLicense(licenseKey, force = false) {
  return apiCall('/api/v1/license/verify', {
    body: {
      license_key: licenseKey,
      machine_id: resolveMachineId(),
      client_version: CONFIG.server.clientVersion,
      force: !!force,
    },
  });
}

async function sendHeartbeat() {
  if (!state.session) return false;
  try {
    const data = await apiCall('/api/v1/license/heartbeat', {
      body: {
        session_id: state.session.session_id,
        session_token: state.session.session_token,
        machine_id: resolveMachineId(),
        client_version: CONFIG.server.clientVersion,
      },
    });
    state.session.expire_at = data.expire_at;
    return true;
  } catch (err) {
    if (err.code === 4009 || err.code === 4010) {
      logError('心跳', err, '会话已失效，即将返回验证页');
      handleSessionLost(err.message);
      return false;
    }
    logError('心跳', err, '将在下个周期重试');
    return false;
  }
}

async function deactivateLicense() {
  if (!state.session) return;
  await apiCall('/api/v1/license/deactivate', {
    body: {
      session_id: state.session.session_id,
      session_token: state.session.session_token,
    },
  });
}

async function fetchLicenseInfo() {
  if (!state.session) throw new ApiError(-1, '尚未建立会话');
  return apiCall('/api/v1/license/info', {
    method: 'GET',
    query: {
      session_id: state.session.session_id,
      session_token: state.session.session_token || '',
    },
  });
}

/* ========================= 7. 心跳与倒计时 ========================= */
function startHeartbeat() {
  stopHeartbeat();
  const interval = CONFIG.features.heartbeatInterval;
  if (!interval) return;
  state.heartbeatTimer = setInterval(() => { sendHeartbeat(); }, interval * 1000);
}

function stopHeartbeat() {
  if (state.heartbeatTimer) { clearInterval(state.heartbeatTimer); state.heartbeatTimer = null; }
}

function startCountdown() {
  stopCountdown();
  const tick = () => {
    if (!state.session || !state.session.expire_at) return;
    const remain = new Date(state.session.expire_at).getTime() - Date.now();
    const info = fmtDuration(remain);
    const el = $('countdownText');
    if (el) {
      el.textContent = info.expired ? '已过期' : info.text;
      const box = $('countdownBox');
      box.classList.toggle('is-urgent', !info.expired && remain < 3 * 86400000);
      box.classList.toggle('is-critical', !info.expired && remain < 86400000);
    }
    // 进度条：按 30 天为满格估算
    const bar = $('authProgress');
    if (bar) bar.style.width = info.expired ? '0%' : `${Math.max(2, Math.min(100, (remain / (30 * 86400000)) * 100))}%`;
    if (info.expired) {
      log('warn', '授权已到期，正在返回验证页');
      handleSessionLost('授权已到期，请重新验证');
    }
  };
  tick();
  state.countdownTimer = setInterval(tick, 1000);
}

function stopCountdown() {
  if (state.countdownTimer) { clearInterval(state.countdownTimer); state.countdownTimer = null; }
}

function handleSessionLost(message) {
  stopHeartbeat();
  stopCountdown();
  clearRememberedKey();
  state.session = null;
  showAlert('authAlert', 'warn', message || '会话已失效，请重新验证卡密');
  switchView('verify');
}

/* ========================= 8. UI 渲染 ========================= */
function switchView(view) {
  state.view = view;
  // 切换视图时统一复位按钮状态，避免验证成功后停留在「验证中...」的禁用态
  setBusy(false);
  $$('.lc-view').forEach(el => el.classList.remove('is-active'));
  const target = view === 'app' ? $('viewApp') : $('viewVerify');
  target.classList.add('is-active');
  // 面板宽度在两个视图间切换
  const shell = $('shellPanel');
  shell.classList.toggle('lc-panel--wide', view === 'app');
  shell.classList.toggle('lc-panel--narrow', view !== 'app');
}

function showAlert(id, type, message, code) {
  const el = $(id);
  if (!el) return;
  if (!message) { el.classList.remove('is-show'); return; }
  const icons = { ok: '✓', err: '✕', warn: '!', info: 'i' };
  el.className = `lc-alert lc-alert--${type} is-show`;
  el.innerHTML = `<span class="lc-alert-icon">${icons[type] || 'i'}</span>
    <div class="lc-alert-body">
      <div>${escapeHtml(message)}</div>
      ${code ? `<div class="lc-alert-code">code=${code}</div>` : ''}
    </div>`;
}

function hideAlert(id) { showAlert(id, 'info', ''); }

let toastTimer = null;
function toast(message, type = 'ok') {
  const wrap = $('toastWrap');
  const el = document.createElement('div');
  el.className = `lc-toast lc-toast--${type}`;
  const icons = { ok: '✓', err: '✕', warn: '!', info: 'i' };
  el.innerHTML = `<span>${icons[type]}</span><span>${escapeHtml(message)}</span>`;
  wrap.appendChild(el);
  clearTimeout(toastTimer);
  setTimeout(() => {
    el.classList.add('is-out');
    setTimeout(() => el.remove(), 320);
  }, 2600);
}

/** 授权状态 → 徽标 */
function statusPill(status) {
  const map = {
    ACTIVE: ['ok', '已授权'],
    UNUSED: ['warn', '未激活'],
    EXPIRED: ['err', '已过期'],
    DISABLED: ['err', '已禁用'],
  };
  const [tone, text] = map[status] || ['ok', status || '已授权'];
  return `<span class="lc-pill lc-pill--${tone}">${escapeHtml(text)}</span>`;
}

/** 渲染授权详情表 */
function renderAuthDetail() {
  const s = state.session;
  if (!s) return;
  const rows = [
    ['授权状态', statusPill(s.status || 'ACTIVE')],
    ['产品', escapeHtml(CONFIG.product.name)],
    ['卡密 ID', escapeHtml(s.license_id || '-')],
    [CONFIG.texts.sessionLabel, escapeHtml(s.session_id || '-')],
    ['机器 ID', escapeHtml(resolveMachineId())],
    [CONFIG.texts.expireLabel, escapeHtml(fmtDateTime(s.expire_at))],
  ];
  $('authDetail').innerHTML = rows.map(([k, v]) =>
    `<div class="lc-dl-row"><span class="lc-dl-k">${escapeHtml(k)}</span><span class="lc-dl-v">${v}</span></div>`
  ).join('');
  // 顶部主视觉区的到期时间也要同步
  $('expireTime').textContent = fmtDateTime(s.expire_at);
  // 状态异常时顶部徽标同步变色
  const hero = $('authHero');
  if (hero) {
    const bad = s.status === 'EXPIRED' || s.status === 'DISABLED';
    hero.classList.toggle('is-warn', bad);
  }
  const heroText = $('authStatusText');
  if (heroText) {
    const texts = { ACTIVE: '授权有效', UNUSED: '未激活', EXPIRED: '授权已过期', DISABLED: '授权已禁用' };
    heroText.textContent = texts[s.status] || '授权有效';
  }
}

/* ========================= 9. 获取卡密弹窗 ========================= */
function openGetKeyModal() {
  const cfg = CONFIG.getKey;
  const body = $('getKeyBody');

  if (cfg.mode === 'link') {
    body.innerHTML = `
      <p class="lc-getkey-text">点击下方按钮将在浏览器中打开购买页面。</p>
      <a class="lc-contact" href="${escapeHtml(cfg.url)}" target="_blank" rel="noopener">
        <span>${escapeHtml(cfg.url)}</span><span class="lc-contact-tag">打开 ↗</span>
      </a>`;
  } else {
    const items = (cfg.items || []).map(it => {
      if (it.type === 'contact') {
        // 可点击复制：视觉上与其他文本明显不同
        return `<div><span class="lc-contact" data-copy="${escapeHtml(it.value)}">
          ${escapeHtml(it.value)}<span class="lc-contact-tag">点击复制</span>
        </span></div>`;
      }
      if (it.type === 'link') {
        return `<div class="lc-getkey-text" style="margin:6px 0">
          <span style="color:var(--lc-text-2)">${escapeHtml(it.label)}：</span>
          <a href="${escapeHtml(it.value)}" target="_blank" rel="noopener"
             style="color:var(--lc-accent);text-decoration:underline;text-underline-offset:3px">${escapeHtml(it.value)}</a>
        </div>`;
      }
      return `<div class="lc-getkey-text" style="margin:6px 0">${escapeHtml(it.label)}：${escapeHtml(it.value)}</div>`;
    }).join('');

    body.innerHTML = `<p class="lc-getkey-text">${escapeHtml(cfg.desc || '')}</p>${items}`;
  }

  $('getKeyModal').classList.add('is-open');
  log('info', '打开获取卡密弹窗');
}

/** 事件委托：弹窗内所有可复制元素统一处理 */
function bindCopyDelegation() {
  $('getKeyBody').addEventListener('click', (e) => {
    const target = e.target.closest('[data-copy]');
    if (!target) return;
    const value = target.dataset.copy;
    copyText(value).then(() => {
      const tag = target.querySelector('.lc-contact-tag');
      target.classList.add('is-copied');
      if (tag) tag.textContent = '已复制';
      toast(`${value} 已复制到剪贴板`, 'ok');
      log('info', `复制联系方式: ${value}`);
      setTimeout(() => {
        target.classList.remove('is-copied');
        if (tag) tag.textContent = '点击复制';
      }, 1800);
    }).catch(() => {
      toast('复制失败，请手动选择复制', 'err');
      log('error', `复制失败: ${value}`);
    });
  });
}

/* ========================= 10. 确认弹窗 ========================= */
/** 通用确认框，返回 Promise<boolean> */
function confirmDialog({ title, body, confirmText, cancelText, danger }) {
  return new Promise((resolve) => {
    $('confirmTitle').textContent = title;
    $('confirmBody').innerHTML = body;
    $('confirmOk').textContent = confirmText || '确认';
    $('confirmCancel').textContent = cancelText || '取消';
    $('confirmOk').className = `lc-btn ${danger ? 'lc-btn--danger' : 'lc-btn--primary'}`;
    $('confirmModal').classList.add('is-open');

    const close = (result) => {
      $('confirmModal').classList.remove('is-open');
      $('confirmOk').onclick = null;
      $('confirmCancel').onclick = null;
      $('confirmModal').onclick = null;
      resolve(result);
    };
    $('confirmOk').onclick = () => close(true);
    $('confirmCancel').onclick = () => close(false);
    // 点击遮罩空白处等同于取消
    $('confirmModal').onclick = (e) => { if (e.target === $('confirmModal')) close(false); };
  });
}

/* ========================= 11. 主流程 ========================= */
function setBusy(flag) {
  state.busy = flag;
  const btn = $('verifyBtn');
  if (!btn) return;
  btn.disabled = flag;
  btn.innerHTML = flag
    ? `<span class="lc-spinner"></span>验证中...`
    : escapeHtml(CONFIG.texts.verifyButton);
}

async function onVerifySubmit() {
  if (state.busy) return;
  const input = $('licenseInput');
  const key = input.value.trim();
  hideAlert('verifyAlert');

  if (!key) {
    showAlert('verifyAlert', 'warn', '请输入卡密');
    input.focus();
    return;
  }

  setBusy(true);
  log('info', `开始验证卡密: ${maskKey(key)}`);
  try {
    const data = await verifyLicense(key, false);
    onVerifySuccess(data, key);
  } catch (err) {
    // 4001 且提示顶号 → 询问是否强制顶号
    if (err.code === 4001 && /顶替|顶号|其他设备|已在/.test(err.message)) {
      setBusy(false);
      const force = await confirmDialog({
        title: '该卡密已被其他设备使用',
        body: `<strong>${escapeHtml(err.message)}</strong><br><br>
               继续将把该卡密从原设备上解绑，此操作无法撤销。`,
        confirmText: '顶号并继续',
        cancelText: '取消',
        danger: true,
      });
      if (force) {
        setBusy(true);
        try {
          const data2 = await verifyLicense(key, true);
          onVerifySuccess(data2, key);
        } catch (err2) {
          setBusy(false);
          showAlert('verifyAlert', 'err', err2.message, err2.code);
          logError('验证', err2);
        }
      }
      return;
    }
    setBusy(false);
    showAlert('verifyAlert', 'err', err.message, err.code);
    logError('验证', err);
  }
}

/** 卡密脱敏，日志里不打印完整卡密 */
function maskKey(key) {
  if (key.length <= 8) return key.slice(0, 3) + '***';
  return `${key.slice(0, 4)}****${key.slice(-4)}`;
}

function onVerifySuccess(data, rawKey) {
  // authorization 是服务端签名的字符串（不可直接解析出字段），
  // 所以卡密 ID 优先从会话日志/详情接口拿，这里先留空由 renderAuthDetail 回填。
  state.session = {
    session_id: data.session_id,
    session_token: data.session_token,
    expire_at: data.expire_at,
    license_id: data.license_id || '-',
  };
  log('info', `验证成功，会话 ${data.session_id}`);
  if (CONFIG.features.rememberKey) {
    try { localStorage.setItem('lc_license_key', rawKey); } catch (e) {}
  }
  renderAuthDetail();
  switchView('app');
  startHeartbeat();
  startCountdown();
  toast('授权成功，欢迎使用', 'ok');
  // 后台拉一次授权详情，把卡密 ID 等服务端字段补全
  refreshAuthDetail();
}

/** 拉取服务端授权详情并更新界面（失败静默，不影响主流程） */
async function refreshAuthDetail() {
  if (!state.session) return;
  try {
    const info = await fetchLicenseInfo();
    state.session.license_id = info.license_id || state.session.license_id;
    state.session.status = info.status;
    renderAuthDetail();
  } catch (err) {
    log('warn', `获取授权详情失败: ${err.message}`);
  }
}

async function onLogoutClick() {
  const ok = await confirmDialog({
    title: CONFIG.texts.logoutConfirmTitle,
    body: `${escapeHtml(CONFIG.texts.logoutConfirmBody)}<br><br>
           <span style="color:var(--lc-text-3);font-size:12.5px">
             机器 ID：${escapeHtml(resolveMachineId())}
           </span>`,
    confirmText: '确认退出',
    cancelText: '返回',
    danger: true,
  });
  if (!ok) return;

  const btn = $('logoutBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="lc-spinner"></span>处理中...';
  try {
    await deactivateLicense();
    log('info', '已退出授权并解绑当前设备');
    toast('已退出授权', 'ok');
  } catch (err) {
    // 服务端解绑失败也要清理本地状态，否则用户会卡在应用页
    logError('退出授权', err, '本地状态仍会清理');
    toast('服务端解绑失败，已在本地退出', 'warn');
  }
  btn.disabled = false;
  btn.innerHTML = escapeHtml(CONFIG.texts.logoutButton);
  stopHeartbeat();
  stopCountdown();
  clearRememberedKey();
  state.session = null;
  $('licenseInput').value = '';
  switchView('verify');
}

async function onCloseClick() {
  const ok = await confirmDialog({
    title: CONFIG.texts.closeConfirmTitle,
    body: escapeHtml(CONFIG.texts.closeConfirmBody),
    confirmText: '确认退出',
    cancelText: '继续使用',
    danger: true,
  });
  if (!ok) return;
  log('info', '用户确认关闭程序');
  stopHeartbeat();
  stopCountdown();
  // 桌面端（Electron/Tauri）可在此调用真正的关闭逻辑
  if (window.require && window.require('electron')) {
    try { window.require('electron').remote.app.quit(); return; } catch (e) {}
  }
  // 浏览器环境：显示退出状态（继承当前主题）
  document.body.innerHTML = `
    <div class="lc-root" style="min-height:100vh">
      <div class="lc-noise"></div>
      <div class="lc-panel lc-panel--narrow" style="max-width:400px">
        <div class="lc-body" style="text-align:center;padding:44px 30px">
          <div class="lc-logo" style="margin:0 auto 18px">${escapeHtml(CONFIG.product.logoText)}</div>
          <div style="font-family:var(--lc-font-display);font-size:19px;font-weight:700;margin-bottom:8px">程序已退出</div>
          <div style="color:var(--lc-text-3);font-size:13px;line-height:1.7">
            这是浏览器演示环境，真实客户端在此处结束进程。<br>
            你可以刷新页面重新体验完整流程。
          </div>
          <button class="lc-btn lc-btn--primary" style="margin-top:24px" onclick="location.reload()">
            重新启动演示
          </button>
        </div>
      </div>
    </div>`;
}

/* ========================= 12. 记住卡密 ========================= */
function clearRememberedKey() {
  try { localStorage.removeItem('lc_license_key'); } catch (e) {}
}

/** 启动时若本地有卡密则自动验证一次，省去重复输入 */
async function tryAutoVerify() {
  if (!CONFIG.features.rememberKey) return;
  let saved = null;
  try { saved = localStorage.getItem('lc_license_key'); } catch (e) {}
  if (!saved) return;
  log('info', '检测到已保存的卡密，正在自动验证...');
  const input = $('licenseInput');
  if (input) input.value = saved;
  setBusy(true);
  try {
    const data = await verifyLicense(saved, false);
    onVerifySuccess(data, saved);
    toast('已自动恢复上次授权', 'ok');
  } catch (err) {
    log('warn', `自动验证失败: ${err.message}`);
    setBusy(false);
    hideAlert('verifyAlert');
  }
}

/* ========================= 13. 初始化 ========================= */
function applyConfig() {
  document.title = `${CONFIG.product.name} — 授权验证`;
  $('logoText').textContent = CONFIG.product.logoText;
  $('brandName').textContent = CONFIG.product.name;
  $('brandSub').textContent = `${CONFIG.product.version} · ${CONFIG.product.subtitle}`;
  $('footProduct').textContent = `${CONFIG.product.name} ${CONFIG.product.version}`;
  $('footServer').textContent = CONFIG.server.url;
  $('verifyTitle').textContent = CONFIG.texts.verifyTitle;
  $('licenseInput').placeholder = CONFIG.texts.verifyPlaceholder;
  $('getKeyBtn').textContent = CONFIG.getKey.buttonText || CONFIG.texts.getKeyButton;
  $('logoutBtn').textContent = CONFIG.texts.logoutButton;
  $('closeBtn').textContent = CONFIG.texts.closeButton;
  $('expireLabel').textContent = CONFIG.texts.expireLabel;

  // 顶号提示条
  const notice = $('kickNotice');
  if (CONFIG.texts.kickNotice) {
    notice.innerHTML = `<span class="lc-notice-icon">⚠</span><span>${escapeHtml(CONFIG.texts.kickNotice)}</span>`;
    notice.style.display = 'flex';
  } else {
    notice.style.display = 'none';
  }

  // 机器 ID 输入框按开关显示
  const machineField = $('machineField');
  machineField.style.display = CONFIG.features.showMachineId ? 'block' : 'none';

  // 日志面板按开关显示
  $('logbar').style.display = CONFIG.features.showLog ? 'flex' : 'none';
  $('log').style.display = CONFIG.features.showLog ? 'block' : 'none';

  // 主题切换按钮：可禁用，或强制固定某个主题时隐藏
  const themeBtn = $('themeBtn');
  const themeLocked = CONFIG.features.forceTheme === 'light' || CONFIG.features.forceTheme === 'dark';
  if (!CONFIG.features.allowThemeToggle || themeLocked) {
    if (themeBtn) themeBtn.style.display = 'none';
  }

  // 兜底重应用主题：applyConfig 里操作了大量 DOM，
  // 这里再确认一次主题没被意外改动，避免界面与用户偏好不一致。
  applyTheme(document.documentElement.getAttribute('data-theme') || resolveInitialTheme());
}

/** 导出诊断信息：排查问题时让用户一键复制 */
function collectDiagnostics() {
  const lines = [
    `产品: ${CONFIG.product.name} ${CONFIG.product.version}`,
    `服务器: ${CONFIG.server.url}`,
    `当前主题: ${document.documentElement.getAttribute('data-theme') || '(未设置)'}`,
    `存储的偏好: ${themeStore.get() || '(无)'}`,
    `强制主题: ${CONFIG.features.forceTheme || '(未设置)'}`,
    `客户端版本: ${CONFIG.server.clientVersion}`,
    `机器 ID: ${resolveMachineId()}`,
    `会话 ID: ${state.session?.session_id || '(无活跃会话)'}`,
    `就绪状态: ${document.readyState}`,
    `存储可用: ${(() => { try { localStorage.setItem('__probe', '1'); localStorage.removeItem('__probe'); return '是'; } catch (e) { return '否(' + e.name + ')'; } })()}`,
    `--- 最近日志 ---`,
    ...state.logEntries.slice(-40).map(e => `${fmtTime(e.time)} [${e.level}] ${e.message}`),
  ];
  return lines.join('\n');
}

function bindEvents() {
  $('verifyForm').addEventListener('submit', (e) => { e.preventDefault(); onVerifySubmit(); });
  // 注意：卡密区分大小写，不能做任何大小写/空格规整，否则会与服务端精确匹配冲突。
  // 这里只去掉首尾空白，用户粘贴时常见的多余空格是无害的。
  $('licenseInput').addEventListener('input', (e) => {
    const trimmed = e.target.value.replace(/^\s+|\s+$/g, '');
    if (trimmed !== e.target.value) e.target.value = trimmed;
  });
  $('getKeyBtn').addEventListener('click', openGetKeyModal);
  $('getKeyClose').addEventListener('click', () => $('getKeyModal').classList.remove('is-open'));
  $('logoutBtn').addEventListener('click', onLogoutClick);
  $('closeBtn').addEventListener('click', onCloseClick);

  // 日夜主题切换
  $('themeBtn')?.addEventListener('click', toggleTheme);

  // 日志面板
  $('logToggle').addEventListener('click', () => {
    $('log').classList.toggle('is-open');
  });
  $('logClear').addEventListener('click', clearLog);
  // 复制 = 导出完整诊断信息（环境 + 日志），比只复制日志更有助于定位问题
  $('logCopy').addEventListener('click', () => {
    if (!state.logEntries.length) { toast('暂无日志可复制', 'warn'); return; }
    copyText(collectDiagnostics()).then(() => toast('诊断信息已复制', 'ok')).catch(() => toast('复制失败', 'err'));
  });
  $$('.lc-log-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.lc-log-tab').forEach(t => t.classList.remove('is-active'));
      tab.classList.add('is-active');
      state.logFilter = tab.dataset.filter;
      renderLog();
    });
  });

  // 点击遮罩关闭获取卡密弹窗
  $('getKeyModal').addEventListener('click', (e) => {
    if (e.target === $('getKeyModal')) $('getKeyModal').classList.remove('is-open');
  });

  // 回车即提交
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      $('getKeyModal').classList.remove('is-open');
    }
  });
}

function init() {
  // 主题要在其他渲染之前确定，否则会出现闪烁
  applyTheme(resolveInitialTheme());
  applyConfig();
  bindEvents();
  bindCopyDelegation();
  resolveMachineId();
  log('info', `${CONFIG.product.name} 客户端启动`);
  log('info', `主题: ${document.documentElement.getAttribute('data-theme') === 'dark' ? '夜间' : '日间'}`);
  log('info', `服务器: ${CONFIG.server.url}`);
  if (!CONFIG.server.apiKey) {
    log('warn', '未配置 API Key，验证会直接失败');
  }
  switchView('verify');
  tryAutoVerify();
}

/* 脚本位于 body 末尾时 DOMContentLoaded 通常尚未触发，
   但部分环境（含 Electron 预加载、缓存命中）可能已经就绪，
   因此两种情况都要覆盖，避免 init 永远不执行导致界面空白。 */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true });
} else {
  init();
}

// 主题兜底：部分环境（存储分区、跨域隔离、Electron 预加载、自动化浏览器）
// 在页面脚本执行的那一瞬间还读不到 localStorage，导致 resolveInitialTheme()
// 回落成日间，表现为「用户选了夜间，刷新后又变亮」。
// 这里在 load 事件（所有资源就绪、存储可访问）后再校正一次。
window.addEventListener('load', () => {
  const expected = resolveInitialTheme();
  const actual = document.documentElement.getAttribute('data-theme');
  if (expected !== actual) {
    applyTheme(expected);
    console.info(`[license-client] 主题已校正为${expected === 'dark' ? '夜间' : '日间'}`);
  }
});