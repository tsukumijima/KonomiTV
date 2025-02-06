const Spritesmith = require("spritesmith");
const sharp = require("sharp");
const fs = require("fs");
const { dirname } = require("path");
const crypto = require("crypto");
const baseDir = dirname(__dirname) + "/server/static/logos/";

let channelMapper = {
    default: "default.png",
    "NID1-SID400": "NID1-SID400.png",
    "NID4-SID101": "NID4-SID101.png",
    "NID4-SID103": "NID4-SID103.png",
    "NID4-SID141": "NID4-SID141.png",
    "NID4-SID151": "NID4-SID151.png",
    "NID4-SID161": "NID4-SID161.png",
    "NID4-SID171": "NID4-SID171.png",
    "NID4-SID181": "NID4-SID181.png",
    "NID4-SID191": "NID4-SID191.png",
    "NID4-SID192": "NID4-SID192.png",
    "NID4-SID193": "NID4-SID193.png",
    "NID4-SID200": "NID4-SID200.png",
    "NID4-SID201": "NID4-SID201.png",
    "NID4-SID202": "NID4-SID202.png",
    "NID4-SID211": "NID4-SID211.png",
    "NID4-SID222": "NID4-SID222.png",
    "NID4-SID231": "NID4-SID231.png",
    "NID4-SID232": "NID4-SID232.png",
    "NID4-SID234": "NID4-SID234.png",
    "NID4-SID236": "NID4-SID236.png",
    "NID4-SID241": "NID4-SID241.png",
    "NID4-SID242": "NID4-SID242.png",
    "NID4-SID243": "NID4-SID243.png",
    "NID4-SID244": "NID4-SID244.png",
    "NID4-SID245": "NID4-SID245.png",
    "NID4-SID251": "NID4-SID251.png",
    "NID4-SID252": "NID4-SID252.png",
    "NID4-SID255": "NID4-SID255.png",
    "NID4-SID256": "NID4-SID256.png",
    "NID4-SID260": "NID4-SID260.png",
    "NID4-SID263": "NID4-SID263.png",
    "NID4-SID265": "NID4-SID265.png",
    "NID4-SID531": "NID4-SID531.png",
    "NID6-SID055": "NID6-SID055.png",
    "NID6-SID218": "NID6-SID218.png",
    "NID6-SID219": "NID6-SID219.png",
    "NID6-SID296": "NID6-SID296.png",
    "NID6-SID298": "NID6-SID298.png",
    "NID6-SID299": "NID6-SID299.png",
    "NID6-SID317": "NID6-SID317.png",
    "NID6-SID318": "NID6-SID318.png",
    "NID6-SID339": "NID6-SID339.png",
    "NID6-SID349": "NID6-SID349.png",
    "NID6-SID800": "NID6-SID800.png",
    "NID6-SID801": "NID6-SID801.png",
    "NID7-SID161": "NID7-SID161.png",
    "NID7-SID223": "NID7-SID223.png",
    "NID7-SID227": "NID7-SID227.png",
    "NID7-SID240": "NID7-SID240.png",
    "NID7-SID250": "NID7-SID250.png",
    "NID7-SID254": "NID7-SID254.png",
    "NID7-SID257": "NID7-SID257.png",
    "NID7-SID262": "NID7-SID262.png",
    "NID7-SID290": "NID7-SID290.png",
    "NID7-SID292": "NID7-SID292.png",
    "NID7-SID293": "NID7-SID293.png",
    "NID7-SID294": "NID7-SID294.png",
    "NID7-SID295": "NID7-SID295.png",
    "NID7-SID297": "NID7-SID297.png",
    "NID7-SID300": "NID7-SID300.png",
    "NID7-SID301": "NID7-SID301.png",
    "NID7-SID305": "NID7-SID305.png",
    "NID7-SID307": "NID7-SID307.png",
    "NID7-SID308": "NID7-SID308.png",
    "NID7-SID309": "NID7-SID309.png",
    "NID7-SID310": "NID7-SID310.png",
    "NID7-SID311": "NID7-SID311.png",
    "NID7-SID312": "NID7-SID312.png",
    "NID7-SID314": "NID7-SID314.png",
    "NID7-SID316": "NID7-SID316.png",
    "NID7-SID321": "NID7-SID321.png",
    "NID7-SID322": "NID7-SID322.png",
    "NID7-SID323": "NID7-SID323.png",
    "NID7-SID324": "NID7-SID324.png",
    "NID7-SID325": "NID7-SID325.png",
    "NID7-SID329": "NID7-SID329.png",
    "NID7-SID330": "NID7-SID330.png",
    "NID7-SID331": "NID7-SID331.png",
    "NID7-SID333": "NID7-SID333.png",
    "NID7-SID340": "NID7-SID340.png",
    "NID7-SID341": "NID7-SID341.png",
    "NID7-SID342": "NID7-SID342.png",
    "NID7-SID343": "NID7-SID343.png",
    "NID7-SID351": "NID7-SID351.png",
    "NID7-SID353": "NID7-SID353.png",
    "NID7-SID354": "NID7-SID354.png",
    "NID7-SID363": "NID7-SID363.png",
    "NID10-SID33286": "NID10-SID33286.png",
    "NID10-SID33289": "NID10-SID33289.png",
    "NID10-SID33291": "NID10-SID33291.png",
    "NID10-SID33293": "NID10-SID33293.png",
    "NID10-SID33295": "NID10-SID33295.png",
    "NID10-SID33296": "NID10-SID33296.png",
    "NID10-SID33297": "NID10-SID33297.png",
    "NID10-SID33303": "NID10-SID33303.png",
    "NID10-SID33304": "NID10-SID33304.png",
    "NID10-SID33305": "NID10-SID33305.png",
    "NID10-SID33308": "NID10-SID33308.png",
    "NID10-SID33310": "NID10-SID33310.png",
    "NID10-SID33312": "NID10-SID33312.png",
    "NID10-SID33314": "NID10-SID33314.png",
    "NID10-SID33328": "NID10-SID33328.png",
    "NID10-SID33333": "NID10-SID33333.png",
    "NID10-SID33334": "NID10-SID33334.png",
    "NID10-SID33335": "NID10-SID33335.png",
    "NID10-SID33336": "NID10-SID33336.png",
    "NID10-SID33338": "NID10-SID33338.png",
    "NID10-SID33339": "NID10-SID33339.png",
    "NID10-SID33340": "NID10-SID33340.png",
    "NID10-SID33347": "NID10-SID33347.png",
    "NID10-SID33348": "NID10-SID33348.png",
    "NID10-SID33349": "NID10-SID33349.png",
    "NID10-SID33352": "NID10-SID33352.png",
    "NID10-SID33353": "NID10-SID33353.png",
    "NID10-SID33354": "NID10-SID33354.png",
    "NID10-SID33355": "NID10-SID33355.png",
    "NID10-SID33356": "NID10-SID33356.png",
    "NID10-SID33357": "NID10-SID33357.png",
    "NID10-SID33358": "NID10-SID33358.png",
    "NID10-SID33359": "NID10-SID33359.png",
    "NID10-SID33360": "NID10-SID33360.png",
    "NID10-SID33361": "NID10-SID33361.png",
    "NID10-SID33362": "NID10-SID33362.png",
    "NID10-SID33364": "NID10-SID33364.png",
    "NID10-SID33367": "NID10-SID33367.png",
    "NID10-SID33368": "NID10-SID33368.png",
    "NID10-SID33369": "NID10-SID33369.png",
    "NID10-SID33370": "NID10-SID33370.png",
    "NID10-SID33371": "NID10-SID33371.png",
    "NID10-SID33372": "NID10-SID33372.png",
    "NID10-SID33373": "NID10-SID33373.png",
    "NID10-SID33374": "NID10-SID33374.png",
    "NID10-SID33375": "NID10-SID33375.png",
    "NID10-SID33376": "NID10-SID33376.png",
    "NID10-SID33377": "NID10-SID33377.png",
    "NID10-SID33379": "NID10-SID33379.png",
    "NID10-SID33380": "NID10-SID33380.png",
    "NID10-SID33381": "NID10-SID33381.png",
    "NID10-SID33382": "NID10-SID33382.png",
    "NID10-SID33383": "NID10-SID33383.png",
    "NID10-SID33384": "NID10-SID33384.png",
    "NID10-SID33385": "NID10-SID33385.png",
    "NID10-SID33386": "NID10-SID33386.png",
    "NID10-SID33387": "NID10-SID33387.png",
    "NID10-SID33388": "NID10-SID33388.png",
    "NID10-SID33389": "NID10-SID33389.png",
    "NID10-SID33390": "NID10-SID33390.png",
    "NID10-SID33391": "NID10-SID33391.png",
    "NID10-SID33393": "NID10-SID33393.png",
    "NID10-SID33394": "NID10-SID33394.png",
    "NID10-SID33395": "NID10-SID33395.png",
    "NID10-SID33396": "NID10-SID33396.png",
    "NID10-SID33397": "NID10-SID33397.png",
    "NID10-SID33398": "NID10-SID33398.png",
    "NID10-SID33399": "NID10-SID33399.png",
    "NID10-SID33400": "NID10-SID33400.png",
    "NID10-SID33401": "NID10-SID33401.png",
    "NID10-SID33402": "NID10-SID33402.png",
    "NID10-SID33403": "NID10-SID33403.png",
    "NID10-SID33404": "NID10-SID33404.png",
    "NID10-SID33406": "NID10-SID33406.png",
    "NID10-SID33408": "NID10-SID33408.png",
    "NID10-SID33409": "NID10-SID33409.png",
    "NID10-SID33410": "NID10-SID33410.png",
    "NID10-SID33411": "NID10-SID33411.png",
    "NID10-SID33412": "NID10-SID33412.png",
    "NID10-SID33413": "NID10-SID33413.png",
    "NID10-SID33415": "NID10-SID33415.png",
    "NID10-SID33417": "NID10-SID33417.png",
    "NID10-SID33418": "NID10-SID33418.png",
    "NID10-SID33419": "NID10-SID33419.png",
    "NID10-SID33422": "NID10-SID33422.png",
    "NID10-SID33423": "NID10-SID33423.png",
    "NID10-SID33424": "NID10-SID33424.png",
    "NID10-SID33425": "NID10-SID33425.png",
    "NID10-SID33426": "NID10-SID33426.png",
    "NID10-SID33427": "NID10-SID33427.png",
    "NID10-SID33428": "NID10-SID33428.png",
    "NID10-SID33429": "NID10-SID33429.png",
    "NID10-SID33430": "NID10-SID33430.png",
    "NID10-SID33431": "NID10-SID33431.png",
    "NID10-SID33432": "NID10-SID33432.png",
    "NID10-SID33433": "NID10-SID33433.png",
    "NID10-SID33435": "NID10-SID33435.png",
    "NID10-SID33436": "NID10-SID33436.png",
    "NID10-SID33437": "NID10-SID33437.png",
    "NID10-SID33438": "NID10-SID33438.png",
    "NID10-SID33440": "NID10-SID33440.png",
    "NID10-SID33442": "NID10-SID33442.png",
    "NID10-SID33443": "NID10-SID33443.png",
    "NID10-SID33444": "NID10-SID33444.png",
    "NID10-SID33445": "NID10-SID33445.png",
    "NID10-SID33446": "NID10-SID33446.png",
    "NID10-SID33448": "NID10-SID33448.png",
    "NID10-SID33449": "NID10-SID33449.png",
    "NID10-SID33450": "NID10-SID33450.png",
    "NID10-SID33451": "NID10-SID33451.png",
    "NID10-SID33452": "NID10-SID33452.png",
    "NID10-SID33456": "NID10-SID33456.png",
    "NID10-SID33457": "NID10-SID33457.png",
    "NID10-SID33458": "NID10-SID33458.png",
    "NID10-SID33459": "NID10-SID33459.png",
    "NID10-SID33460": "NID10-SID33460.png",
    "NID10-SID33461": "NID10-SID33461.png",
    "NID10-SID33462": "NID10-SID33462.png",
    "NID10-SID33463": "NID10-SID33463.png",
    "NID10-SID33469": "NID10-SID33469.png",
    "NID10-SID33470": "NID10-SID33470.png",
    "NID10-SID33471": "NID10-SID33471.png",
    "NID10-SID33710": "NID10-SID33710.png",
    "NID10-SID33711": "NID10-SID33711.png",
    "NID10-SID33712": "NID10-SID33712.png",
    "NID10-SID33713": "NID10-SID33713.png",
    "NID10-SID33714": "NID10-SID33714.png",
    "NID10-SID33715": "NID10-SID33715.png",
    "NID10-SID33725": "NID10-SID33725.png",
    "NID10-SID33726": "NID10-SID33726.png",
    "NID10-SID33727": "NID10-SID33727.png",
    "NID10-SID33728": "NID10-SID33728.png",
    "NID10-SID33731": "NID10-SID33731.png",
    "NID10-SID33732": "NID10-SID33732.png",
    "NID10-SID33733": "NID10-SID33733.png",
    "NID10-SID33734": "NID10-SID33734.png",
    "NID10-SID33735": "NID10-SID33735.png",
    "NID11-SID101": "NID11-SID101.png",
    "NID11-SID102": "NID11-SID102.png",
    "NID11-SID141": "NID11-SID141.png",
    "NID11-SID151": "NID11-SID151.png",
    "NID11-SID161": "NID11-SID161.png",
    "NID11-SID171": "NID11-SID171.png",
    "NID11-SID181": "NID11-SID181.png",
    "NID11-SID211": "NID11-SID211.png",
    "NID11-SID221": "NID11-SID221.png",
    "NID31762-SID63504": "NID31762-SID63504.png",
    "NID31764-SID63520": "NID31764-SID63520.png",
    "NID31767-SID63544": "NID31767-SID63544.png",
    "NID31778-SID62480": "NID31778-SID62480.png",
    "NID31794-SID61456": "NID31794-SID61456.png",
    "NID31795-SID61464": "NID31795-SID61464.png",
    "NID31796-SID61472": "NID31796-SID61472.png",
    "NID31810-SID60432": "NID31810-SID60432.png",
    "NID31811-SID60440": "NID31811-SID60440.png",
    "NID31826-SID59408": "NID31826-SID59408.png",
    "NID31827-SID59416": "NID31827-SID59416.png",
    "NID31828-SID59424": "NID31828-SID59424.png",
    "NID31829-SID59432": "NID31829-SID59432.png",
    "NID31842-SID58384": "NID31842-SID58384.png",
    "NID31843-SID58392": "NID31843-SID58392.png",
    "NID31844-SID58400": "NID31844-SID58400.png",
    "NID31845-SID58408": "NID31845-SID58408.png",
    "NID31858-SID57360": "NID31858-SID57360.png",
    "NID31859-SID57368": "NID31859-SID57368.png",
    "NID31860-SID57376": "NID31860-SID57376.png",
    "NID31861-SID57384": "NID31861-SID57384.png",
    "NID31874-SID56336": "NID31874-SID56336.png",
    "NID31875-SID56344": "NID31875-SID56344.png",
    "NID31876-SID56352": "NID31876-SID56352.png",
    "NID31877-SID56360": "NID31877-SID56360.png",
    "NID31878-SID56368": "NID31878-SID56368.png",
    "NID31890-SID59312": "NID31890-SID59312.png",
    "NID31891-SID55320": "NID31891-SID55320.png",
    "NID31892-SID55328": "NID31892-SID55328.png",
    "NID31906-SID54288": "NID31906-SID54288.png",
    "NID31938-SID52240": "NID31938-SID52240.png",
    "NID31939-SID52248": "NID31939-SID52248.png",
    "NID31940-SID52256": "NID31940-SID52256.png",
    "NID31941-SID52264": "NID31941-SID52264.png",
    "NID31954-SID51216": "NID31954-SID51216.png",
    "NID31955-SID51224": "NID31955-SID51224.png",
    "NID31956-SID51232": "NID31956-SID51232.png",
    "NID32018-SID47120": "NID32018-SID47120.png",
    "NID32019-SID47128": "NID32019-SID47128.png",
    "NID32020-SID47136": "NID32020-SID47136.png",
    "NID32021-SID47144": "NID32021-SID47144.png",
    "NID32038-SID46128": "NID32038-SID46128.png",
    "NID32054-SID45104": "NID32054-SID45104.png",
    "NID32070-SID44080": "NID32070-SID44080.png",
    "NID32086-SID43056": "NID32086-SID43056.png",
    "NID32102-SID42032": "NID32102-SID42032.png",
    "NID32118-SID41008": "NID32118-SID41008.png",
    "NID32118-SID41009": "NID32118-SID41009.png",
    "NID32118-SID41010": "NID32118-SID41010.png",
    "NID32134-SID39984": "NID32134-SID39984.png",
    "NID32150-SID38960": "NID32150-SID38960.png",
    "NID32150-SID38961": "NID32150-SID38961.png",
    "NID32162-SID37904": "NID32162-SID37904.png",
    "NID32163-SID37912": "NID32163-SID37912.png",
    "NID32164-SID37920": "NID32164-SID37920.png",
    "NID32178-SID36880": "NID32178-SID36880.png",
    "NID32179-SID36888": "NID32179-SID36888.png",
    "NID32194-SID35856": "NID32194-SID35856.png",
    "NID32195-SID35864": "NID32195-SID35864.png",
    "NID32196-SID35872": "NID32196-SID35872.png",
    "NID32197-SID35880": "NID32197-SID35880.png",
    "NID32210-SID34832": "NID32210-SID34832.png",
    "NID32211-SID34840": "NID32211-SID34840.png",
    "NID32212-SID34848": "NID32212-SID34848.png",
    "NID32213-SID34856": "NID32213-SID34856.png",
    "NID32230-SID33840": "NID32230-SID33840.png",
    "NID32242-SID32784": "NID32242-SID32784.png",
    "NID32243-SID32792": "NID32243-SID32792.png",
    "NID32258-SID31760": "NID32258-SID31760.png",
    "NID32259-SID31768": "NID32259-SID31768.png",
    "NID32260-SID31776": "NID32260-SID31776.png",
    "NID32261-SID31784": "NID32261-SID31784.png",
    "NID32274-SID30736": "NID32274-SID30736.png",
    "NID32275-SID30744": "NID32275-SID30744.png",
    "NID32276-SID30752": "NID32276-SID30752.png",
    "NID32277-SID30760": "NID32277-SID30760.png",
    "NID32295-SID29752": "NID32295-SID29752.png",
    "NID32311-SID28728": "NID32311-SID28728.png",
    "NID32327-SID27704": "NID32327-SID27704.png",
    "NID32359-SID25656": "NID32359-SID25656.png",
    "NID32359-SID25657": "NID32359-SID25657.png",
    "NID32375-SID24632": "NID32375-SID24632.png",
    "NID32391-SID23608": "NID32391-SID23608.png",
    "NID32391-SID23610": "NID32391-SID23610.png",
    "NID32402-SID22544": "NID32402-SID22544.png",
    "NID32403-SID22552": "NID32403-SID22552.png",
    "NID32404-SID22560": "NID32404-SID22560.png",
    "NID32418-SID21520": "NID32418-SID21520.png",
    "NID32419-SID21528": "NID32419-SID21528.png",
    "NID32420-SID21536": "NID32420-SID21536.png",
    "NID32421-SID21544": "NID32421-SID21544.png",
    "NID32434-SID20496": "NID32434-SID20496.png",
    "NID32435-SID20504": "NID32435-SID20504.png",
    "NID32436-SID20512": "NID32436-SID20512.png",
    "NID32437-SID20520": "NID32437-SID20520.png",
    "NID32450-SID19472": "NID32450-SID19472.png",
    "NID32451-SID19480": "NID32451-SID19480.png",
    "NID32452-SID19488": "NID32452-SID19488.png",
    "NID32453-SID19496": "NID32453-SID19496.png",
    "NID32466-SID18448": "NID32466-SID18448.png",
    "NID32467-SID18456": "NID32467-SID18456.png",
    "NID32468-SID18464": "NID32468-SID18464.png",
    "NID32482-SID17424": "NID32482-SID17424.png",
    "NID32483-SID17432": "NID32483-SID17432.png",
    "NID32484-SID17440": "NID32484-SID17440.png",
    "NID32485-SID17448": "NID32485-SID17448.png",
    "NID32658-SID6160": "NID32658-SID6160.png",
    "NID32659-SID6168": "NID32659-SID6168.png",
    "NID32660-SID6176": "NID32660-SID6176.png",
    "NID32674-SID5136": "NID32674-SID5136.png",
    "NID32675-SID5144": "NID32675-SID5144.png",
    "NID32676-SID5152": "NID32676-SID5152.png",
    "NID32677-SID5160": "NID32677-SID5160.png",
    "NID32678-SID5168": "NID32678-SID5168.png",
    "NID32690-SID4112": "NID32690-SID4112.png",
    "NID32691-SID4120": "NID32691-SID4120.png",
    "NID32692-SID4128": "NID32692-SID4128.png",
    "NID32693-SID4136": "NID32693-SID4136.png",
    "NID32694-SID4144": "NID32694-SID4144.png",
    "NID32706-SID3088": "NID32706-SID3088.png",
    "NID32707-SID3096": "NID32707-SID3096.png",
    "NID32708-SID3104": "NID32708-SID3104.png",
    "NID32709-SID3112": "NID32709-SID3112.png",
    "NID32722-SID2064": "NID32722-SID2064.png",
    "NID32723-SID2072": "NID32723-SID2072.png",
    "NID32724-SID2080": "NID32724-SID2080.png",
    "NID32725-SID2088": "NID32725-SID2088.png",
    "NID32736-SID1024": "NID32736-SID1024.png",
    "NID32737-SID1032": "NID32737-SID1032.png",
    "NID32738-SID1040": "NID32738-SID1040.png",
    "NID32739-SID1048": "NID32739-SID1048.png",
    "NID32740-SID1056": "NID32740-SID1056.png",
    "NID32741-SID1064": "NID32741-SID1064.png",
    "NID32741-SID1065": "NID32741-SID1065.png",
    "NID32741-SID1066": "NID32741-SID1066.png",
    "NID32742-SID1072": "NID32742-SID1072.png",
    BaycomCH: "community-channels/BaycomCH.png",
    eo光チャンネル: "community-channels/eo光チャンネル.png",
    "J：COMチャンネル": "community-channels/J：COMチャンネル.png",
    "J：COMテレビ": "community-channels/J：COMテレビ.png",
    ZTV: "community-channels/ZTV.png",
    イッツコムch10: "community-channels/イッツコムch10.png",
    イッツコムch11: "community-channels/イッツコムch11.png",
    "スカパー！ナビ1": "community-channels/スカパー！ナビ1.png",
    "スカパー！ナビ2": "community-channels/スカパー！ナビ2.png",
    ベイコム12CH: "community-channels/ベイコム12CH.png",
};
let hashMapper = {};

