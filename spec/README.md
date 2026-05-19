# SD-WAN 璇婃柇骞冲彴瑙勮寖绱㈠紩

## 馃摎 瑙勮寖鏂囨。瀵艰埅

鏈枃妗ｆ彁渚涙墍鏈夋妧鏈鑼冦€侀厤缃爣鍑嗗拰鏈€浣冲疄璺电殑绱㈠紩锛屽府鍔╁紑鍙戣€呭揩閫熷畾浣嶆墍闇€淇℃伅銆?
---

## 馃搸 婧愮爜鍔熻兘瀹炵幇鏂囨。闀滃儚锛圥0锛?
- **[00_core/implementation_doc_mirror.md](00_core/implementation_doc_mirror.md)** 猸愨瓙猸?**蹇呰**  
  - `src/**/*.py` 涓?`docs/implementation/src/**/*.md` **涓€姣斾竴璺緞**鏄犲皠  
  - 鏂囨。蹇呭绔犺妭銆佽Е鍙戞椂鏈恒€佹ā鏉?HTML 绛夎祫浜у鐞嗐€佽眮鍏嶄笌 **pre-commit 绱㈠紩闂ㄧ**  
  - **Agent 闃呰椤哄簭**锛歚docs/implementation/FLOW_*.md` 鈫?`docs/implementation/SRC_INDEX.md` 鈫?`docs/implementation/src/...` 鈫?灞€閮ㄦ簮鐮? 
  - Cursor / Agent 蹇呭畧瑙?**[`.cursor/rules/sdwan-p0-core.md`](../.cursor/rules/sdwan-p0-core.md)**锛圥0锛夛紱绱㈠紩瑙?**[`.cursor/RULES.md`](../.cursor/RULES.md)**銆?*[`AI_SPEC_GUIDE.md`](../.cursor/AI_SPEC_GUIDE.md)**锛堜粎鏌ラ槄琛級  
- **娴佺▼鍦板浘**锛歔../docs/implementation/FLOW_quick_check.md](../docs/implementation/FLOW_quick_check.md) 路 [../docs/implementation/FLOW_deep_dive.md](../docs/implementation/FLOW_deep_dive.md) 路 [../docs/implementation/FLOW_business_diagnose.md](../docs/implementation/FLOW_business_diagnose.md)  
- **鍏ㄦ爲绱㈠紩锛堢敓鎴愶級**锛歔../docs/implementation/SRC_INDEX.md](../docs/implementation/SRC_INDEX.md)锛坄python scripts/generate_implementation_index.py`锛? 
- **浜虹被閫熸煡**锛歔../docs/implementation/README.md](../docs/implementation/README.md)

---

## 馃攳 鎸夊姛鑳芥ā鍧楀垎绫?
### 1锔忊儯 Traceroute / 璺緞杩借釜 猸?
#### 鏍稿績瑙勮寖
- **[20_domain/probe/probe_traceroute.md](20_domain/probe/probe_traceroute.md)** 猸愨瓙 **蹇呰**
  - 馃搹 鏍囧噯閰嶇疆锛?璺?脳 3娆?脳 5绉?= 105绉?  - 馃敘 璁＄畻鍏紡鍜岃秴鏃跺眰绾ц璁?  - 鈿欙笍 Flow灞傚拰鏈嶅姟灞傞厤缃ず渚?  - 馃洜锔?瀹炵幇瑕佹眰鍜屾暟鎹ā鍨?  - 馃搳 鍦烘櫙鍖栭厤缃姣?
#### 瀹炴柦鎸囧崡
- [../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md](../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md) - 璇︾粏鐨勫満鏅垎鏋愬拰鏅鸿兘閰嶇疆绠楁硶
- [../docs/TRACEROUTE_EMPTY_PATH_FIX.md](../docs/TRACEROUTE_EMPTY_PATH_FIX.md) - 绌鸿矾寰勯棶棰樹慨澶?- [../docs/TRACEROUTE_PATH_DISPLAY_ENHANCEMENT.md](../docs/TRACEROUTE_PATH_DISPLAY_ENHANCEMENT.md) - 璺緞鏄剧ず澧炲己
- [../docs/TRACEROUTE_PROCESS_VARIABLE_FIX.md](../docs/TRACEROUTE_PROCESS_VARIABLE_FIX.md) - 杩涚▼鍙橀噺淇
- [../docs/TRACEROUTE_TIMEOUT_HOP_DISPLAY.md](../docs/TRACEROUTE_TIMEOUT_HOP_DISPLAY.md) - 瓒呮椂璺崇偣鏄剧ず
- [../docs/WINDOWS_TRACERT_MISSING_HOPS_FIX.md](../docs/WINDOWS_TRACERT_MISSING_HOPS_FIX.md) - Windows缂哄け璺崇偣淇

