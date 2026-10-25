# Home Assistant API review

Review date: October 25, 2026. Official documentation was accessible; fetching the `2026.10.4` source tag failed. The implementation review used `dev`. Source review is separate from runtime compatibility, whose actual results belong in [VALIDATION.md](VALIDATION.md).

| Area | Source and implementation decision |
| --- | --- |
| Config Flow | [Documentation](https://contributors.home-assistant.io/core/integrations/config-flow/), [native flow](https://github.com/home-assistant/core/blob/dev/homeassistant/components/shopping_list/config_flow.py): stable unique ID, `async_set_unique_id`, `async_create_entry`, validate connectivity before saving. |
| Options Flow | [Documentation](https://contributors.home-assistant.io/core/integrations/options-flow/): separate `OptionsFlow`, `self.config_entry`, update listener reloads the entry. |
| Native list | [Shopping List](https://www.home-assistant.io/integrations/shopping_list/), [platform](https://github.com/home-assistant/core/blob/dev/homeassistant/components/shopping_list/todo.py): stable UID/status, no reliable creation timestamp. |
| Read/write | [todo](https://www.home-assistant.io/integrations/todo/), [entity](https://github.com/home-assistant/core/blob/dev/homeassistant/components/todo/entity.py), [services](https://github.com/home-assistant/core/blob/dev/homeassistant/components/todo/services.py): `async_delete_todo_items` accepts UIDs. `todo.remove_item` also matches summaries and risks a UID/name collision. |
| Events | [ShoppingData](https://github.com/home-assistant/core/blob/dev/homeassistant/components/shopping_list/common.py): `shopping_list_updated` covers individual and bulk mutations. Events trigger snapshot reconciliation. Entity state events also detect availability changes. |
| Panel | [Documentation](https://contributors.home-assistant.io/frontend/custom-ui/panel/), [panel_custom](https://github.com/home-assistant/core/blob/dev/homeassistant/components/panel_custom/__init__.py): local ES modules, `async_register_panel`, `require_admin=True`; assets use `async_register_static_paths` and `StaticPathConfig`. |
| WebSocket | [Documentation](https://contributors.home-assistant.io/frontend/extending/websocket-api/): command schemas, `async_response`, `require_admin`, registration and `hass.callWS`. Authorization wraps the scheduled callback, not the raw coroutine. All operations require an administrator. |
| Recorder | [Documentation](https://www.home-assistant.io/integrations/recorder/), [helper](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/recorder.py), [implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/recorder/core.py): connection configuration has no stable public extension contract. |
| Async/lifecycle | [Documentation](https://contributors.home-assistant.io/core/internals/asyncio/): worker-thread SQL, event callbacks marked `@callback`, listener/task/engine cleanup on unload and HA stop. |

## Isolated implementation-dependent adapters

1. `infrastructure/ha/shopping_list.py` looks up `hass.data[DATA_COMPONENT].get_entity(entity_id)` to call UID-specific deletion without name matching. It verifies registry provider, availability, features and UID/status shape. Incompatible changes disable operations; there is no name-based deletion fallback.
2. `infrastructure/ha/database_config.py` uses `get_instance(hass)` and guarded optional `db_url` access. It never uses Recorder sessions. Missing or incompatible configuration falls back to separate SQLite or a manual URL. Connection secrets are not exposed through panel APIs or error logs.

`compat.py` supports `probatio` and earlier `voluptuous`. Reviewed `dev` sources use `probatio`; runtime checks remain necessary for each target version.

## Safe limitations

- User-reordered list positions are not creation times. Automatic deletion requires observed addition order; ambiguous startup/offline duplicates remain unchanged.
- HA has no public atomic compare-and-delete service. In the reviewed native implementation, in-memory UID deletion precedes its first `await`; the adapter checks immediately before entering that method. Other providers require separate audits.
- Events may coalesce. The latest snapshot is reconciled without inventing intermediate transitions. Uncertain timing preserves purchases instead of cancelling them.
- `hacs.json` expresses a 2026.10+ installation target, not verified compatibility. Fake-based contracts, in-process HA tests and real Docker scenarios are reported separately.
- Actual container testing exposed two lifecycle details: native add events may arrive after state notifications have already persisted the item, and one-time stop listeners unregister before their callback runs. Reconciliation now promotes the delayed UID-specific addition, and runtime cleanup owns a regular stop listener's unsubscription.