let channelDupper = {};

let channelXY = {};
let css = `.ch-sprite {
    /* logo default size = 256*/
    --ch-sprite-real-width: 256;
    --ch-sprite-real-height: 256;
    --ch-sprite-scale-ratio: calc(var(--ch-sprite-width) / var(--ch-sprite-real-width));
    --ch-sprite-real-croped-height: calc(var(--ch-sprite-height) / var(--ch-sprite-scale-ratio));
  
    width: calc(var(--ch-sprite-real-width) * 1px);
    height: calc(var(--ch-sprite-real-croped-height) * 1px);
    background-position: calc(-1 * var(--ch-sprite-x) * 1px) calc(-1 * (var(--ch-sprite-y) + (var(--ch-sprite-real-height) - var(--ch-sprite-height) / var(--ch-sprite-scale-ratio)) / 2) * 1px);
    border-radius: calc(var(--ch-sprite-border-radius) / var(--ch-sprite-scale-ratio) * 1px);
    zoom: var(--ch-sprite-scale-ratio);
    transform-origin: top left;
    background-image: url(/assets/images/channel-logo-sprite.webp);
}
.ch-sprite>img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
`;
async function run() {
    for (const key in channelMapper) {
        const path = baseDir + channelMapper[key];
        const hash = await hashFile(path);
        if (hash in hashMapper) {
            if (!channelDupper[hashMapper[hash]]) {
                channelDupper[hashMapper[hash]] = [key];
            } else {
                channelDupper[hashMapper[hash]].push(key);
            }
            delete channelMapper[key];
        } else {
            hashMapper[hash] = key;
            // console.log("ch", key, hash);
        }
    }
    const channelMapperPathReverse = Object.fromEntries(
        Object.entries(channelMapper).map(([key, value]) => [
            baseDir + value,
            key,
        ])
    );
    // console.log(channelDupper);
    Spritesmith.run(
        {
            src: Object.keys(channelMapper)
                // .filter((ch) => {
                //     // //                   = BS                     = BS4K                = CS                     = CS                     = CS
                //     // return ch.startsWith('NID4-') || ch.startsWith('NID11-') || ch.startsWith('NID6-') || ch.startsWith('NID7-') || ch.startsWith('NID10-')
                //     // return ch === "default" || !ch.startsWith("NID3");
                //     return true;
                // })
                .map((ch) => baseDir + channelMapper[ch]),
        },
        async function (err, result) {
            if (err) throw err;
            // fs.writeFileSync(__dirname + '/public/assets/images/BSCS-sprite.png',result.image);

            Object.entries(result.coordinates).forEach(([path, value]) => {
                const key = channelMapperPathReverse[path];
                channelXY[key] = { x: value.x, y: value.y };
                if (channelDupper[key]) {
                    channelDupper[key].forEach((dupch) => {
                        channelXY[dupch] = channelXY[key];
                        // console.log('dup',dupch,key)
                    });
                }
            });
            Object.entries(channelXY).forEach(([id, xy]) => {
                css += `.ch-sprite[chid=${id}] {--ch-sprite-x: ${xy.x};--ch-sprite-y: ${xy.y};}`;
                css += `.ch-sprite[chid=${id}] > img{display:none;}`;
                css += "\n";
            });

            fs.writeFileSync(__dirname + "/src/styles/channel-logo.css", css);
            console.log(channelXY);
            sharp(result.image)
                .png({ compressionLevel: 9 })
                .webp({ quality: 80 })
                .toFile(
                    __dirname + "/public/assets/images/channel-logo-sprite.webp"
                );
        }
    );
}
run();

async function hashFile(path) {
    const fileBuffer = fs.readFileSync(path);
    const hash = crypto.createHash("sha256").update(fileBuffer).digest("hex");
    return hash;
}
