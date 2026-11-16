const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const ts = require('typescript');

// 実際のクラス全体を読み込み、外部のプレイヤー・ストア・SSE 接続だけを置き換える。
const source_path = path.resolve(__dirname, '../src/services/player/managers/LiveEventManager.ts');
const source = ts.transpileModule(fs.readFileSync(source_path, 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText;

function createManager() {
    const connections = [];
    const sleeps = [];
    const restart_events = [];
    const player_store = {
        live_stream_status: null,
        event_emitter: {emit: (name, payload) => restart_events.push({name, payload})},
    };
    const channels_store = {display_channel_id: 'gr011', viewer_count: null};

    class FakeEventSource {
        constructor() {
            this.listeners = new Map();
            this.closed = false;
            connections.push(this);
        }
        addEventListener(name, callback) {
            this.listeners.set(name, callback);
        }
        close() {
            this.closed = true;
        }
        async sendStatus(status) {
            await this.listeners.get('status_update')({data: JSON.stringify({
                status, detail: 'test status', client_count: 1, started_at: 0, updated_at: 0,
            })});
        }
    }

    const utils = {
        api_base_url: '',
        sleep: (seconds) => new Promise((resolve) => sleeps.push({seconds, resolve})),
    };
    const imports = {
        '@/stores/ChannelsStore': {default: () => channels_store},
        '@/stores/PlayerStore': {default: () => player_store},
        '@/utils': {default: utils, PlayerUtils: {extractLiveAPIQualityFromDPlayer: () => '1080p'}},
    };
    const exports = {};
    vm.runInNewContext(source, {
        exports,
        require: (name) => {
            assert.ok(Object.hasOwn(imports, name), `Unexpected import: ${name}`);
            return imports[name];
        },
        EventSource: FakeEventSource,
        document: {pictureInPictureElement: null},
        console: {log() {}},
    }, {filename: source_path});

    const player = {
        template: {notice: {textContent: ''}},
        container: {classList: {contains: () => false}},
        video: {pause() {}},
        danmaku: {clear() {}},
        notice() {},
        hideNotice() {},
    };
    const manager = new exports.default(player);

    function resolveIdlingSleep() {
        const index = sleeps.findIndex((sleep) => sleep.seconds === 1);
        assert.notEqual(index, -1, 'Idling must wait before requesting a restart');
        sleeps.splice(index, 1)[0].resolve();
    }

    return {manager, connections, restart_events, resolveIdlingSleep};
}

test('Idling が継続している接続では待機後に再起動を要求する', async () => {
    const {manager, connections, restart_events, resolveIdlingSleep} = createManager();
    try {
        await manager.init();
        const pending = connections[0].sendStatus('Idling');
        assert.equal(restart_events.length, 0);
        resolveIdlingSleep();
        await pending;
        assert.equal(restart_events.length, 1);
        assert.equal(restart_events[0].name, 'PlayerRestartRequired');
    } finally {
        await manager.destroy();
    }
});

test('待機中に破棄された接続は再起動を要求しない', async () => {
    const {manager, connections, restart_events, resolveIdlingSleep} = createManager();
    await manager.init();
    const pending = connections[0].sendStatus('Idling');
    await manager.destroy();
    assert.equal(connections[0].closed, true);
    resolveIdlingSleep();
    await pending;
    assert.equal(restart_events.length, 0);
});

for (const status of ['Standby', 'ONAir', 'Offline']) {
    test(`待機中に ${status} へ変わった接続は古い Idling 通知で再起動しない`, async () => {
        const {manager, connections, restart_events, resolveIdlingSleep} = createManager();
        try {
            await manager.init();
            const pending = connections[0].sendStatus('Idling');
            await connections[0].sendStatus(status);
            resolveIdlingSleep();
            await pending;
            assert.equal(restart_events.length, 0);
        } finally {
            await manager.destroy();
        }
    });
}

test('同じ Manager を再初期化した後は新しい接続の Idling 通知だけが再起動を要求する', async () => {
    const {manager, connections, restart_events, resolveIdlingSleep} = createManager();
    try {
        await manager.init();
        const old_pending = connections[0].sendStatus('Idling');
        await manager.destroy();
        assert.equal(connections[0].closed, true);
        await manager.init();
        const new_pending = connections[1].sendStatus('Idling');

        // 新旧両方の接続が Idling でも、破棄前の接続は再起動を要求してはいけない。
        resolveIdlingSleep();
        await old_pending;
        assert.equal(restart_events.length, 0);
        resolveIdlingSleep();
        await new_pending;
        assert.equal(restart_events.length, 1);
    } finally {
        await manager.destroy();
    }
});
