/**
 * Floating-Vue の v-tooltip グローバルディレクティブが Vuetify 3.6 系以降で実装された v-tooltip グローバルディレクティブと競合するため、
 * Floating-Vue 側のグローバルディレクティブを異なる名前で登録するためのプラグイン
 * ref: https://github.com/Akryum/floating-vue/blob/main/packages/floating-vue/src/index.ts
 */

import { VTooltip as PrivateVTooltip, VClosePopper as PrivateVClosePopper, Tooltip, Dropdown, Menu, options as config } from 'floating-vue';
import { App } from 'vue';


// https://github.com/Akryum/floating-vue/blob/main/packages/floating-vue/src/util/assign-deep.ts
function assign(to: any, from: any) {
    for (const key in from) {
        if (Object.prototype.hasOwnProperty.call(from, key)) {
            if (typeof from[key] === 'object' && to[key]) {
                assign(to[key], from[key]);
            } else {
                to[key] = from[key];
            }
        }
    }
}

export function install(app: App, options: any = {}) {
    if ((app as any).$fTooltipInstalled) return;
    (app as any).$fTooltipInstalled = true;

    assign(config, options);

    // Directive
    app.directive('ftooltip', PrivateVTooltip);  // v-tooltip -> v-ftooltip
    app.directive('fclose-popper', PrivateVClosePopper);  // v-close-popper -> v-fclose-popper
    // Components
    app.component('FTooltip', Tooltip);  // VTooltip -> FTooltip
    app.component('FDropdown', Dropdown);  // VDropdown -> FDropdown
    app.component('FMenu', Menu);  // VMenu -> FMenu
}

const plugin = {
    install,
    options: config,
};

export default plugin;
