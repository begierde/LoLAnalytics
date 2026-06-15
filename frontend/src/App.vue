<template>
  <div v-if="!authenticated" class="login-screen">
    <form class="login-panel" @submit.prevent="login">
      <div class="brand-mark">LT</div>
      <h1>LoLAnalytics</h1>
      <p>{{ t('loginHelp') }}</p>
      <label>{{ t('username') }}</label>
      <input v-model="loginForm.username" autocomplete="username">
      <label>{{ t('password') }}</label>
      <input v-model="loginForm.password" type="password" autocomplete="current-password">
      <button :disabled="loggingIn">{{ loggingIn ? t('running') : t('login') }}</button>
      <div v-if="message" class="message err">{{ message }}</div>
    </form>
  </div>

  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">LT</div>
        <div class="brand-title">LoLAnalytics</div>
        <div class="brand-subtitle">{{ t('subtitle') }}</div>
      </div>
      <nav>
        <button :class="{active: tab === 'collect'}" @click="navigate('collect')">{{ t('navCollect') }}</button>
        <button :class="{active: tab === 'stats'}" @click="navigate('stats')">{{ t('navStats') }}</button>
        <button :class="{active: tab === 'monitors'}" @click="navigate('monitors')">{{ t('navMonitors') }}</button>
        <button :class="{active: tab === 'logs'}" @click="navigate('logs')">{{ t('navLogs') }}</button>
        <button :class="{active: tab === 'settings'}" @click="navigate('settings')">{{ t('navSettings') }}</button>
      </nav>
      <div class="sidebar-footer">
        <div>{{ t('defaultServer') }}: {{ settings.defaultServer || collect.server || '-' }}</div>
        <div>{{ t('rankScope') }}: {{ rankLabel(settings.defaultRankScope || collect.rankScope) }}</div>
      </div>
    </aside>

    <main class="content">
      <header class="topbar">
        <div>
          <div class="eyebrow">{{ t('workspace') }}</div>
          <h1>{{ pageTitle }}</h1>
          <p class="help">{{ pageDescription }}</p>
        </div>
        <div class="topbar-actions">
          <span class="status-pill" :class="settings.hasRiotApiKey ? 'ok' : 'warn'">
            {{ settings.hasRiotApiKey ? t('keyConfigured') : t('keyNotConfigured') }}
          </span>
          <span class="status-pill">{{ collect.timezone }}</span>
          <button class="secondary" @click="refreshCurrent">{{ t('refresh') }}</button>
          <button class="secondary" @click="logout">{{ t('logout') }}</button>
        </div>
      </header>

      <div class="view">
        <section v-if="message" class="message" :class="messageType">{{ message }}</section>

        <section v-if="tab === 'collect'" class="stack">
          <div class="section-head">
            <div>
              <h2>{{ t('submitCollection') }}</h2>
              <p>{{ t('collectHelp') }}</p>
            </div>
          </div>
          <div class="panel">
            <div class="form-grid">
              <div>
                <label>{{ t('days') }}</label>
                <input type="number" min="1" max="365" v-model.number="collect.days">
              </div>
              <div>
                <label>{{ t('playerLimit') }}</label>
                <input type="number" min="1" max="300" v-model.number="collect.limitPlayers">
              </div>
              <div>
                <label>{{ t('server') }}</label>
                <select v-model="collect.server">
                  <option v-for="server in settings.servers || []" :key="server.code" :value="server.code">
                    {{ server.code }} - {{ server.label }}
                  </option>
                </select>
              </div>
              <div class="wide">
                <label>{{ t('rankScope') }}</label>
                <select v-model="collect.rankScope">
                  <option value="challenger">{{ t('rankChallenger') }}</option>
                  <option value="challenger_grandmaster">{{ t('rankChallengerGrandmaster') }}</option>
                  <option value="challenger_grandmaster_master">{{ t('rankAllElite') }}</option>
                </select>
              </div>
              <div>
                <label>{{ t('timezone') }}</label>
                <select v-model="collect.timezone">
                  <option v-for="timezone in timezoneOptions" :key="timezone.value" :value="timezone.value">
                    {{ timezoneLabel(timezone) }}
                  </option>
                </select>
              </div>
              <div class="wide">
                <label>{{ t('leagueSource') }}</label>
                <select v-model="collect.refreshLeague">
                  <option :value="true">{{ t('refreshLeague') }}</option>
                  <option :value="false">{{ t('reusePlayers') }}</option>
                </select>
              </div>
              <div class="actions full">
                <button :disabled="collecting" @click="startCollect">{{ collecting ? t('running') : t('submitCollection') }}</button>
                <button class="secondary" @click="loadJobs">{{ t('refreshJobStatus') }}</button>
              </div>
            </div>
          </div>
          <data-table-panel :title="t('jobs')" :help="t('jobsHelp')">
            <table>
              <thead><tr><th>ID</th><th>{{ t('status') }}</th><th>{{ t('progress') }}</th><th>{{ t('server') }}</th><th>{{ t('rankScope') }}</th><th>{{ t('message') }}</th><th>{{ t('error') }}</th></tr></thead>
              <tbody>
                <tr v-for="job in jobs" :key="job.id">
                  <td>{{ job.id }}</td>
                  <td><span class="status-text">{{ job.status }}</span></td>
                  <td>{{ job.progress_current }}/{{ job.progress_total }}</td>
                  <td>{{ job.server || '-' }}</td>
                  <td>{{ rankLabel(job.rank_scope) }}</td>
                  <td>{{ job.message || '-' }}</td>
                  <td class="err">{{ job.error || '' }}</td>
                </tr>
                <tr v-if="!jobs.length"><td colspan="7">{{ t('noJobs') }}</td></tr>
              </tbody>
            </table>
            <template #pager>
              <pager :pagination="jobPagination" :label="pageText(jobPagination)" @prev="jobPagination.page--; loadJobs()" @next="jobPagination.page++; loadJobs()" />
            </template>
          </data-table-panel>
        </section>

        <section v-if="tab === 'stats'" class="stack">
          <div class="section-head">
            <div>
              <h2>{{ t('statsOverview') }}</h2>
              <p>{{ t('statsHelp') }}</p>
            </div>
            <div class="actions end">
              <select v-model.number="collect.days" @change="loadStats()">
                <option :value="7">7 {{ t('daysShort') }}</option>
                <option :value="14">14 {{ t('daysShort') }}</option>
                <option :value="30">30 {{ t('daysShort') }}</option>
                <option :value="90">90 {{ t('daysShort') }}</option>
              </select>
              <select v-model="collect.timezone" @change="loadStats()">
                <option v-for="timezone in timezoneOptions" :key="timezone.value" :value="timezone.value">
                  {{ timezoneLabel(timezone) }}
                </option>
              </select>
            </div>
          </div>
          <div class="grid">
            <div class="metric"><span>{{ t('flexSamples') }}</span><strong>{{ stats.summary?.total_events || 0 }}</strong><small>{{ t('samples') }}</small></div>
            <div class="metric"><span>{{ t('activePlayers') }}</span><strong>{{ stats.summary?.unique_players || 0 }}</strong><small>{{ t('players') }}</small></div>
            <div class="metric"><span>{{ t('weekdaySamples') }}</span><strong>{{ stats.summary?.weekday_total || 0 }}</strong><small>{{ t('weekday') }}</small></div>
            <div class="metric"><span>{{ t('weekendSamples') }}</span><strong>{{ stats.summary?.weekend_total || 0 }}</strong><small>{{ t('weekend') }}</small></div>
          </div>
          <div class="two">
            <chart-panel :title="t('heatmap')" :help="t('chartFilterNote')" id="heatmap" />
            <chart-panel :title="t('hourDistribution')" :help="t('chartFilterNote')" id="hours" />
          </div>
          <div class="two">
            <data-table-panel :title="t('topSlots')">
              <table>
                <thead><tr><th>{{ t('weekday') }}</th><th>{{ t('hour') }}</th><th>{{ t('samples') }}</th></tr></thead>
                <tbody>
                  <tr v-for="slot in stats.summary?.top_slots || []" :key="slot.weekday + slot.hour">
                    <td>{{ slot.weekday }}</td><td>{{ pad(slot.hour) }}:00</td><td>{{ slot.count }}</td>
                  </tr>
                  <tr v-if="!(stats.summary?.top_slots || []).length"><td colspan="3">{{ t('noData') }}</td></tr>
                </tbody>
              </table>
            </data-table-panel>
            <data-table-panel :title="t('playerActivity')">
              <table>
                <thead><tr><th>Riot ID</th><th>{{ t('games') }}</th><th>{{ t('commonHours') }}</th><th>LP</th></tr></thead>
                <tbody>
                  <tr v-for="player in stats.players || []" :key="player.puuid">
                    <td>{{ player.riotId }}</td>
                    <td>{{ player.count }}</td>
                    <td>{{ (player.topHours || []).map(h => pad(h) + ':00').join(', ') || '-' }}</td>
                    <td>{{ player.leaguePoints || '-' }}</td>
                  </tr>
                  <tr v-if="!(stats.players || []).length"><td colspan="4">{{ t('noData') }}</td></tr>
                </tbody>
              </table>
              <template #pager>
                <pager :pagination="playerPagination" :label="pageText(playerPagination)" @prev="playerPagination.page--; loadStats()" @next="playerPagination.page++; loadStats()" />
              </template>
            </data-table-panel>
          </div>
        </section>

        <section v-if="tab === 'monitors'" class="stack">
          <div class="panel">
            <div class="section-head">
              <div>
                <h2>{{ t('addMonitor') }}</h2>
                <p>{{ t('monitorHelp') }}</p>
              </div>
            </div>
            <div class="row" style="margin-top: 14px;">
              <div class="span-3">
                <label>Riot ID</label>
                <input v-model="newMonitor" placeholder="gameName#tagLine">
              </div>
              <div class="actions">
                <button @click="addMonitor">{{ t('save') }}</button>
                <button class="secondary" @click="checkNow">{{ t('checkNow') }}</button>
              </div>
            </div>
          </div>
          <data-table-panel :title="t('monitorList')">
            <table>
              <thead><tr><th>Riot ID</th><th>{{ t('enabled') }}</th><th>{{ t('lastCheck') }}</th><th>{{ t('status') }}</th><th></th></tr></thead>
              <tbody>
                <tr v-for="monitor in monitors" :key="monitor.id">
                  <td>{{ monitor.riot_id }}</td>
                  <td><span class="badge" :class="monitor.enabled ? 'ok' : 'warn'">{{ monitor.enabled ? t('yes') : t('no') }}</span></td>
                  <td>{{ monitor.last_checked_utc || '-' }}</td>
                  <td>{{ monitor.last_status || '-' }}</td>
                  <td class="actions">
                    <button class="secondary" @click="toggleMonitor(monitor)">{{ monitor.enabled ? t('disable') : t('enable') }}</button>
                    <button class="danger" @click="deleteMonitor(monitor.id)">{{ t('delete') }}</button>
                  </td>
                </tr>
                <tr v-if="!monitors.length"><td colspan="5">{{ t('noData') }}</td></tr>
              </tbody>
            </table>
          </data-table-panel>
        </section>

        <section v-if="tab === 'logs'" class="stack">
          <div class="panel">
            <div class="section-head">
              <div>
                <h2>{{ t('logs') }}</h2>
                <p>{{ t('logsHelp') }}</p>
              </div>
            </div>
            <div class="row" style="margin-top: 14px;">
              <div>
                <label>{{ t('level') }}</label>
                <select v-model="logFilters.level">
                  <option value="">{{ t('all') }}</option>
                  <option value="debug">debug</option>
                  <option value="info">info</option>
                  <option value="error">error</option>
                </select>
              </div>
              <div>
                <label>{{ t('category') }}</label>
                <select v-model="logFilters.category">
                  <option value="">{{ t('all') }}</option>
                  <option value="collection">collection</option>
                  <option value="monitor">monitor</option>
                  <option value="webhook">webhook</option>
                  <option value="api_key">api_key</option>
                  <option value="settings">settings</option>
                </select>
              </div>
              <div class="actions">
                <button @click="loadLogs">{{ t('refresh') }}</button>
                <button class="danger" @click="clearLogs">{{ t('clearLogs') }}</button>
              </div>
            </div>
          </div>
          <data-table-panel>
            <table>
              <thead><tr><th>ID</th><th>{{ t('time') }}</th><th>{{ t('level') }}</th><th>{{ t('category') }}</th><th>{{ t('message') }}</th></tr></thead>
              <tbody>
                <tr v-for="log in logs" :key="log.id">
                  <td>{{ log.id }}</td>
                  <td>{{ log.created_at_utc }}</td>
                  <td><span class="badge" :class="log.level === 'error' ? 'err' : (log.level === 'info' ? 'ok' : '')">{{ log.level }}</span></td>
                  <td>{{ log.category }}</td>
                  <td>
                    <div>{{ log.message }}</div>
                    <button class="secondary" style="margin-top: 6px;" @click="log.expanded = !log.expanded">{{ log.expanded ? t('hideDetail') : t('showDetail') }}</button>
                    <pre v-if="log.expanded" class="log-detail">{{ JSON.stringify(log.detail || {}, null, 2) }}</pre>
                  </td>
                </tr>
                <tr v-if="!logs.length"><td colspan="5">{{ t('noLogs') }}</td></tr>
              </tbody>
            </table>
            <template #pager>
              <pager :pagination="logPagination" :label="pageText(logPagination)" @prev="logPagination.page--; loadLogs()" @next="logPagination.page++; loadLogs()" />
            </template>
          </data-table-panel>
        </section>

        <section v-if="tab === 'settings'" class="stack">
          <div class="panel">
            <h2>{{ t('appSettings') }}</h2>
            <div class="row" style="margin-top: 14px;">
              <div>
                <label>{{ t('language') }}</label>
                <select v-model="settings.language">
                  <option value="zh">中文</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div>
                <label>{{ t('defaultServer') }}</label>
                <select v-model="settings.defaultServer">
                  <option v-for="server in settings.servers || []" :key="server.code" :value="server.code">
                    {{ server.code }} - {{ server.label }}
                  </option>
                </select>
              </div>
              <div>
                <label>{{ t('defaultRankScope') }}</label>
                <select v-model="settings.defaultRankScope">
                  <option value="challenger">{{ t('rankChallenger') }}</option>
                  <option value="challenger_grandmaster">{{ t('rankChallengerGrandmaster') }}</option>
                  <option value="challenger_grandmaster_master">{{ t('rankAllElite') }}</option>
                </select>
              </div>
              <div>
                <label>{{ t('monitorInterval') }}</label>
                <input type="number" min="1" max="1440" v-model.number="settings.monitorIntervalMinutes">
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="section-head">
              <div>
                <h2>{{ t('riotApiKey') }}</h2>
                <p>{{ settings.hasRiotApiKey ? t('keyConfigured') + ': ' + settings.riotApiKeyMasked : t('keyNotConfigured') }}</p>
              </div>
            </div>
            <div class="row" style="margin-top: 14px;">
              <div class="span-3">
                <label>{{ t('newApiKey') }}</label>
                <input type="password" v-model="riotApiKeyInput" placeholder="RGAPI-...">
              </div>
              <div class="actions">
                <button class="secondary" @click="checkApiKey">{{ t('checkApiKey') }}</button>
              </div>
            </div>
            <p class="help" v-if="apiKeyCheck.message" :class="apiKeyCheck.valid ? 'ok' : 'err'">{{ apiKeyCheck.message }} {{ apiKeyCheck.checkedAt || '' }}</p>
          </div>
          <div class="panel">
            <h2>{{ t('webhookSettings') }}</h2>
            <div style="margin-top: 14px;">
              <label>Webhook URL</label>
              <input v-model="settings.webhookUrl">
            </div>
            <div style="margin-top: 12px;">
              <label>{{ t('webhookTemplate') }}</label>
              <textarea v-model="settings.webhookTemplate"></textarea>
            </div>
            <div class="actions" style="margin-top: 14px;">
              <button @click="saveSettings">{{ t('saveSettings') }}</button>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script>
