"""UI setup and options; SQL secrets never returned through the panel API."""

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .compat import vol
from .const import DOMAIN
from .infrastructure.database.store import SqlUnitOfWork
from .infrastructure.ha.database_config import database_url
from .infrastructure.ha.shopping_list import NativeShoppingList, UnsupportedList


def schema(defaults: dict):
    return vol.Schema(
        {
            vol.Required(
                "entity_id", default=defaults.get("entity_id", "todo.shopping_list")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    filter={"domain": "todo", "integration": "shopping_list"}
                )
            ),
            vol.Required("deduplicate", default=defaults.get("deduplicate", True)): bool,
            vol.Optional("database_url", default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional("reset_database_url", default=False): bool,
            vol.Optional("diagnostics", default=defaults.get("diagnostics", False)): bool,
        }
    )


async def validate(hass, data: dict) -> dict:
    await NativeShoppingList(hass, data["entity_id"]).read()
    url = database_url(hass, data.get("database_url", ""))
    uow = await hass.async_add_executor_job(SqlUnitOfWork, url)
    try:
        await hass.async_add_executor_job(uow.initialize)
    finally:
        await uow.close()
    return data


class Pax0rListkeeperFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                await validate(self.hass, user_input)
            except UnsupportedList:
                errors["base"] = "unsupported_list"
            except Exception:
                errors["base"] = "database_error"
            else:
                return self.async_create_entry(title="pax0r's Listkeeper", data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return Pax0rListkeeperOptions()


class Pax0rListkeeperOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        defaults = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            data = {**defaults, **user_input}
            if user_input.get("reset_database_url"):
                data["database_url"] = ""
            elif not user_input.get("database_url"):
                data["database_url"] = defaults.get("database_url", "")
            try:
                await validate(self.hass, data)
            except UnsupportedList:
                errors["base"] = "unsupported_list"
            except Exception:
                errors["base"] = "database_error"
            else:
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(step_id="init", data_schema=schema(defaults), errors=errors)
