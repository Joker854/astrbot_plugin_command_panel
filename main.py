"""指令面板插件：以图片形式按插件分类展示群内可用指令、功能简介与使用权限。"""

import json
import re
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.permission import PermissionType, PermissionTypeFilter
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import star_handlers_registry

PLUGIN_NAME = "astrbot_plugin_command_panel"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "panel.html"

PERMISSION_LABELS = {
    PermissionType.ADMIN: "管理员",
    PermissionType.GROUP_ADMIN: "群管理员",
    PermissionType.SHARED_GROUP_ADMIN: "群管理员",
    PermissionType.MEMBER: "所有人",
}


class CommandPanelPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context, config)
        self.config = config or {}

    def _cfg(self, key: str, default):
        return self.config.get(key, default)

    def _parse_plugins_config(self) -> dict:
        """解析 plugins_config 文本(JSON)，解析失败时按空配置处理。"""
        raw = self._cfg("plugins_config", "")
        if not isinstance(raw, str) or not raw.strip():
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError as e:
            logger.warning(f"plugins_config 不是合法 JSON，已忽略: {e}")
            return {}

    def _get_wake_prefix(self, umo: str | None) -> str:
        try:
            prefixes = self.context.get_config(umo).get("wake_prefix", ["/"])
            for p in prefixes:
                if p:
                    return p
        except Exception as e:  # noqa: BLE001 配置读取失败时退回默认前缀
            logger.debug(f"读取 wake_prefix 失败，使用默认值: {e}")
        return "/"

    @staticmethod
    def _command_full_name(cmd: CommandFilter) -> str:
        parent = (cmd.parent_command_names or [""])[0]
        return f"{parent} {cmd.command_name}".strip()

    @staticmethod
    def _command_params(cmd: CommandFilter) -> str:
        try:
            params = cmd.print_types()
        except Exception:  # noqa: BLE001 参数签名异常不应影响面板展示
            return ""
        # print_types 对可选参数输出形如 "idx(NoneType)=None"，精简为参数名
        params = params.replace("(NoneType)=None", "")
        params = re.sub(r"=None\b", "", params)
        return params.strip(",").replace(",,", ",")

    @staticmethod
    def _command_permission(handler) -> str:
        for f in handler.event_filters:
            if isinstance(f, PermissionTypeFilter):
                return PERMISSION_LABELS.get(f.permission_type, "所有人")
        return "所有人"

    def _collect_panel_data(self, event: AstrMessageEvent) -> dict:
        plugins_conf = self._parse_plugins_config()
        hide_admin_for_member = (
            bool(self._cfg("hide_admin_commands_for_member", False))
            and not event.is_admin()
        )
        show_builtin = bool(self._cfg("show_builtin_plugins", True))
        hide_self = bool(self._cfg("hide_self", False))

        plugins: list[dict] = []
        plugin_index: dict[str, dict] = {}
        total_commands = 0

        for handler in star_handlers_registry:
            if not handler.enabled:
                continue
            meta = star_map.get(handler.handler_module_path)
            if not meta or not meta.activated:
                continue
            cmd_filter = next(
                (f for f in handler.event_filters if isinstance(f, CommandFilter)),
                None,
            )
            if cmd_filter is None:
                continue

            pname = meta.name or meta.root_dir_name or "未知插件"
            pconf = plugins_conf.get(pname)
            if pconf is None:  # 允许以目录名(root_dir_name)作为配置键
                pconf = plugins_conf.get(meta.root_dir_name or "", {})
            if pconf.get("show") is False:
                continue
            if not show_builtin and meta.reserved:
                continue
            if hide_self and pname == PLUGIN_NAME:
                continue

            full_name = self._command_full_name(cmd_filter)
            hide_patterns = pconf.get("hide_commands") or []
            try:
                if any(re.search(pat, full_name) for pat in hide_patterns):
                    continue
            except re.error as e:
                logger.warning(f"插件 {pname} 的 hide_commands 含非法正则，已忽略: {e}")

            permission = self._command_permission(handler)
            if hide_admin_for_member and permission == "管理员":
                continue

            params = self._command_params(cmd_filter)
            aliases = sorted(cmd_filter.alias) if cmd_filter.alias else []

            plugin_entry = plugin_index.get(pname)
            if plugin_entry is None:
                plugin_entry = {
                    "name": pconf.get("alias") or meta.display_name or pname,
                    "version": meta.version or "",
                    "desc": pconf.get("desc") or meta.short_desc or meta.desc or "",
                    "commands": [],
                }
                plugin_index[pname] = plugin_entry
                plugins.append(plugin_entry)

            plugin_entry["commands"].append(
                {
                    "name": full_name,
                    "params": params,
                    "aliases": aliases,
                    "desc": handler.desc or "暂无描述",
                    "perm": permission,
                }
            )
            total_commands += 1

        for entry in plugins:
            entry["commands"].sort(key=lambda c: c["name"])

        return {
            "title": self._cfg("panel_title", "指令面板"),
            "theme": self._cfg("theme_color", "#5b8ff9"),
            "wake_prefix": self._get_wake_prefix(event.unified_msg_origin),
            "plugins": plugins,
            "show_stats": bool(self._cfg("show_stats", True)),
            "stats": f"共 {len(plugins)} 个插件 · {total_commands} 个可用指令",
        }

    @staticmethod
    def _build_plain_text(data: dict) -> str:
        lines = [f"【{data['title']}】指令前缀: {data['wake_prefix'] or '无'}"]
        for plugin in data["plugins"]:
            header = plugin["name"]
            if plugin["version"]:
                header += f" ({plugin['version']})"
            lines.append(f"\n◆ {header}")
            for cmd in plugin["commands"]:
                params = f" {cmd['params']}" if cmd["params"] else ""
                lines.append(
                    f"  {data['wake_prefix']}{cmd['name']}{params} - "
                    f"{cmd['desc']} [{cmd['perm']}]"
                )
        if data["show_stats"]:
            lines.append(f"\n{data['stats']}")
        return "\n".join(lines)

    @filter.command("查看指令面板", alias={"指令面板", "面板", "commands"})
    async def panel(self, event: AstrMessageEvent):
        """查看当前可用的指令面板（图片）"""
        try:
            data = self._collect_panel_data(event)
            if not data["plugins"]:
                yield event.plain_result("当前没有可展示的指令。")
                return
            tmpl = TEMPLATE_PATH.read_text(encoding="utf-8")
            try:
                image_path = await self.html_render(
                    tmpl,
                    data,
                    return_url=False,
                    umo=event.unified_msg_origin,
                )
                yield event.image_result(image_path)
            except Exception as e:  # noqa: BLE001 渲染失败时回退为文本，不能让插件报错
                logger.warning(f"指令面板图片渲染失败，回退为文本输出: {e}")
                yield event.plain_result(self._build_plain_text(data))
        except Exception as e:  # noqa: BLE001 兜底，任何异常都不应导致插件崩溃
            logger.error(f"生成指令面板失败: {e}")
            yield event.plain_result("生成指令面板时出现问题，请稍后再试。")

    async def terminate(self):
        """插件被卸载/停用时调用"""
