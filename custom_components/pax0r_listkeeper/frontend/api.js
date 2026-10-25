/** Versioned HA WebSocket transport. UI state lives in the panel. */
export class ShoppingApi {
  constructor(hass) { this.hass = hass; }
  async call(action, fields = {}) {
    const response = await this.hass.callWS({
      type: `pax0r_listkeeper/${action}`, api_version: 1, ...fields,
    });
    return response.data;
  }
}
