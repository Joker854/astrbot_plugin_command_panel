# 指令面板（astrbot_plugin_command_panel）

发送指令后生成一张图片，按插件分类展示当前所有可用指令、功能简介与使用权限，方便群成员快速了解机器人能做什么。

## 使用

- `/查看指令面板`（别名：`/指令面板`、`/面板`、`/commands`）
- 返回一张按插件分组的指令面板图片；若图片渲染服务不可用，自动回退为文本列表。

## 配置

在 AstrBot WebUI「插件 → 指令面板 → 配置」中可视化修改：

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `panel_title` | 面板标题 | `指令面板` |
| `theme_color` | 主题色（十六进制） | `#5b8ff9` |
| `show_stats` | 底部显示插件/指令统计 | `true` |
| `show_builtin_plugins` | 是否展示 AstrBot 内置插件 | `true` |
| `hide_self` | 是否隐藏本插件 | `false` |
| `hide_admin_commands_for_member` | 对非管理员隐藏管理员指令 | `false` |
| `plugins_config` | 按插件的展示规则（JSON，带代码编辑器） | 见下 |

### plugins_config 示例

```json
{
  "astrbot_plugin_xxx": {
    "alias": "工具箱",
    "show": true,
    "desc": "自定义插件描述",
    "hide_commands": ["^test$", "debug"]
  }
}
```

- 键为插件名（`metadata.yaml` 中的 `name`），也可使用插件目录名。
- `alias`：可选，设置后图片中只展示别名。
- `show`：默认 `true`，设为 `false` 则该插件不出现在图片中。
- `desc`：可选，覆盖插件描述。
- `hide_commands`：正则表达式列表，命中指令全名（含指令组前缀）的指令不展示。

## 许可

MIT
