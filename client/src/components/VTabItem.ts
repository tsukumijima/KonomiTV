
import { VueConstructor, VNode } from 'vue';

import VTabItem from 'vuetify/lib/components/VTabs/VTabItem';

// VTabItem は VWindowItem を extend() して実装されている
export default (VTabItem as VueConstructor).extend({
    render (h): VNode {
        return h('transition', {
            props: {
                name: (this as any).computedTransition,
            },
            on: {
                // Handlers for enter windows.
                beforeEnter: (this as any).onBeforeTransition,
                afterEnter: (this as any).onAfterTransition,
                enterCancelled: (this as any).onTransitionCancelled,

                // Handlers for leave windows.
                beforeLeave: (this as any).onBeforeTransition,
                afterLeave: (this as any).onAfterTransition,
                leaveCancelled: (this as any).onTransitionCancelled,

                // Enter handler for height transition.
                enter: (this as any).onEnter,
            }
        // this.showLazyContent() を通さずに常にレンダリングされるようにする
        // 本来は実際に表示されている時だけレンダリングし、負荷を減らすための処理
        // ただチャンネルリストのレンダリングは重いので、最初からレンダリングされていた方がタブの初回切り替えが早くなる
        }, [(this as any).genWindowItem()]);
    }
});