#### 鐩稿叧鏈嶅姟瀹炵幇
- `src/sdwan_desktop/services/dns_split.py` - DNS鍒嗘祦鍜孋PE閾捐矾妫€娴嬶紙鍖呭惈Traceroute璋冪敤锛?- `src/sdwan_desktop/tools/implementations/network/traceroute.py` - Traceroute宸ュ叿瀹炵幇

---

### 2锔忊儯 ICMP / Ping 鎺㈡祴

#### 鏍稿績瑙勮寖
- **[20_domain/probe/probe_icmp.md](20_domain/probe/probe_icmp.md)** 猸愨瓙 **蹇呰**
  - 馃搹 ICMP鍗忚鏍囧噯
  - 馃敡 鎺㈡祴鍙傛暟鍜屾暟鎹ā鍨?  - 馃洜锔?瀹炵幇瑕佹眰鍜屽钩鍙板吋瀹规€?  - 馃搳 鎬ц兘瑕佹眰鍜屽畨鍏ㄨ€冭檻

#### 鐩稿叧鏈嶅姟瀹炵幇
- `src/sdwan_desktop/services/connectivity.py` - 杩為€氭€ф祴璇曟湇鍔?- `src/sdwan_desktop/tools/implementations/network/ping.py` - Ping宸ュ叿瀹炵幇

---

### 3锔忊儯 DNS 瑙ｆ瀽涓庡垎娴?
#### 鏍稿績瑙勮寖
- **[20_domain/probe/probe_dns.md](20_domain/probe/probe_dns.md)** 猸愨瓙 **蹇呰**
  - 馃搹 DNS鍗忚鏍囧噯
  - 馃敡 瑙ｆ瀽鍙傛暟鍜屾暟鎹ā鍨?  - 馃洜锔?瀹炵幇瑕佹眰鍜岀紦瀛樼瓥鐣?
#### DNS鍒嗘祦娴嬭瘯
- [../docs/DNS_SPLIT_INDEPENDENT_TEST_GUIDE.md](../docs/DNS_SPLIT_INDEPENDENT_TEST_GUIDE.md) - DNS鍒嗘祦鐙珛娴嬭瘯鎸囧崡
- [../docs/DNS_SPLIT_AND_PATH_DISPLAY_FIX.md](../docs/DNS_SPLIT_AND_PATH_DISPLAY_FIX.md) - DNS鍒嗘祦鍜岃矾寰勬樉绀轰慨澶?- [../docs/DNS_SPLIT_DISPLAY_FIX.md](../docs/DNS_SPLIT_DISPLAY_FIX.md) - DNS鍒嗘祦鏄剧ず淇
- [../docs/dns_split_timeout_fix.md](../docs/dns_split_timeout_fix.md) - DNS鍒嗘祦瓒呮椂淇
- [../docs/DNS_SPLIT_FIX_20260502.md](../docs/DNS_SPLIT_FIX_20260502.md) 猸?**鏈€鏂颁慨澶?*

#### 鐩稿叧鏈嶅姟瀹炵幇
- `src/sdwan_desktop/services/dns_split.py` - DNS鍒嗘祦娴嬭瘯鏈嶅姟
- `src/sdwan_desktop/interface/cli/commands/quick_check.py` - CLI鍛戒护瀹炵幇

---

### 4锔忊儯 TCP 绔彛鎺㈡祴

