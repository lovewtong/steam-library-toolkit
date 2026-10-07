'use strict';
// Only allowlisted protocol field names and value TYPES leave this recorder.
// Unknown keys and all scalar values (including IDs, names and tokens) are discarded.
const fields = new Set(['sessions', 'machine_name', 'client_instanceid', 'client_info',
  'local_users', 'apps', 'appid', 'app', 'app_type', 'games', 'game_count', 'name',
  'playtime_forever', 'playtime_2weeks', 'rtime_last_played', 'playtime_windows_forever',
  'playtime_mac_forever', 'playtime_linux_forever', 'playtime_deck_forever']);
function shape(value, depth = 0) {
  if (depth > 6) return {type: 'depth_limit'};
  if (value === null) return {type: 'null'};
  if (Array.isArray(value)) {
    const variants = new Map();
    for (const item of value) {
      const description = shape(item, depth + 1);
      const key = JSON.stringify(description);
      variants.set(key, description);
      if (variants.size >= 32) break;
    }
    return {type: 'array', length: value.length, item_shapes: [...variants.values()],
      variants_may_be_truncated: variants.size >= 32};
  }
  if (typeof value === 'object') {
    const properties = {};
    let omitted = 0;
    for (const key of Object.keys(value).sort()) {
      if (fields.has(key)) properties[key] = shape(value[key], depth + 1);
      else omitted++;
    }
    return {type: 'object', properties, omitted_fields: omitted};
  }
  return {type: typeof value === 'number' && Number.isInteger(value) ? 'integer' : typeof value};
}
module.exports = {shape};
