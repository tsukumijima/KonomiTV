<template>
    <div class="route-container">
        <nav class="watch-navigation">
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/tv/">
                <Icon class="watch-navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/video/">
                <Icon class="watch-navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/schedules/">
                <Icon class="watch-navigation__link-icon" icon="fluent:calendar-ltr-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/captures/">
                <Icon class="watch-navigation__link-icon" icon="fluent:image-multiple-24-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/watchlist/">
                <Icon class="watch-navigation__link-icon" icon="ic:round-playlist-play" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/history/">
                <Icon class="watch-navigation__link-icon" icon="fluent:history-16-regular" width="26px" />
            </router-link>
            <v-spacer></v-spacer>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/settings/">
                <Icon class="watch-navigation__link-icon" icon="fluent:settings-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/version/">
                <Icon class="watch-navigation__link-icon" icon="fluent:info-16-regular" width="26px" />
            </router-link>
        </nav>
        <main class="watch-container watch-container--panel-display">
            <div class="watch-content">
                <header class="watch-header">
                    <img class="watch-header__broadcaster" src="http://192.168.1.36:7000/api/channels/gr011/logo">
                    <span class="watch-header__program-title">ニュースウオッチ9▽自宅療養者激増保健所は医療機関は…▽脱プラ企業は家庭は</span>
                    <span class="watch-header__program-time">21:00 ～ 22:00</span>
                    <v-spacer></v-spacer>
                    <span class="watch-header__now">2021/08/23 21:56:01</span>
                </header>
                <div class="watch-player">
                    <div class="watch-player__button">
                        <div v-ripple class="switch-button switch-button-up">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-left-24-filled" width="31px" rotate="1" />
                        </div>
                        <div v-ripple class="switch-button switch-button-panel switch-button-panel--open">
                            <Icon class="switch-button-icon" icon="fluent:navigation-16-filled" width="31px" />
                        </div>
                        <div v-ripple class="switch-button switch-button-down">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-right-24-filled" width="31px" rotate="1" />
                        </div>
                    </div>
                </div>
            </div>
            <div class="watch-panel">
                <div class="watch-panel__header">
                    <div class="panel-close-button">
                        <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
                        <span class="panel-close-button__text">閉じる</span>
                    </div>
                    <v-spacer></v-spacer>
                    <div class="panel-broadcaster">
                        <img class="panel-broadcaster__icon" src="http://192.168.1.36:7000/api/channels/gr011/logo">
                        <div class="panel-broadcaster__number">011</div>
                        <div class="panel-broadcaster__name">NHK総合1・東京</div>
                    </div>
                </div>
                <div class="watch-panel__content">
                    <section class="program-info">
                        <h1 class="program-info__title">スーパーカブ 第1話「ないないの女の子」</h1>
                        <div class="program-info__time">2021/04/08 (木) 01:35 ～ 02:05 (30分)</div>
                        <div class="program-info__description">朝目を覚ましそそくさと朝食を済ませ、お弁当を用意し家を出る。親はいない、お金もない、趣味もない、友達と呼べる人も将来の目標もない、「ないないづくし」の…。</div>
                        <div class="program-info__next-title">
                            <span class="program-info__next-title-decorate">NEXT</span>
                            <Icon class="program-info__next-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                            <span class="program-info__next-title-text">MIRAI系アイドルTV</span>
                        </div>
                        <div class="program-info__next-time">2021/04/08 (木) 01:35 ～ 02:05 (30分)</div>
                        <div class="program-info__status">
                            <Icon icon="fa-solid:eye" height="14px" />
                            <span class="ml-2">0</span>
                            <Icon class="ml-5" icon="fa-solid:fire-alt" height="14px" />
                            <span class="ml-2">0</span>
                            <Icon class="ml-5" icon="bi:chat-left-text-fill" height="14px" />
                            <span class="ml-2">0</span>
                        </div>
                    </section>
                    <section class="program-detail">
                        <h2 class="program-detail__heading">番組内容</h2>
                        <div class="program-detail__text">
                            【STORY】<br>
                            私にはなにもない。と思っていた。<br>
                            山梨県北杜市の高校に通う女の子、小熊。<br>
                            両親も友達も趣味も無い、<br>
                            何も無い日々を過ごす彼女だが、<br>
                            ふと見かけた中古のスーパーカブを買ったことで、ちょっとずつ短調な毎日が変わり始める。<br>
                        </div>
                    </section>
                </div>
                <div class="watch-panel__navigation">
                    <div v-ripple class="panel-navigation-button panel-navigation-button--active">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                        <span class="panel-navigation-button__text">番組情報</span>
                    </div>
                    <div v-ripple class="panel-navigation-button">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                        <span class="panel-navigation-button__text">チャンネル</span>
                    </div>
                    <div v-ripple class="panel-navigation-button">
                        <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="31px" />
                        <span class="panel-navigation-button__text">コメント</span>
                    </div>
                    <div v-ripple class="panel-navigation-button">
                        <Icon class="panel-navigation-button__icon" icon="fa-brands:twitter" width="34px" />
                        <span class="panel-navigation-button__text">Twitter</span>
                    </div>
                </div>
            </div>
        </main>
    </div>