#### 鏍稿績瑙勮寖
- **[20_domain/probe/probe_tcp.md](20_domain/probe/probe_tcp.md)** 猸愨瓙 **蹇呰**
  - 馃搹 TCP鍗忚鏍囧噯
  - 馃敡 鎺㈡祴鍙傛暟鍜屾暟鎹ā鍨?  - 馃洜锔?瀹炵幇瑕佹眰鍜屽苟鍙戞帶鍒?
#### 鐩稿叧鏈嶅姟瀹炵幇
- `src/sdwan_desktop/tools/implementations/network/tcping.py` - TCPing宸ュ叿瀹炵幇

---

### 5锔忊儯 CPE 閾捐矾璺敱妫€娴?
#### 浼樺寲鏂囨。
- [../docs/CPE_LINK_ROUTING_OPTIMIZATION.md](../docs/CPE_LINK_ROUTING_OPTIMIZATION.md) - CPE閾捐矾璺敱浼樺寲
- [../docs/CPE_LINK_ROUTING_PERFORMANCE_OPTIMIZATION.md](../docs/CPE_LINK_ROUTING_PERFORMANCE_OPTIMIZATION.md) - 鎬ц兘浼樺寲
- [../docs/CPE_LINK_ROUTING_TCPING_OPTIMIZATION.md](../docs/CPE_LINK_ROUTING_TCPING_OPTIMIZATION.md) - TCPing浼樺寲
- [../docs/CPE_LINK_ROUTING_DNS_FIX_SUMMARY.md](../docs/CPE_LINK_ROUTING_DNS_FIX_SUMMARY.md) - DNS淇鎬荤粨
- [../docs/cpe_link_routing_and_tools_output_fix.md](../docs/cpe_link_routing_and_tools_output_fix.md) - 宸ュ叿鍜岃緭鍑轰慨澶?- [../docs/cpe_link_routing_dns_failure_optimization.md](../docs/cpe_link_routing_dns_failure_optimization.md) - DNS澶辫触浼樺寲

#### 鐩稿叧鏈嶅姟瀹炵幇
- `src/sdwan_desktop/services/dns_split.py` - CpeLinkRouteResult鏁版嵁妯″瀷鍜屾娴嬫柟娉?
---

### 6锔忊儯 Flow 寮曟搸涓庢墽琛屾祦绋?
#### 鏍稿績瑙勮寖
- **[SDWAN_SPEC.md](SDWAN_SPEC.md)** 猸愨瓙猸?**鏍稿績瑙勮寖**
  - 馃彈锔?鏋舵瀯鍒嗗眰鍜岃亴璐ｅ垝鍒?  - 馃搳 鏁版嵁濂戠害鍜岀被鍨嬪畾涔?  - 馃攧 Flow寮曟搸鍜屾墽琛屾ā鍨?  - 馃洜锔?宸ュ叿绯荤粺瑙勮寖
  
- **[50_execution/pipeline_engine.md](50_execution/pipeline_engine.md)** - Pipeline寮曟搸瑙勮寖

#### 瀹炴柦璁″垝
- [sprint3_plan.md](sprint3_plan.md) - Sprint 3 璁″垝
- [sprint4_plan.md](sprint4_plan.md) - Sprint 4 璁″垝
- [sprint5_plan.md](sprint5_plan.md) - Sprint 5 璁″垝
- [sprint6_plan.md](sprint6_plan.md) - Sprint 6 璁″垝
- [sprint7_plan.md](sprint7_plan.md) - Sprint 7 璁″垝
- [sprint8_plan.md](sprint8_plan.md) - Sprint 8 璁″垝
- [sprint9_project_closure_plan.md](sprint9_project_closure_plan.md) - Sprint 9 椤圭洰鏀跺熬璁″垝

#### 鐩稿叧瀹炵幇
- `src/sdwan_desktop/runtime/engine.py` - Flow寮曟搸鏍稿績
- `src/sdwan_desktop/runtime/executor.py` - Step鎵ц鍣?- `src/sdwan_desktop/flow/definitions/` - Flow瀹氫箟

---

### 7锔忊儯 鏁版嵁濂戠害涓庣被鍨嬬郴缁?
#### 鏍稿績瑙勮寖
- **[00_core/data_contract.md](00_core/data_contract.md)** - 鏁版嵁濂戠害瑙勮寖
- **[00_core/state_context.md](00_core/state_context.md)** - 鐘舵€佷笂涓嬫枃瑙勮寖
- **[00_core/error_model.md](00_core/error_model.md)** - 閿欒妯″瀷瑙勮寖

