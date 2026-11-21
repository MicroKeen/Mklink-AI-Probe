# 动态组件与接口绑定

本功能让用户和 Agent 基于已有 MKLink 能力组态自己的工作台。开发者 Agent 可新增受构建管理的组件或业务适配器；运行中的用户与 Agent 从真实目录创建实例、绑定接口、调整显示并保存。自然语言由当前 Agent 解释为已声明的语义动作，浏览器不运行 LLM。

通用开发流程由 `agent-ui-dev` skill 提供，本文件说明 MKLink 中实际的注册入口、调用形状和验证路径。共享协议、认证及命令回执见[语义工作台](frontend-workbench.md)，本轮验证结果见[验证报告](verification/agent-ui-workbench.md)。

## 组件、窗口和绑定

| 对象 | 当前实现 |
| --- | --- |
| 页面内窗口 | 工作台中的面板；12 列网格，可移动、缩放、停靠为标签组、聚焦及分离 |
| 控制窗口 | `type: controls` 面板，内部包含稳定 `component_id` 的 `widgets` |
| 组件类型 | `button` 动作按钮、`form` 参数表单、`value` 状态数值、`indicator` 状态灯；实际可选类型由共享 manifest 决定 |
| 动作绑定 | 指定目标 `panel_id`、动作名称、固定参数及创建时冻结的参数/effect 契约 |
| 状态绑定 | 指定目标 `panel_id` 和该目标 `read()` 已公开的状态路径 |
| 临时状态 | 按组件 ID 管理的表单草稿、显示值、执行状态、错误、结果及操作身份；移动组件不把它们当新组件重建 |

新增、绑定、停靠和保存都不执行业务。按钮执行才调用绑定动作；表单可以先填写后执行；状态数值和状态灯只读取公开状态。状态显示周期性刷新现有视图状态，不新建硬件采集；需要确切读值时使用 `component.read` 的回执。

绑定对象来自当前页面的 `SemanticSurface`。控制窗口不能互相绑定形成递归执行链；目标未就绪、被移除或动作的 schema/effect 改变时，组件显示绑定失效并拒绝执行，需用户或 Agent 显式重新绑定。面板名相同不代表同一个目标。

## 新增一种真实组件：沿用 indicator 路径

### 1. 先判断是否需要业务开发

若已有能力能完成需求，新增显示类型和绑定即可。若原 UI 已能完成但没有语义入口，在其原业务函数或 store 上增加 `SemanticSurface.catalog/read/execute`，必要时保留 `validate`；原 UI 和组件仍调用同一个实现。确实缺少业务功能时，先实现既有服务/API 层及测试，再开放绑定，不能用自定义 renderer 中直接 fetch 任意 URL 替代。

`SemanticAction` 声明 `name`、`description`、严格 `args` schema 和 `effect`。动作必须返回实际结果或真实 Promise；参数、设备 generation、采集所有权、类型写权限和原任务状态仍由既有路径校验。共享与本面板操作在描述中明确，不因放进独立窗口就成为独立采集。

### 2. 修改前后端共用 manifest

类型元数据唯一来源是 [`mklink/frontend_components.json`](../mklink/frontend_components.json)。已有 `indicator` 的完整定义为：

```json
{
  "title": "状态灯",
  "description": "Display a bound boolean or scalar status",
  "presentation": "value",
  "minW": 2,
  "minH": 1,
  "defaultW": 3,
  "defaultH": 1
}
```

将同类新增定义放入 `components` 下的稳定类型 ID。ID 使用小写字母开头的小写字母/数字/连字符，最长 64 字符；`presentation` 当前只能为 `button`、`form` 或 `value`。尺寸使用组件内部 12 列网格单位，均为 1–12 的整数且默认尺寸不小于最小尺寸。manifest 的 `version` 和当前组件实例 `version` 均为 1；破坏性结构变化需同时设计迁移，不能仅改数字。

前端 [`workbenchControls.ts`](../gui/src/lib/workbenchControls.ts) 从此文件注册类型，后端 [`frontend_layout.py`](../mklink/frontend_layout.py) 从同一文件校验类型、展示类别、尺寸与绑定。仅注册前端类型不构成可持久化扩展：未加入 manifest 的类型会被后端保存拒绝。manifest 不接受脚本、HTML、URL 或用户项目提供的类型定义。

### 3. 可选注册 renderer

默认按钮、表单和数值展示能够表达需求时不用新增 renderer。状态灯需要专有呈现，因此已有 [`WorkbenchIndicator.vue`](../gui/src/components/dash/WorkbenchIndicator.vue)，并在 [`WorkbenchPanel.vue`](../gui/src/components/dash/WorkbenchPanel.vue) 的模块入口注册：

```ts
import { registerControlRenderer } from '../../lib/workbenchControls'
import WorkbenchIndicator from './WorkbenchIndicator.vue'

registerControlRenderer('indicator', WorkbenchIndicator)
```

