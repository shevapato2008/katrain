# GN/GC 补充赛事下一批100个 exact core（只读候选）

## 范围与结论

基于已捕获生产快照选定100个 exact core、102局：2004韩国联赛48 core/50局；2007段位赛52 core/52局（已排除原30样本）。赛事类型与赛季可参考下列专业来源；本批逐局外部配对未核准，所有关联最终保持 HOLD，不产生批准、写库或翻译。

初步候选分类：{"CANDIDATE_REVIEW": 94, "HOLD_METADATA_CONFLICT": 6}。CANDIDATE_REVIEW仅表示没有发现当前日期/阶段冲突，不等于SAFE。

韩国联赛已有赛事类型id=50；只读查询未发现含“段位”的类型。2004赛季可跨至2005年1月2日；届次数字留空。2007按轮次、日期提出升段组候选，定段组与升段组不可仅凭统称合并，届次数字留空。

## 来源及证据边界

- [rank_schedule](https://sports.sina.com.cn/go/2007-06-29/10373008597.shtml)：当年专业赛事报道及组委会补充通知；2007 武汉段位赛、定段/升段分组、升段赛12轮及轮次日期；不支持所有逐局配对。
- [league_organizer](https://www.newswire.co.kr/newsRead.php?no=25989)：BadukTV 原发布方赛事总结新闻稿；2004 한국바둑리그赛事类型与赛季；不支持全部逐局配对。
- [league_final](https://sports.sina.com.cn/o/2005-01-03/11561331284.shtml)：当年专业赛事报道；2004赛季延续至2005年1月2日；不能按DT年份重命名赛季。

## 可复现选择

固定seed：`kifu-event-gn-gc-next100-2026-10-04-v1`；2004精确同名候选排除原30样本后全取48core；2007文件形core按12轮每轮取hash最小4个，再取剩余全局hash最小4个。运行同目录`.py`可从本地gzip复现JSON/MD/SHA，不连接生产。输入SHA256：`a2dc534a1022f76adaa761808052fbc009b0223e159e4603af0933a66fef4ac7`。范围绑定原捕获快照，后续处理应按album_id、exact raw/core、SGF SHA再核对。

## 后续扩展及冲突

2007补充候选池共592局，其中“第五轮半决赛”70局需单列HOLD：不能把半决赛当类型的一部分，也不能自动删除。升段赛程日期不符：album_id [70450]。2004另外3个明确半决赛候选不在本批，IDs [38869, 38877, 38878]；应分别核实阶段与对阵。

下一步按轮次赛果表补逐局棋手对阵，再用原SGF核对颜色、结果和职业段位；韩国先补球队/台次/常规赛或季后赛。GN/GC同源，不能重复计为两份外证。保留100个exact范围逐条决策，禁止创建覆盖整个文件名族的自动别名。

## 精确范围清单

完整原GN/GC、日期、对阵、原始路径及SHA在同名JSON。

|exact core|局数|album IDs|类型/赛季/轮次候选|候选分类|
|---|---:|---|---|---|
|040827kbl-4r-1g-2.sgf|1|103739|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|040919kbl-5r-1g-1.sgf|1|74049|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|041125kbl-7r-2g-4.sgf|1|30492|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|041126kbl-7r-2g-3.sgf|1|89510|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|041127kbl-7r-2g-2.sgf|1|83326|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|041203kbl-7r-3g-3.sgf|1|93232|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-05-13|1|105914|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-05-14|1|87287|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-05-20|1|74019|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-05-21|1|113472|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-05-28|1|89505|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-03|1|88341|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-04|1|93228|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-06|1|118639|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-11|1|87288|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-12|1|144813|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-24|1|74023|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-25|1|113473|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-06-26|1|83323|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-07-01|1|83024|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-07-02|1|103738|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-07-08|1|30481|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-07-09|1|89506|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-07-15|1|83025|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-08-05|1|74030|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-08-06|1|93229|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-08-12|1|30484|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-08-13|1|89507|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-08-26|1|74038|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-09|1|83028|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-10|1|122159|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-16|1|30495|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-17|1|89511|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-24|1|103741|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-26|1|111529|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-30|1|74060|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004-12-31|1|103742|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-caolisgf|1|38560|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-cuilisgf|1|50087|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-licaosgf|1|38851|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-lilisgf|1|97503|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-liliusgf|1|101338|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-limusgf|2|97588,101340|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-mulisgf|1|101336|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-piaocaosgf|1|38864|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-piaolisgf|1|101341|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-songcaosgf|1|38866|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2004kr-liansai-songlisgf|2|97589,101337|韩国围棋联赛/2004/None|CANDIDATE_REVIEW|
|2007cn-duan-1-dongypzhangtsgf|1|58393|中国围棋段位赛/2007/1|CANDIDATE_REVIEW|
|2007cn-duan-1-jiayftuqsgf|1|81929|中国围棋段位赛/2007/1|CANDIDATE_REVIEW|
|2007cn-duan-1-yezhangsgf|1|145761|中国围棋段位赛/2007/1|CANDIDATE_REVIEW|
|2007cn-duan-1-yinhtianzsgf|1|136360|中国围棋段位赛/2007/1|CANDIDATE_REVIEW|
|2007cn-duan-10-hangtplihssgf|1|71792|中国围棋段位赛/2007/10|CANDIDATE_REVIEW|
|2007cn-duan-10-mengtlgulysgf|1|67241|中国围棋段位赛/2007/10|CANDIDATE_REVIEW|
|2007cn-duan-10-wangwtangwxsgf|1|134741|中国围棋段位赛/2007/10|CANDIDATE_REVIEW|
|2007cn-duan-10-wangxysongrhsgf|1|133245|中国围棋段位赛/2007/10|CANDIDATE_REVIEW|
|2007cn-duan-10-wujchenbysgf|1|41215|中国围棋段位赛/2007/10|CANDIDATE_REVIEW|
|2007cn-duan-11-jinldongypsgf|1|58389|中国围棋段位赛/2007/11|CANDIDATE_REVIEW|
|2007cn-duan-11-qinyxweimrsgf|1|125085|中国围棋段位赛/2007/11|CANDIDATE_REVIEW|
|2007cn-duan-11-yuanzlujsgf|1|114705|中国围棋段位赛/2007/11|CANDIDATE_REVIEW|
|2007cn-duan-11-zhouwangsgf|1|137911|中国围棋段位赛/2007/11|CANDIDATE_REVIEW|
|2007cn-duan-12-dingllantsgf|1|57054|中国围棋段位赛/2007/12|CANDIDATE_REVIEW|
|2007cn-duan-12-dongypjiaqsgf|1|58406|中国围棋段位赛/2007/12|CANDIDATE_REVIEW|
|2007cn-duan-12-guotrlouxsgf|1|69895|中国围棋段位赛/2007/12|CANDIDATE_REVIEW|
|2007cn-duan-12-tuhusgf|1|76288|中国围棋段位赛/2007/12|CANDIDATE_REVIEW|
|2007cn-duan-2-tongyltuqsgf|1|136373|中国围棋段位赛/2007/2|CANDIDATE_REVIEW|
|2007cn-duan-2-wangjwangyxsgf|1|137849|中国围棋段位赛/2007/2|CANDIDATE_REVIEW|
|2007cn-duan-2-zhoukzhaoxhsgf|1|148154|中国围棋段位赛/2007/2|CANDIDATE_REVIEW|
|2007cn-duan-2-zhuyhlantsgf|1|96925|中国围棋段位赛/2007/2|CANDIDATE_REVIEW|
|2007cn-duan-3-lihlidysgf|1|98952|中国围棋段位赛/2007/3|CANDIDATE_REVIEW|
|2007cn-duan-3-wangcxliaoxwsgf|1|106221|中国围棋段位赛/2007/3|CANDIDATE_REVIEW|
|2007cn-duan-3-wangjnchenbysgf|1|41212|中国围棋段位赛/2007/3|CANDIDATE_REVIEW|
|2007cn-duan-3-wangstangjlsgf|1|134674|中国围棋段位赛/2007/3|CANDIDATE_REVIEW|
|2007cn-duan-3-zhaoxhluodlsgf|1|115151|中国围棋段位赛/2007/3|CANDIDATE_REVIEW|
|2007cn-duan-4-caibhwangpsgf|1|35002|中国围棋段位赛/2007/4|CANDIDATE_REVIEW|
|2007cn-duan-4-tangwxzhurksgf|1|134742|中国围棋段位赛/2007/4|CANDIDATE_REVIEW|
|2007cn-duan-4-xufryangxtsgf|1|144514|中国围棋段位赛/2007/4|CANDIDATE_REVIEW|
|2007cn-duan-4-zhaoxhlifsgf|1|99027|中国围棋段位赛/2007/4|CANDIDATE_REVIEW|
|2007cn-duan-5-caoxyfanwjsgf|1|36916|中国围棋段位赛/2007/5|HOLD_METADATA_CONFLICT|
|2007cn-duan-5-wangxytangwxsgf|1|134739|中国围棋段位赛/2007/5|HOLD_METADATA_CONFLICT|
|2007cn-duan-5-xujyjinjsgf|1|88915|中国围棋段位赛/2007/5|HOLD_METADATA_CONFLICT|
|2007cn-duan-5-zhangczhanghsgf|1|147355|中国围棋段位赛/2007/5|HOLD_METADATA_CONFLICT|
|2007cn-duan-5-zhangxbfangjsgf|1|60107|中国围棋段位赛/2007/5|HOLD_METADATA_CONFLICT|
|2007cn-duan-6-wanghycuicsgf|1|48045|中国围棋段位赛/2007/6|CANDIDATE_REVIEW|
|2007cn-duan-6-yuanzwutsgf|1|140909|中国围棋段位赛/2007/6|CANDIDATE_REVIEW|
|2007cn-duan-6-zhanglhanhsgf|1|70450|中国围棋段位赛/2007/6|HOLD_METADATA_CONFLICT|
|2007cn-duan-6-zhangqxufrsgf|1|144512|中国围棋段位赛/2007/6|CANDIDATE_REVIEW|
|2007cn-duan-7-baigyliuxsgf|1|30352|中国围棋段位赛/2007/7|CANDIDATE_REVIEW|
|2007cn-duan-7-lijwuxysgf|1|99788|中国围棋段位赛/2007/7|CANDIDATE_REVIEW|
|2007cn-duan-7-wangjnliuylsgf|1|113407|中国围棋段位赛/2007/7|CANDIDATE_REVIEW|
|2007cn-duan-7-zhangwzhangdysgf|1|147372|中国围棋段位赛/2007/7|CANDIDATE_REVIEW|
|2007cn-duan-8-huangctaoxsgf|1|76970|中国围棋段位赛/2007/8|CANDIDATE_REVIEW|
|2007cn-duan-8-lizwangxysgf|1|105056|中国围棋段位赛/2007/8|CANDIDATE_REVIEW|
|2007cn-duan-8-tuqxzysgf|1|136568|中国围棋段位赛/2007/8|CANDIDATE_REVIEW|
|2007cn-duan-8-wangnqchendlsgf|1|41235|中国围棋段位赛/2007/8|CANDIDATE_REVIEW|
|2007cn-duan-8-zhouksunlsgf|1|133895|中国围棋段位赛/2007/8|CANDIDATE_REVIEW|
|2007cn-duan-9-lizcaibhsgf|1|34993|中国围棋段位赛/2007/9|CANDIDATE_REVIEW|
|2007cn-duan-9-louxyangxtsgf|1|114343|中国围棋段位赛/2007/9|CANDIDATE_REVIEW|
|2007cn-duan-9-tuqlantsgf|1|96924|中国围棋段位赛/2007/9|CANDIDATE_REVIEW|
|2007cn-duan-9-zhangwjzhaosxsgf|1|147661|中国围棋段位赛/2007/9|CANDIDATE_REVIEW|
