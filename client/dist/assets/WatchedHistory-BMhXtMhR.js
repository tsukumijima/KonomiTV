import{d as v,u as y,q as r,s as m,x as f,z as w,c as B,a as i,b as p,B as b,o as q,_ as S}from"./index-B7OgWKtM.js";import{B as H,R as M}from"./RecordedProgramList-c8g7Jb3l.js";import{H as V,N as x}from"./Navigation-CnqcZDIH.js";import{V as N}from"./Videos-d0PD3lY7.js";import"./VDialog-B5uyaSNw.js";import"./VChip-CXvR9eN_.js";import"./VTextField-Cn4WKwf3.js";import"./VAvatar-CxE9IZav.js";import"./VCard-CZrRuC1N.js";import"./ssrBoot-CgU2lsL7.js";import"./VSelect-9qvNrm53.js";const R={class:"route-container"},k={class:"watched-history-container-wrapper"},E={class:"watched-history-container"},I=v({__name:"WatchedHistory",setup(L){const s=w(),g=b(),l=y(),n=r([]),c=r(0),t=r(!0),a=r(1),u=async()=>{const e=l.settings.watched_history.sort((d,h)=>h.updated_at-d.updated_at).map(d=>d.video_id);if(e.length===0){n.value=[],c.value=0,t.value=!1;return}const o=await N.fetchVideos("ids",a.value,e);o&&(n.value=o.recorded_programs,c.value=o.total),t.value=!1},_=async e=>{a.value=e,t.value=!0,await g.replace({query:{...s.query,page:e.toString()}})};return m(()=>s.query,async e=>{e.page&&(a.value=parseInt(e.page)),await u()},{deep:!0}),m(()=>l.settings.watched_history,async()=>{await u()},{deep:!0}),f(async()=>{s.query.page&&(a.value=parseInt(s.query.page)),await u()}),(e,o)=>(q(),B("div",R,[i(V),p("main",null,[i(x),p("div",k,[p("div",E,[i(H,{crumbs:[{name:"ホーム",path:"/"},{name:"視聴履歴",path:"/watched-history/",disabled:!0}]}),i(M,{title:"視聴履歴",programs:n.value,total:c.value,page:a.value,hideSort:!0,isLoading:t.value,showBackButton:!0,showEmptyMessage:!t.value,emptyMessage:"まだ視聴履歴がありません。",emptySubMessage:"録画番組を30秒以上みると、<br class='d-sm-none'>視聴履歴に追加されます。",forWatchedHistory:!0,"onUpdate:page":_},null,8,["programs","total","page","isLoading","showEmptyMessage"])])])])]))}}),K=S(I,[["__scopeId","data-v-66d144f1"]]);export{K as default};