注册必须发生在 manifest 已加载、该类型组件挂载前。`registerControlRenderer` 内部使用 `markRaw` 保存 Vue 组件引用；配置文件不会保存 renderer。当前 `ControlPanel` 传入 `widget`、目标动作 `schema`、`busy` 和 `value`，接收 `read` 与 `invoke(args)` 事件，分别进入同一 `component.read`/`component.invoke` 路径。状态灯仅发出 `read`，并复用 `--input-bg`、`--fg`、`--muted`、`--success` 等主题变量。

新增 renderer 的可见操作必须具有同等语义入口；不可在 renderer 内增加一个只有鼠标能触发的业务动作。需要超出当前属性/事件模型的互动时，更新明确的组件契约、schema、状态和测试；不要在布局外壳增加针对每种业务类型的执行分支。

### 4. 绑定既有能力

[`workbenchBindings.ts`](../gui/src/lib/workbenchBindings.ts) 从宿主提供的目标目录解析真实面板，再按动作名称解析其当前 `SemanticSurface`。动作绑定保存规范化的 args/effect 契约；执行前重新核对契约，并合并固定参数和本次输入，按原 schema 校验。状态路径只遍历目标公开状态中的自有字段，拒绝原型相关路径及过大的字段。

[`useFrontendWorkbench.ts`](../gui/src/composables/useFrontendWorkbench.ts) 提供宿主调用，保留现有认证、目标身份和错误/未知结果处理。`component.invoke` 的外层目录保守声明为 `effect: device`；实际绑定动作的 effect 仍由目标目录与冻结契约确定。不得因为它看起来像按钮就跳过设备操作授权。

语义执行通过 `SemanticExecutionContext` 显式传递已受保护的调用上下文，嵌套绑定只复用身份一致的现有 guard，并在执行前后检查未知结果；UI 默认没有该上下文，始终经过连接与并发检查。新增中间 adapter 转发 `execute` 时需保留第三个上下文参数，不能用共享异步标记代替。

新类型应出现在用户类型选择器、`component.types` 和 `component.add` 的 enum 中。注册器及通用 ControlPanel 已覆盖实例新增、绑定、配置、输入、执行、删除和读取；自定义 renderer 不需要另造一套 Agent 接口。

## 自然语言到语义动作

先按共享协议选择明确的在线 `page_id`，读取当前目录与 revision，再按 `panel_id` 和动作 `name` 查出传输用 action ID。每一步提交独立命令，查询原回执并回读；不要拼接 action ID，也不要把下表当成一个批量事务。

下表 `W` 表示已发现且就绪的波形面板，`C`、`D` 为新建控制窗口，`B/F/V/I` 是对应 `component.add` 返回的真实 ID。这些字母是文档别名，调用时替换为返回值。表中的“宿主”决定应从哪个面板的 action catalog 取动作。

| 用户意图 | 宿主 / action name | 完整 args 示例 |
| --- | --- | --- |
| “增加一个采集控制台” | `workbench` / `panel.add` | `{"type":"controls","title":"采集控制台"}` → 记下返回的 C |
| “看看可以添加什么控件” | C / `component.types` | `{}` |
| “放一个显示图例按钮” | C / `component.add` | `{"type":"button","title":"显示图例"}` → B |
| “按钮控制这张波形的图例” | C / `component.bind` | `{"component_id":"B","panel_id":"W","action":"waveform.legend","args_json":"{\"visible\":true}"}` |
| “执行这个按钮” | C / `component.invoke` | `{"component_id":"B"}` |
| “增加采样间隔表单” | C / `component.add` | `{"type":"form","title":"采样间隔（秒）"}` → F |
| “绑定当前波形的共享采样间隔” | C / `component.bind` | `{"component_id":"F","panel_id":"W","action":"superwatch.interval","args_json":"{}"}` |
| “先填 5 ms，不执行” | C / `component.input` | `{"component_id":"F","args_json":"{\"interval\":0.005}"}` |
| “现在应用该表单” | C / `component.invoke` | `{"component_id":"F"}`；只有已授权相应共享设备操作时才执行 |
| “增加通道数量读数” | C / `component.add` | `{"type":"value","title":"波形通道数"}` → V |
| “读取这张图的通道总数” | C / `component.bind` | `{"component_id":"V","panel_id":"W","state_path":"channels.total"}` |
| “增加图例状态灯” | C / `component.add` | `{"type":"indicator","title":"图例状态"}` → I |
| “状态灯绑定图例是否显示” | C / `component.bind` | `{"component_id":"I","panel_id":"W","state_path":"view.legend"}` |
| “立即读回状态灯” | C / `component.read` | `{"component_id":"I"}` |
| “打开/关闭这个组件的配置” | C / `component.editor` | `{"component_id":"I","open":true}`；关闭用 `false` |
| “给状态灯改标题” | C / `component.configure` | `{"component_id":"I","title":"当前图例"}` |
| “将状态灯放到右侧” | C / `component.move` | `{"component_id":"I","x":8,"y":0,"w":3,"h":1}` |
| “把控制台移到下方并加宽” | `workbench` / `panel.move` | `{"panel_id":"C","x":0,"y":8,"w":12,"h":4}` |
| “控制台与这张波形停靠为标签” | `workbench` / `panel.dock` | `{"panel_id":"C","target_panel_id":"W"}` |
| “切换到控制台标签” | `workbench` / `panel.focus` | `{"panel_id":"C"}` |
| “把控制台分离出来” | `workbench` / `panel.undock` | `{"panel_id":"C"}` |
| “再开一个辅助控制台” | `workbench` / `panel.add` | `{"type":"controls","title":"辅助控制台"}` → D |
| “把状态灯移到辅助控制台” | `workbench` / `component.transfer` | `{"component_id":"I","target_panel_id":"D"}`；后续 I 的动作宿主改为 D |
| “解除状态灯绑定” | D / `component.unbind` | `{"component_id":"I"}` |
| “移除状态灯” | D / `component.remove` | `{"component_id":"I"}` |
| “关闭辅助控制台” | `workbench` / `panel.remove` | `{"panel_id":"D"}`；同时移除其中的组件视图，不停止共享业务 |
| “保存/恢复工作台” | `workbench` / `layout.save` 或 `layout.restore` | `{}`；恢复替换当前未保存的布局 |

