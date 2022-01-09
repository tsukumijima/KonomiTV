
import { VueConstructor, VNode } from 'vue';

import { convertToUnit } from 'vuetify/lib/util/helpers'
import VTabs from 'vuetify/lib/components/VTabs/VTabs';
import VTabsBar from '@/components/VTabsBar';

export default (VTabs as VueConstructor).extend({
    methods: {

        // VTabsBar は VTabs から暗黙的に生成されるコンポーネントのため、直接上書きすることができない
        // そこで VTabs 自体も上書きし、VTabs で $createElement() される時の VTabsBar を自前でオーバーライドしたものに差し替える
        // ビルド済みのファイルには型定義が入っていないので any を多用せざるを得ない…
        genBar(items: VNode[], slider: VNode | null) {
            const data = {
                style: {
                    height: convertToUnit((this as any).height),
                },
                props: {
                    activeClass: (this as any).activeClass,
                    centerActive: (this as any).centerActive,
                    dark: (this as any).dark,
                    light: (this as any).light,
                    mandatory: !(this as any).optional,
                    mobileBreakpoint: (this as any).mobileBreakpoint,
                    nextIcon: (this as any).nextIcon,
                    prevIcon: (this as any).prevIcon,
                    showArrows: (this as any).showArrows,
                    value: (this as any).internalValue,
                },
                on: {
                    'call:slider': (this as any).callSlider,
                    change: (val: any) => {
                        (this as any).internalValue = val;
                    },
                },
                ref: 'items',
            };

            (this as any).setTextColor((this as any).computedColor, data);
            (this as any).setBackgroundColor((this as any).backgroundColor, data);

            // ここでオーバーライドした VTabsBar を使うのが最重要
            // これをやるためだけにわざわざ VTabs に関してもオーバーライドする羽目になってる…
            return (this as any).$createElement(VTabsBar, data, [
                (this as any).genSlider(slider),
                items,
            ]);
        }
    }
});