#### 鐩稿叧瀹炵幇
- `src/sdwan_desktop/core/types/` - 绫诲瀷瀹氫箟
- `src/sdwan_desktop/core/errors/` - 閿欒瀹氫箟

---

### 8锔忊儯 鏋舵瀯涓庡垎灞傛ā鍨?
#### 鏍稿績瑙勮寖
- **[10_architecture/layering_model.md](10_architecture/layering_model.md)** - 鍒嗗眰鏋舵瀯妯″瀷

#### 鐩稿叧瀹炵幇
- `src/sdwan_desktop/interface/` - Interface Layer
- `src/sdwan_desktop/services/` - Service Layer
- `src/sdwan_desktop/tools/` - Tool Layer
- `src/sdwan_desktop/core/` - Core Layer

---

### 9锔忊儯 鎶ュ憡鐢熸垚

#### 鏍稿績瑙勮寖
- **[20_domain/reporting/report_schema.md](20_domain/reporting/report_schema.md)** - 鎶ュ憡Schema瑙勮寖

#### 鐩稿叧瀹炵幇
- `src/sdwan_desktop/reporting/` - 鎶ュ憡鐢熸垚妯″潡
- `src/sdwan_desktop/services/reporter/` - 鎶ュ憡鏈嶅姟

---

### 馃敓 涓€閿綋妫€娴佺▼

#### 鐙珛娴嬭瘯鍛戒护
- [../docs/INDEPENDENT_TEST_COMMANDS_GUIDE.md](../docs/INDEPENDENT_TEST_COMMANDS_GUIDE.md) - 鐙珛娴嬭瘯鍛戒护浣跨敤鎸囧崡
- [../QUICK_START_INDEPENDENT_TESTS.md](../QUICK_START_INDEPENDENT_TESTS.md) - 蹇€熷紑濮嬫寚鍗?- [../IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - 瀹炴柦鎬荤粨

#### 淇璁板綍
- [../docs/QUICK_CHECK_CRITICAL_FIX.md](../docs/QUICK_CHECK_CRITICAL_FIX.md) - 鍏抽敭淇
- [../docs/QUICK_CHECK_FLOW_CHAIN_REVIEW.md](../docs/QUICK_CHECK_FLOW_CHAIN_REVIEW.md) - Flow閾惧鏌?- [../docs/QUICK_CHECK_OPTIMIZATION.md](../docs/QUICK_CHECK_OPTIMIZATION.md) - 浼樺寲璁板綍
- [../docs/QUICK_CHECK_ANALYZER_REFACTORING.md](../docs/QUICK_CHECK_ANALYZER_REFACTORING.md) - 鍒嗘瀽鍣ㄩ噸鏋?
#### 鐩稿叧瀹炵幇
- `src/sdwan_desktop/flow/definitions/quick_check.py` - Quick Check Flow瀹氫箟
- `src/sdwan_desktop/interface/cli/commands/quick_check.py` - CLI鍛戒护瀹炵幇
- `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py` - GUI瀹炵幇

---

## 馃幆 鎸夊紑鍙戦樁娈靛垎绫?
### Phase 1: 鍩虹鏋舵瀯
- [SDWAN_SPEC.md](SDWAN_SPEC.md) - 鏍稿績瑙勮寖
- [00_core/](00_core/) - 鏁版嵁濂戠害
- [10_architecture/](10_architecture/) - 鏋舵瀯妯″瀷

### Phase 2: 鎺㈤拡瀹炵幇
- [20_domain/probe/probe_icmp.md](20_domain/probe/probe_icmp.md) - ICMP鎺㈡祴
- [20_domain/probe/probe_dns.md](20_domain/probe/probe_dns.md) - DNS鎺㈡祴
- [20_domain/probe/probe_tcp.md](20_domain/probe/probe_tcp.md) - TCP鎺㈡祴
- [20_domain/probe/probe_traceroute.md](20_domain/probe/probe_traceroute.md) - Traceroute鎺㈡祴

### Phase 3: Flow寮曟搸
- [50_execution/pipeline_engine.md](50_execution/pipeline_engine.md) - Pipeline寮曟搸
- [SDWAN_SPEC_PATCHES.md](SDWAN_SPEC_PATCHES.md) - 瑙勮寖琛ヤ竵

### Phase 4: 涓氬姟閫昏緫
- [detail_function_design.md](detail_function_design.md) - 璇︾粏鍔熻兘璁捐
- [sdwan_analyzer_project.md](sdwan_analyzer_project.md) - 椤圭洰鎬讳綋璁捐

### Phase 5: 鎶ュ憡涓庤緭鍑?- [20_domain/reporting/report_schema.md](20_domain/reporting/report_schema.md) - 鎶ュ憡Schema

---

## 馃挕 浣跨敤寤鸿

### 瀵逛簬Agent寮€鍙戣€?
1. **瀹炵幇Traceroute鍔熻兘鏃?*锛?   - 馃摉 棣栧厛闃呰锛歔20_domain/probe/probe_traceroute.md](20_domain/probe/probe_traceroute.md)
   - 馃敡 鍙傝€冩爣鍑嗛厤缃細7璺?脳 3娆?脳 5绉?= 105绉?   - 馃洜锔?鏌ョ湅瀹炴柦鎸囧崡锛歔../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md](../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md)

