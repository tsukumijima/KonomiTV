<template>
    <div class="breadcrumbs" v-if="crumbs">
        <router-link v-for="(crumb, index) in crumbs" :key="index" :to="crumb.path">
            {{crumb.name}}
            <Icon v-if="index < crumbs.length - 1" icon="fluent:chevron-right-12-regular" width="16px" class="mx-1" />
        </router-link>
    </div>
</template>
<script lang="ts" setup>


// Props
defineProps<{
    crumbs: { name: string; path: string; }[];
}>();

</script>
<style lang="scss" scoped>

.breadcrumbs {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 13px;
    color: rgb(var(--v-theme-text-darken-1));
    @include smartphone-vertical {
        display: none;
    }

    a {
        display: flex;
        align-items: center;
        text-decoration: none;
        color: inherit;
        transition: color 0.15s;

        &:hover {
            color: rgb(var(--v-theme-text));
        }
    }
}

</style>