import Plotly from 'plotly.js-dist-min'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const FALLBACK_TIMEZONE = 'UTC+08:00'

function formatUtcOffset(minutesAheadOfUtc) {
  if (minutesAheadOfUtc === 0) return 'UTC'
  const sign = minutesAheadOfUtc > 0 ? '+' : '-'
  const absolute = Math.abs(minutesAheadOfUtc)
  const hours = String(Math.floor(absolute / 60)).padStart(2, '0')
  const minutes = String(absolute % 60).padStart(2, '0')
  return `UTC${sign}${hours}:${minutes}`
}

function detectBrowserTimezone() {
  return formatUtcOffset(-new Date().getTimezoneOffset())
}

const messages = {
  zh: {
    subtitle: 'Flex 王者时段统计与玩家监控', workspace: 'Operations',
    loginHelp: '使用管理员账号登录', username: '用户名', password: '密码', login: '登录', logout: '退出',
    navCollect: '采集', navStats: '统计', navMonitors: '监控', navLogs: '日志', navSettings: '设置',
    collectTitle: '采集任务', statsTitle: '数据工作台', monitorsTitle: '玩家监控', logsTitle: '运行日志', settingsTitle: '应用设置',
    collectDescription: '提交后台采集任务并跟踪进度。', statsDescription: '查看 Flex 活跃时段、小时分布和玩家行为。', monitorsDescription: '管理 Riot ID 监控并立即检查当前状态。', logsDescription: '按级别和类别筛选本地运行事件。', settingsDescription: '配置默认服务器、段位范围、API Key 和 Webhook。',
    submitCollection: '提交采集任务', collectHelp: '采集会在 Worker 中后台运行。', refreshJobStatus: '刷新任务状态', jobsHelp: '最近的采集任务会显示在这里，运行中的任务会自动轮询。',
    days: '时间窗口（天）', daysShort: '天', playerLimit: '玩家数量', players: '玩家', server: '服务器', rankScope: '段位范围', timezone: '时区', leagueSource: '玩家来源',
    refreshLeague: '刷新当前榜单', reusePlayers: '复用缓存玩家', running: '运行中',
    rankChallenger: '仅王者', rankChallengerGrandmaster: '王者 + 宗师', rankAllElite: '王者 + 宗师 + 大师',
    jobs: '任务', status: '状态', progress: '进度', message: '消息', error: '错误', noJobs: '暂无任务',
    statsOverview: 'Flex 活跃概览', statsHelp: '指标和图表使用当前时间窗口，并排除低价值凌晨数据。',
    flexSamples: 'Flex 样本', activePlayers: '活跃玩家', weekdaySamples: '工作日样本', weekendSamples: '周末样本', weekend: '周末',
    heatmap: '时段热力图', hourDistribution: '小时分布', topSlots: 'Top 时段', weekday: '星期', hour: '小时', samples: '样本',
    playerActivity: '玩家活跃度', games: '场次', commonHours: '常见小时',
    addMonitor: '添加监控玩家', monitorHelp: '输入 Riot ID 后保存，也可以立即触发一次监控检查。', save: '保存', checkNow: '立即检查', monitorList: '监控列表', enabled: '启用', lastCheck: '最近检查',
    yes: '是', no: '否', enable: '启用', disable: '停用', delete: '删除',
    logs: '日志', logsHelp: '用于排查采集、监控、Webhook 和设置变更。', level: '级别', category: '类别', all: '全部', refresh: '刷新', clearLogs: '清空日志',
    time: '时间', showDetail: '展开详情', hideDetail: '收起详情', noLogs: '暂无日志', noData: '暂无数据',
    appSettings: '应用设置', language: '语言', defaultServer: '默认服务器', defaultRankScope: '默认段位范围', monitorInterval: '监控轮询间隔（分钟）',
    riotApiKey: 'Riot API Key', newApiKey: '新的 Riot API Key', checkApiKey: '检查 API Key', keyConfigured: '已配置', keyNotConfigured: '未配置 API Key',
    webhookSettings: 'Webhook 设置', webhookTemplate: 'Webhook JSON 模板', saveSettings: '保存设置',
    taskQueued: '任务已提交', settingsSaved: '设置已保存', monitorSaved: '已保存监控玩家', logsCleared: '日志已清空',
    pageSize: '每页', prev: '上一页', next: '下一页', pageInfo: '第 {page} / {totalPages} 页，共 {total} 条', chartFilterNote: '图表已排除 02:00-10:00 的数据',
  },
  en: {
    subtitle: 'Flex Challenger activity and player monitoring', workspace: 'Operations',
    loginHelp: 'Sign in with the admin account', username: 'Username', password: 'Password', login: 'Sign in', logout: 'Logout',
    navCollect: 'Collect', navStats: 'Stats', navMonitors: 'Monitors', navLogs: 'Logs', navSettings: 'Settings',
    collectTitle: 'Collection jobs', statsTitle: 'Data workbench', monitorsTitle: 'Player monitoring', logsTitle: 'Run logs', settingsTitle: 'App settings',
    collectDescription: 'Submit background collection jobs and track progress.', statsDescription: 'Review Flex activity windows, hourly shape, and player behavior.', monitorsDescription: 'Manage Riot ID monitors and check current state.', logsDescription: 'Filter local runtime events by level and category.', settingsDescription: 'Configure defaults, Riot API key, and webhook delivery.',
    submitCollection: 'Submit collection job', collectHelp: 'Collection runs in the background worker.', refreshJobStatus: 'Refresh job status', jobsHelp: 'Recent collection jobs appear here. Running jobs poll automatically.',
    days: 'Window (days)', daysShort: 'days', playerLimit: 'Player limit', players: 'players', server: 'Server', rankScope: 'Rank scope', timezone: 'Timezone', leagueSource: 'Player source',
    refreshLeague: 'Refresh current league', reusePlayers: 'Reuse cached players', running: 'Running',
    rankChallenger: 'Challenger only', rankChallengerGrandmaster: 'Challenger + Grandmaster', rankAllElite: 'Challenger + Grandmaster + Master',
    jobs: 'Jobs', status: 'Status', progress: 'Progress', message: 'Message', error: 'Error', noJobs: 'No jobs',
    statsOverview: 'Flex activity overview', statsHelp: 'Metrics and charts use the selected window and exclude low-signal overnight data.',
    flexSamples: 'Flex samples', activePlayers: 'Active players', weekdaySamples: 'Weekday samples', weekendSamples: 'Weekend samples', weekend: 'Weekend',
    heatmap: 'Time heatmap', hourDistribution: 'Hourly distribution', topSlots: 'Top slots', weekday: 'Weekday', hour: 'Hour', samples: 'Samples',
    playerActivity: 'Player activity', games: 'Games', commonHours: 'Common hours',
    addMonitor: 'Add monitored player', monitorHelp: 'Save a Riot ID or trigger an immediate monitor check.', save: 'Save', checkNow: 'Check now', monitorList: 'Monitor list', enabled: 'Enabled', lastCheck: 'Last check',
    yes: 'Yes', no: 'No', enable: 'Enable', disable: 'Disable', delete: 'Delete',
    logs: 'Logs', logsHelp: 'Useful for debugging collection, monitoring, webhook, and settings changes.', level: 'Level', category: 'Category', all: 'All', refresh: 'Refresh', clearLogs: 'Clear logs',
    time: 'Time', showDetail: 'Show detail', hideDetail: 'Hide detail', noLogs: 'No logs', noData: 'No data',
    appSettings: 'App settings', language: 'Language', defaultServer: 'Default server', defaultRankScope: 'Default rank scope', monitorInterval: 'Monitor interval (minutes)',
    riotApiKey: 'Riot API Key', newApiKey: 'New Riot API Key', checkApiKey: 'Check API Key', keyConfigured: 'Configured', keyNotConfigured: 'API Key is not configured',
    webhookSettings: 'Webhook settings', webhookTemplate: 'Webhook JSON template', saveSettings: 'Save settings',
    taskQueued: 'Job submitted', settingsSaved: 'Settings saved', monitorSaved: 'Monitor saved', logsCleared: 'Logs cleared',
    pageSize: 'Per page', prev: 'Previous', next: 'Next', pageInfo: 'Page {page} / {totalPages}, {total} total', chartFilterNote: 'Charts exclude data from 02:00 to 10:00',
  },
}