2. **瀹炵幇鍏朵粬鎺㈤拡鏃?*锛?   - 馃摉 闃呰瀵瑰簲鐨刾robe瑙勮寖鏂囨。
   - 馃敡 閬靛惊鏁版嵁妯″瀷瀹氫箟
   - 馃洜锔?鍙傝€冪幇鏈夊疄鐜颁唬鐮?
3. **寮€鍙慒low姝ラ鏃?*锛?   - 馃摉 闃呰[SDWAN_SPEC.md](SDWAN_SPEC.md)鐨凢low寮曟搸绔犺妭
   - 馃敡 閬靛惊鍒嗗眰鏋舵瀯鍘熷垯
   - 馃洜锔?鍙傝€冪幇鏈夌殑Flow瀹氫箟

### 瀵逛簬缁存姢鑰?
1. **鏌ユ壘淇璁板綍**锛?   - 浣跨敤鍏抽敭璇嶆悳绱?`../docs/*FIX*.md`
   - 鏌ョ湅鏈€鏂扮殑淇鏃ユ湡

2. **浜嗚В鏋舵瀯婕旇繘**锛?   - 闃呰Sprint璁″垝鏂囨。
   - 鏌ョ湅瑙勮寖琛ヤ竵鏂囨。

3. **鎬ц兘浼樺寲鍙傝€?*锛?   - 鏌ョ湅鍚勬ā鍧楃殑OPTIMIZATION鏂囨。
   - 鍙傝€冩渶浣冲疄璺电珷鑺?
---

## 馃搵 瑙勮寖浼樺厛绾?
| 浼樺厛绾?| 鏍囪瘑 | 璇存槑 | 绀轰緥 |
|--------|------|------|------|
| **P0** | 猸愨瓙猸?| 鏍稿績瑙勮寖锛屽繀椤婚伒瀹?| SDWAN_SPEC.md |
| **P1** | 猸愨瓙 | 閲嶈瑙勮寖锛屽己鐑堝缓璁?| probe_*.md |
| **P2** | 猸?| 鍙傝€冭鑼冿紝寤鸿閬靛惊 | 瀹炴柦鎸囧崡銆佷慨澶嶈褰?|

---

## 馃攧 鏇存柊璁板綍

| 鏃ユ湡 | 鐗堟湰 | 鏇存柊鍐呭 | 浣滆€?|
|------|------|---------|------|
| 2026-05-02 | v1.0 | 鍒濆鐗堟湰锛屾坊鍔燭raceroute瑙勮寖绱㈠紩 | SD-WAN鍥㈤槦 |

---

**鏈€鍚庢洿鏂?*: 2026-05-02  
**缁存姢鑰?*: SD-WAN 璇婃柇骞冲彴鍥㈤槦  
**鍙嶉娓犻亾**: 鎻愪氦Issue鎴栬仈绯绘妧鏈礋璐ｄ汉