`args_json` 是受限 JSON 对象字符串，不是脚本。`component.input` 替换本组件的本次表单输入，不执行、不保存，也不将私密草稿放入公共 read；省略字段仍采用绑定固定参数。`component.invoke` 若提供 `args_json`，以该次参数覆盖固定参数；省略时表单读取当前输入，按钮使用固定参数。

`component.bind` 的 button 固定参数需满足完整动作 schema；form 可只设置部分固定参数，执行时仍校验完整必填参数。上例采样间隔 API 单位是秒，5 ms 传入 0.005；始终以当时真实目录的范围与前置条件为准。

## 布局、状态与失败处理

布局版本 2 将组件放在控制面板 `widgets` 中，标签组放在 `docks` 中。面板、组件和标签组 ID 不重复；每个面板最多属于一个标签组。窗口与组件都校验最小尺寸、网格边界和重叠；遇到占位时移动至可用位置，回读实际位置。旧版本 1 先在内存中适配，显式保存后才升级文件，原共享 workspace 不被替代。

跨控制窗口移动保留组件 ID、绑定以及本页面中的临时输入和执行状态；不是复制后再次执行。新建、停靠、移动、保存、恢复都不连接设备、开始采集或调用绑定动作。表单草稿、显示值和在途执行不写入布局，重新打开页面不能据布局重放之前的操作。固定参数会保存，不能把令牌或私密待发送内容当固定参数。

组件 `read()` 返回配置、当前编辑器对象、执行状态、截断错误信息、操作身份和有界结果摘要。`operation_id` 是组件本次执行的关联标识；Agent 发出的传输命令仍以自己的 `command_id` 查询 broker receipt，二者不能混用。`unknown` 或响应丢失不代表未执行，应检查原回执及真实业务状态，不能移动组件、改 ID 或刷新页面后自动重发。

相同绑定的配置应用和布局恢复保留临时状态；恢复为不同绑定或类型时清除旧草稿与结果，避免把输入带到另一能力。执行中或结果未知的组件不能通过改绑、解绑或覆盖绑定的布局恢复清除记录；纯标题、几何及窗口移动仍可使用。一次新执行只显示该次操作的状态和结果。

不兼容/未知类型、无效布局或陈旧 revision 的保存会拒绝并保留已保存文件；绑定目标或契约失效则保留组件并提示重绑。当前没有任意远程类型热加载、独立操作系统窗口、跨屏同步或嵌套分割树。

## 交付新类型需要的验证

- 组件注册与真实目录：新类型可创建，用户和 Agent 都能配置/绑定；新增 renderer 的所有可见操作可通过语义执行并回读。
- 绑定：复用原业务函数，校验参数类型、契约变化和失效目标；错误原因和 unknown 可见，响应丢失不自动重放。
- 生命周期：双实例独立，跨窗口移动保留草稿/状态，关闭只释放视图；布局恢复不执行动作。
- 持久化：经真实后端保存并读取包含新类型的版本 2 布局，再在浏览器恢复；不能只测试前端类型注册或数组里出现实例。
- 设计：注册尺寸与主题变量实际生效，鼠标/Agent 路径一致，明暗主题、窄屏和键盘操作可用。

现有落点包括 `workbenchControls.test.ts`、`workbenchBindings.test.ts`、`ControlPanel.test.ts`、`WorkbenchTab.test.ts`、`workbenchLayout.test.ts` 及 `test_frontend_storage.py`。后者已有 indicator 的真实 API 往返和共享 manifest 扩展测试。按仓库要求经 `scripts/build_workspace.ps1` 运行针对检查、类型与生产构建；通过数字、浏览器和硬件证据由验证报告统一记录。