const DataTablePanel = {
  props: ['title', 'help'],
  template: `<div class="panel flush"><div v-if="title || help" class="panel-header"><div><h2 v-if="title">{{ title }}</h2><p v-if="help" class="help">{{ help }}</p></div></div><div class="panel-body table-wrap"><slot /></div><slot name="pager" /></div>`,
}

const ChartPanel = {
  props: ['title', 'help', 'id'],
  template: `<div class="panel"><div class="section-head"><div><h2>{{ title }}</h2><p>{{ help }}</p></div></div><div :id="id" class="chart"></div></div>`,
}

const Pager = {
  props: ['pagination', 'label'],
  emits: ['prev', 'next'],
  template: `<div class="pager"><span>{{ label }}</span><div class="pager-controls"><button class="secondary" :disabled="pagination.page <= 1" @click="$emit('prev')">‹</button><button class="secondary" :disabled="pagination.page >= pagination.totalPages" @click="$emit('next')">›</button></div></div>`,
}

export default {
  components: { DataTablePanel, ChartPanel, Pager },
  data() {
    return {
      authenticated: Boolean(sessionStorage.getItem('accessToken')),
      accessToken: sessionStorage.getItem('accessToken') || '',
      loginForm: { username: 'admin', password: '' },
      loggingIn: false,
      tab: 'collect',
      message: '',
      messageType: '',
      collecting: false,
      collect: { days: 30, timezone: detectBrowserTimezone(), limitPlayers: 20, refreshLeague: true, server: 'JP', rankScope: 'challenger' },
      jobs: [],
      jobPagination: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
      stats: {},
      playerPagination: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
      monitors: [],
      logs: [],
      logFilters: { level: '', category: '' },
      logPagination: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
      newMonitor: '',
      riotApiKeyInput: '',
      apiKeyCheck: {},
      settings: { monitorIntervalMinutes: 15, webhookUrl: '', webhookTemplate: '{}', language: 'zh', defaultServer: 'JP', defaultRankScope: 'challenger', servers: [], timezones: [] },
      pollTimer: null,
    }
  },
  computed: {
    pageTitle() { return this.t(`${this.tab}Title`) },
    pageDescription() { return this.t(`${this.tab}Description`) },
    timezoneOptions() {
      return this.settings.timezones?.length ? this.settings.timezones : [{ value: FALLBACK_TIMEZONE, country: 'China' }]
    },
  },
  mounted() {
    if (this.authenticated) this.bootstrap()
  },
  methods: {
    t(key) { return (messages[this.settings.language] || messages.zh)[key] || key },
    pad(value) { return String(value).padStart(2, '0') },
    timezoneLabel(timezone) {
      return timezone?.country ? `${timezone.value} - ${timezone.country}` : timezone?.value || FALLBACK_TIMEZONE
    },
    applyDefaultTimezone() {
      const values = new Set(this.timezoneOptions.map(timezone => timezone.value))
      const detected = detectBrowserTimezone()
      if (values.has(detected)) {
        this.collect.timezone = detected
      } else if (values.has(FALLBACK_TIMEZONE)) {
        this.collect.timezone = FALLBACK_TIMEZONE
      } else {
        this.collect.timezone = this.timezoneOptions[0]?.value || FALLBACK_TIMEZONE
      }
    },
    async bootstrap() {
      await this.loadSettings()
      this.applyDefaultTimezone()
      this.collect.server = this.settings.defaultServer || 'JP'
      this.collect.rankScope = this.settings.defaultRankScope || 'challenger'
      await this.loadJobs()
    },
    async login() {
      this.loggingIn = true
      this.message = ''
      try {
        const body = new URLSearchParams({ username: this.loginForm.username || 'admin', password: this.loginForm.password })
        const response = await fetch(`${API_BASE}/auth/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body,
        })
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || response.statusText)
        const result = await response.json()
        this.accessToken = result.access_token
        sessionStorage.setItem('accessToken', this.accessToken)
        this.authenticated = true
        await this.bootstrap()
      } catch (err) {
        this.message = err.message
      } finally {
        this.loggingIn = false
      }
    },
    async logout() {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: this.authHeaders() }).catch(() => {})
      sessionStorage.removeItem('accessToken')
      this.accessToken = ''
      this.authenticated = false
    },
    authHeaders(extra = {}) {
      return { ...extra, Authorization: `Bearer ${this.accessToken}` }
    },
    async api(path, options = {}) {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: this.authHeaders({ 'Content-Type': 'application/json', ...(options.headers || {}) }),
      })
      if (response.status === 401) {
        await this.logout()
        throw new Error('Not authenticated')
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || response.statusText)
      }
      return response.json()
    },
    navigate(nextTab) {
      this.tab = nextTab
      this.refreshCurrent()
    },
    refreshCurrent() {
      if (this.tab === 'collect') return this.loadJobs()
      if (this.tab === 'stats') return this.loadStats()
      if (this.tab === 'monitors') return this.loadMonitors()
      if (this.tab === 'logs') return this.loadLogs()
      if (this.tab === 'settings') return this.loadSettings()
    },
    rankLabel(value) {
      const map = { challenger: this.t('rankChallenger'), challenger_grandmaster: this.t('rankChallengerGrandmaster'), challenger_grandmaster_master: this.t('rankAllElite') }
      return map[value] || value || '-'
    },
    pageText(pagination) {
      const totalPages = pagination.totalPages || 0
      const page = totalPages ? pagination.page : 0
      return this.t('pageInfo').replace('{page}', page).replace('{totalPages}', totalPages).replace('{total}', pagination.total || 0)
    },
    toast(text, type = 'ok') {
      this.message = text
      this.messageType = type
      setTimeout(() => { this.message = '' }, 5000)
    },
    async startCollect() {
      this.collecting = true
      try {
        const result = await this.api('/collection-jobs', { method: 'POST', body: JSON.stringify(this.collect) })
        this.toast(`${this.t('taskQueued')} #${result.jobId}`)
        await this.loadJobs()
        clearInterval(this.pollTimer)
        this.pollTimer = setInterval(this.loadJobs, 3000)
      } catch (err) {
        this.toast(err.message, 'err')
      } finally {
        this.collecting = false
      }
    },
    async loadJobs() {
      const params = new URLSearchParams({ page: this.jobPagination.page, pageSize: this.jobPagination.pageSize })
      const result = await this.api(`/collection-jobs?${params}`)
      this.jobs = result.jobs
      this.jobPagination = { ...this.jobPagination, ...(result.pagination || {}) }
    },
    async loadStats() {
      try {
        const params = new URLSearchParams({ days: this.collect.days, timezone: this.collect.timezone, playerPage: this.playerPagination.page, playerPageSize: this.playerPagination.pageSize })
        this.stats = await this.api(`/stats?${params}`)
        this.playerPagination = { ...this.playerPagination, ...(this.stats.playerPagination || {}) }
        this.$nextTick(this.drawCharts)
      } catch (err) {
        this.toast(err.message, 'err')
      }
    },
    drawCharts() {
      if (!document.getElementById('heatmap') || !document.getElementById('hours')) return
      const summary = this.stats.displaySummary || this.stats.summary || {}
      const heatmap = summary.heatmap || Array.from({ length: 7 }, () => Array(24).fill(0))
      const visibleHours = Array.from({ length: 24 }, (_, i) => i).filter(hour => hour < 2 || hour > 10)
      const hours = visibleHours.map(hour => `${this.pad(hour)}:00`)
      const weekdays = this.settings.language === 'en' ? ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] : ['周一','周二','周三','周四','周五','周六','周日']
      const layout = { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', margin: { l: 48, r: 14, t: 16, b: 50 }, font: { color: '#4f574f', size: 12 } }
      Plotly.newPlot('heatmap', [{ z: heatmap.map(row => visibleHours.map(hour => row[hour] || 0)), x: hours, y: weekdays, type: 'heatmap', colorscale: [[0, '#f7f3ea'], [0.35, '#92cfc6'], [1, '#075d57']], showscale: false }], layout, { displayModeBar: false, responsive: true })
      Plotly.newPlot('hours', [{ x: hours, y: visibleHours.map(hour => (summary.hour_counts || {})[hour] || 0), type: 'bar', marker: { color: '#5a4fcf' } }], layout, { displayModeBar: false, responsive: true })
    },
    async loadMonitors() {
      this.monitors = (await this.api('/monitors')).monitors
    },
    async addMonitor() {
      try {
        await this.api('/monitors', { method: 'POST', body: JSON.stringify({ riotId: this.newMonitor }) })
        this.newMonitor = ''
        this.toast(this.t('monitorSaved'))
        this.loadMonitors()
      } catch (err) { this.toast(err.message, 'err') }
    },
    async toggleMonitor(monitor) {
      await this.api(`/monitors/${monitor.id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !monitor.enabled }) })
      this.loadMonitors()
    },
    async deleteMonitor(id) {
      await this.api(`/monitors/${id}`, { method: 'DELETE' })
      this.loadMonitors()
    },
    async checkNow() {
      try {
        const result = await this.api('/monitor-checks', { method: 'POST' })
        this.toast(`checked ${result.checked}, flex ${result.in_flex}, notifications ${result.notifications}`)
        this.loadMonitors()
      } catch (err) { this.toast(err.message, 'err') }
    },
    async loadLogs() {
      const params = new URLSearchParams()
      if (this.logFilters.level) params.set('level', this.logFilters.level)
      if (this.logFilters.category) params.set('category', this.logFilters.category)
      params.set('page', this.logPagination.page)
      params.set('pageSize', this.logPagination.pageSize)
      const result = await this.api(`/logs?${params}`)
      this.logs = result.logs.map(log => ({ ...log, expanded: false }))
      this.logPagination = { ...this.logPagination, ...(result.pagination || {}) }
    },
    async clearLogs() {
      await this.api('/logs', { method: 'DELETE' })
      this.toast(this.t('logsCleared'))
      this.logPagination.page = 1
      this.loadLogs()
    },
    async loadSettings() {
      this.settings = await this.api('/settings')
    },
    async saveSettings() {
      try {
        await this.api('/settings', { method: 'PUT', body: JSON.stringify({ ...this.settings, riotApiKey: this.riotApiKeyInput || null }) })
        this.riotApiKeyInput = ''
        await this.loadSettings()
        this.toast(this.t('settingsSaved'))
      } catch (err) { this.toast(err.message, 'err') }
    },
    async checkApiKey() {
      try {
        if (this.riotApiKeyInput) await this.saveSettings()
        this.apiKeyCheck = await this.api('/settings/riot-api-key-checks', { method: 'POST', body: JSON.stringify({ server: this.settings.defaultServer }) })
        await this.loadSettings()
      } catch (err) {
        this.apiKeyCheck = { valid: false, message: err.message }
        this.toast(err.message, 'err')
      }
    },
  },
}
</script>