</template>

<script lang="ts">
import Vue from 'vue';
import { Icon } from '@iconify/vue2';

export default Vue.extend({
    name: 'Home',
    components: {
        Icon,
    },
    data() {
        return {
        }
    },
    // 開始時に実行
    created() {
    },
    // 終了時に実行
    destroyed() {
    },
    methods: {
    }
});
</script>

<style lang="scss" scoped>
.route-container {
    background: #000000 !important;
}
.watch-navigation {
    display: flex;
    flex-direction: column;
    position: fixed;
    padding: 22px 8px;
    padding-top: 87px;
    width: 68px;
    top: 0px;
    left: 0px;
    bottom: 0px;
    background: #2F221F80;
    z-index: 1;

    .watch-navigation__link {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 52px;
        border-radius: 11px;
        font-size: 16px;
        color: var(--v-text-base);
        transition: background-color 0.15s;
        text-decoration: none;
        user-select: none;

        &:hover {
            background: #433532A0;
        }

        &--active {
            color: var(--v-primary-base);
            background: #433532A0;
        }
        + .watch-navigation__link {
            margin-top: 4px;
        }
    }
}

.watch-container {
    display: flex;
    width: calc(100% + 352px);  // パネルの幅分はみ出す
    transition: width 0.4s;

    // パネル表示時
    &--panel-display {
        width: calc(100%);  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: var(--v-primary-base);
        }
    }

    .watch-content {
        display: flex;
        position: relative;
        width: 100%;

        .watch-header {
            display: flex;
            align-items: center;
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 82px;
            padding-left: calc(68px + 30px);
            padding-right: 30px;
            background: linear-gradient(to bottom, var(--v-background-base), transparent);
            z-index: 2;

            .watch-header__broadcaster {
                display: inline-block;
                flex-shrink: 0;
                width: 64px;
                height: 35px;
                border-radius: 5px;
                background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                object-fit: cover;
                user-select: none;
            }

            .watch-header__program-title {
                margin-left: 18px;
                font-size: 18px;
                font-weight: bold;
                font-feature-settings: "palt" 1;  // 文字詰め
                letter-spacing: 0.05em;  // 字間を少し空ける
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
            }

            .watch-header__program-time {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 15px;
            }

            .watch-header__now {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 13px;
            }
        }

        .watch-player {
            display: flex;
            position: relative;
            width: 100%;
            height: 100vh;
            background-size: contain;
            background-position: center;
            background-image: url(https://blog.tsukumijima.net/wp-content/uploads/2019/09/IMG_5687_1-e1593344299158.jpg);  // 仮

            .watch-player__button {
                display: flex;
                justify-content: space-around;
                flex-direction: column;
                position: absolute;
                top: 50%;
                right: 20px;
                height: 190px;
                transform: translateY(-50%);

                .switch-button {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    width: 48px;
                    height: 48px;
                    background: #2F221FC0;
                    border-radius: 7px;
                    user-select: none;
                    cursor: pointer;

                    .switch-button-icon {
                        position: relative;
                    }

                    &-up > .switch-button-icon {
                        top: 6px;
                        left: 1px;
                    }
                    &-panel > .switch-button-icon {
                        top: 1.5px;
                        transition: color 0.4s;
                    }
                    &-down > .switch-button-icon {
                        bottom: 4px;
                        left: 1px;
                    }
                }
            }
        }
    }

    .watch-panel {
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        width: 352px;
        height: 100vh;
        background: var(--v-background-base);

        .watch-panel__header {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            width: 100%;
            height: 70px;
            padding-left: 16px;
            padding-right: 16px;

            .panel-close-button {
                display: flex;
                align-items: center;
                flex-shrink: 0;
                height: 35px;
                user-select: none;
                cursor: pointer;

                &__icon {
                    position: relative;
                    left: -4px;
                }
                &__text {
                    font-weight: bold;
                }
            }

            .panel-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;
                margin-left: 16px;

                &__icon {
                    display: inline-block;
                    flex-shrink: 0;
                    width: 43px;
                    height: 24px;
                    border-radius: 3px;
                    background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                    object-fit: cover;
                    user-select: none;
                }

                &__number {
                    flex-shrink: 0;
                    margin-left: 8px;
                    font-size: 16px;
                }

                &__name {
                    margin-left: 5px;
                    font-size: 16px;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                }
            }
        }

        .watch-panel__content {
            height: 100%;
            padding-left: 16px;
            padding-right: calc(16px - 10px);  // スクロールバーの幅を引く
            overflow-y: scroll;

            .program-info {
                .program-info__title {
                    font-size: 22px;
                    font-weight: bold;
                    line-height: 140%;
                    font-feature-settings: "palt" 1;  // 文字詰め
                    letter-spacing: 0.05em;  // 字間を少し空ける
                }
                .program-info__time {
                    margin-top: 8px;
                    color: var(--v-text-darken1);
                    font-size: 14px;
                }
                .program-info__description {
                    margin-top: 12px;
                    color: var(--v-text-darken1);
                    font-size: 12px;
                    line-height: 165%;
                    font-feature-settings: "palt" 1;  // 文字詰め
                    letter-spacing: 0.07em;  // 字間を少し空ける
                }
                .program-info__next-title {
                    display: flex;
                    align-items: center;
                    margin-top: 12px;
                    color: var(--v-text-darken1);
                    font-size: 14px;
                    &-decorate {
                        flex-shrink: 0;
                    }
                    &-icon {
                        flex-shrink: 0;
                        margin-left: 3px;
                    }
                    &-text {
                        display: -webkit-box;
                        margin-left: 3px;
                        overflow: hidden;
                        -webkit-line-clamp: 2;  // 2行までに制限
                        -webkit-box-orient: vertical;
                    }
                }
                .program-info__next-time {
                    margin-top: 2px;
                    color: var(--v-text-darken1);
                    font-size: 14px;
                }
                .program-info__status {
                    display: flex;
                    align-items: center;
                    margin-top: 12px;
                    font-size: 15px;
                    color: var(--v-text-darken1);
                }
            }

            .program-detail {
                margin-top: 24px;

                .program-detail__heading {
                    font-size: 18px;
                }
                .program-detail__text {
                    margin-top: 8px;
                    color: var(--v-text-darken1);
                    font-size: 12px;
                    line-height: 165%;
                    font-feature-settings: "palt" 1;  // 文字詰め
                    letter-spacing: 0.07em;  // 字間を少し空ける
                }
            }
        }

        .watch-panel__navigation {
            display: flex;
            align-items: center;
            justify-content: space-evenly;
            flex-shrink: 0;
            height: 77px;
            background: var(--v-background-lighten1);

            .panel-navigation-button {
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                width: 66px;
                height: 56px;
                padding: 6px 4px;
                border-radius: 5px;
                color: var(--v-text-base);
                box-sizing: content-box;
                user-select: none;
                cursor: pointer;

                &--active {
                    color: var(--v-primary-base);
                }

                &__icon {
                    height: 30px;
                }
                &__text {
                    margin-top: 5px;
                    font-size: 13px;
                }
            }
        }
    }
}
</style>
